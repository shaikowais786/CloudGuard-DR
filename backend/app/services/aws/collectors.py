from datetime import datetime, timezone
from typing import Any

from botocore.exceptions import ClientError

from app.services.aws.base import AWSService, tag_name


class EC2Service(AWSService):
    service_name = "EC2"
    client_name = "ec2"

    def scan(self) -> list[dict[str, Any]]:
        found = []
        for reservation in self.paginate("describe_instances", "Reservations"):
            for instance in reservation.get("Instances", []):
                state = instance.get("State", {}).get("Name", "unknown")
                if state in {"terminated", "shutting-down"}:
                    continue
                instance_id = instance["InstanceId"]
                public_ip = bool(instance.get("PublicIpAddress"))
                score = 92 if state == "running" else 70 if state == "stopped" else 55
                risk = "High" if public_ip else "Medium" if state != "running" else "Low"
                found.append(self.item(
                    instance_id, tag_name(instance.get("Tags"), instance_id), "EC2 instance", state.title(), score, risk,
                    "Public IPv4 address is assigned." if public_ip else f"Instance is {state}.",
                    {"availability_zone": instance.get("Placement", {}).get("AvailabilityZone"),
                     "public_ip": instance.get("PublicIpAddress"), "vpc_id": instance.get("VpcId"),
                     "security_group_ids": [g.get("GroupId") for g in instance.get("SecurityGroups", [])],
                     "platform": instance.get("PlatformDetails"), "instance_type": instance.get("InstanceType"),
                     "backup_enabled": False, "encrypted": None},
                ))
        return found


class RDSService(AWSService):
    service_name = "RDS"
    client_name = "rds"

    def scan(self) -> list[dict[str, Any]]:
        found = []
        for db in self.paginate("describe_db_instances", "DBInstances"):
            status = db.get("DBInstanceStatus", "unknown")
            multi_az = bool(db.get("MultiAZ"))
            retention = int(db.get("BackupRetentionPeriod", 0))
            encrypted = bool(db.get("StorageEncrypted"))
            public = bool(db.get("PubliclyAccessible"))
            issues = [label for okay, label in [(multi_az, "Multi-AZ"), (retention > 0, "automated backups"),
                                                 (encrypted, "encryption"), (not public, "private access")] if not okay]
            score = 96 - 12 * len(issues) if status == "available" else 45
            risk = "High" if public or not encrypted else "Medium" if issues else "Low"
            db_id = db["DBInstanceIdentifier"]
            found.append(self.item(
                db.get("DbiResourceId", db_id), db_id, "RDS database", status.title(), score, risk,
                f"Review {' and '.join(issues)}." if issues else "Multi-AZ, encrypted database with automated backups.",
                {"multi_az": multi_az, "backup_retention_days": retention, "backup_enabled": retention > 0,
                 "encrypted": encrypted, "publicly_accessible": public, "engine": db.get("Engine"),
                 "availability_zone": db.get("AvailabilityZone"), "endpoint": db.get("Endpoint", {}).get("Address")},
            ))
        return found


class S3Service(AWSService):
    service_name = "S3"
    client_name = "s3"
    global_service = True

    def scan(self) -> list[dict[str, Any]]:
        buckets = self.paginate("list_buckets", "Buckets")
        found = []
        for bucket in buckets:
            name = bucket["Name"]
            location = self.connect().get_bucket_location(Bucket=name).get("LocationConstraint") or "us-east-1"
            if location == "EU":
                location = "eu-west-1"
            bucket_client = self.session.client("s3", region_name=location)
            versioning = bucket_client.get_bucket_versioning(Bucket=name).get("Status", "Disabled")
            encrypted = True
            try:
                bucket_client.get_bucket_encryption(Bucket=name)
            except bucket_client.exceptions.ServerSideEncryptionConfigurationNotFoundError:
                encrypted = False
            public_blocked = True
            try:
                access = bucket_client.get_public_access_block(Bucket=name).get("PublicAccessBlockConfiguration", {})
                public_blocked = all(access.get(field, False) for field in (
                    "BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets",
                ))
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") == "NoSuchPublicAccessBlockConfiguration":
                    public_blocked = False
                else:
                    raise
            lifecycle = True
            try:
                bucket_client.get_bucket_lifecycle_configuration(Bucket=name)
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") == "NoSuchLifecycleConfiguration":
                    lifecycle = False
                else:
                    raise
            versioned = versioning == "Enabled"
            score = 96 - (16 if not encrypted else 0) - (16 if not public_blocked else 0) - (12 if not versioned else 0) - (5 if not lifecycle else 0)
            risk = "High" if not encrypted or not public_blocked else "Medium" if not versioned or not lifecycle else "Low"
            issues = [label for okay, label in [(versioned, "versioning"), (encrypted, "encryption"),
                                                 (public_blocked, "public access blocks"), (lifecycle, "a lifecycle policy")] if not okay]
            found.append(self.item(
                name, name, "S3 bucket", "Active", score, risk,
                f"Configure {' and '.join(issues)}." if issues else "Versioning, encryption, and lifecycle policy are configured.",
                {"versioning": versioning, "encrypted": encrypted, "lifecycle_policy": lifecycle,
                 "backup_enabled": versioned, "public_access_blocked": public_blocked}, location,
            ))
        return found


class IAMService(AWSService):
    service_name = "IAM"
    client_name = "iam"
    global_service = True

    def scan(self) -> list[dict[str, Any]]:
        found = []
        for user in self.paginate("list_users", "Users"):
            username = user["UserName"]
            console_access = True
            try:
                self.connect().get_login_profile(UserName=username)
            except self.connect().exceptions.NoSuchEntityException:
                console_access = False
            mfa = self.connect().list_mfa_devices(UserName=username).get("MFADevices", [])
            enabled = bool(mfa)
            score = 94 if enabled or not console_access else 58
            found.append(self.item(
                user["UserId"], username, "IAM user", "Active", score, "Low" if enabled or not console_access else "High",
                "MFA is enabled." if enabled else "Console sign-in is disabled." if not console_access else "Console user does not have a registered MFA device.",
                {"mfa_enabled": enabled if console_access else None, "console_access": console_access,
                 "created_at": user.get("CreateDate", datetime.now(timezone.utc)).isoformat(),
                 "backup_enabled": None, "encrypted": None}, "global",
            ))
        for role in self.paginate("list_roles", "Roles"):
            role_name = role["RoleName"]
            found.append(self.item(
                role["RoleId"], role_name, "IAM role", "Active", 90, "Low",
                "Role trust policy and usage should be reviewed as part of access governance.",
                {"arn": role.get("Arn"), "created_at": role.get("CreateDate", datetime.now(timezone.utc)).isoformat(),
                 "mfa_enabled": None, "encrypted": None}, "global",
            ))
        for group in self.paginate("list_groups", "Groups"):
            group_name = group["GroupName"]
            found.append(self.item(
                group["GroupId"], group_name, "IAM group", "Active", 88, "Low",
                "Review attached policies and group membership during access reviews.",
                {"arn": group.get("Arn"), "created_at": group.get("CreateDate", datetime.now(timezone.utc)).isoformat(),
                 "mfa_enabled": None, "encrypted": None}, "global",
            ))
        return found


class CloudWatchService(AWSService):
    service_name = "CloudWatch"
    client_name = "cloudwatch"

    def scan(self) -> list[dict[str, Any]]:
        found = []
        alarms = self.paginate("describe_alarms", "MetricAlarms")
        alarms.extend(self.paginate("describe_alarms", "CompositeAlarms"))
        for alarm in alarms:
            state = alarm.get("StateValue", "INSUFFICIENT_DATA")
            score = 94 if state == "OK" else 68 if state == "INSUFFICIENT_DATA" else 48
            risk = "High" if state == "ALARM" else "Medium" if state != "OK" else "Low"
            name = alarm.get("AlarmName", "CloudWatch alarm")
            found.append(self.item(
                name, name, "CloudWatch alarm", state.replace("_", " ").title(), score, risk,
                alarm.get("StateReason", "Alarm is configured."),
                {"state": state, "metric_name": alarm.get("MetricName"), "namespace": alarm.get("Namespace"),
                 "backup_enabled": None, "encrypted": None},
            ))
        return found


class SecurityGroupsService(AWSService):
    service_name = "Security Groups"
    client_name = "ec2"

    @staticmethod
    def _open(rule: dict[str, Any]) -> bool:
        return any(item.get("CidrIp") == "0.0.0.0/0" or item.get("CidrIpv6") == "::/0"
                   for item in rule.get("IpRanges", []) + rule.get("Ipv6Ranges", []))

    def scan(self) -> list[dict[str, Any]]:
        found = []
        for group in self.paginate("describe_security_groups", "SecurityGroups"):
            open_rules = [rule for rule in group.get("IpPermissions", []) if self._open(rule)]
            severe = any(rule.get("IpProtocol") == "-1" or
                         (rule.get("FromPort", -1) <= 3389 and rule.get("ToPort", -1) >= 22)
                         for rule in open_rules)
            risk = "High" if severe else "Medium" if open_rules else "Low"
            score = 96 if not open_rules else 52 if severe else 70
            group_id = group["GroupId"]
            found.append(self.item(
                group_id, group.get("GroupName", group_id), "Security group", "Active", score, risk,
                "Public inbound access is allowed." if open_rules else "No public IPv4/IPv6 inbound rules detected.",
                {"vpc_id": group.get("VpcId"), "public_inbound_rules": len(open_rules),
                 "restricted": not open_rules, "backup_enabled": None, "encrypted": None},
            ))
        return found


class VPCService(AWSService):
    service_name = "VPC"
    client_name = "ec2"

    def scan(self) -> list[dict[str, Any]]:
        found = []
        vpcs = self.paginate("describe_vpcs", "Vpcs")
        flow_logs = self.paginate("describe_flow_logs", "FlowLogs")
        logged_vpcs = {entry.get("ResourceId") for entry in flow_logs if entry.get("FlowLogStatus") == "ACTIVE"}
        for vpc in vpcs:
            vpc_id = vpc["VpcId"]
            flow_logs_enabled = vpc_id in logged_vpcs
            score = 93 if flow_logs_enabled else 76
            found.append(self.item(
                vpc_id, tag_name(vpc.get("Tags"), vpc_id), "VPC", vpc.get("State", "available").title(),
                score, "Low" if flow_logs_enabled else "Medium",
                "Flow logs are active." if flow_logs_enabled else "Enable VPC Flow Logs for network investigation.",
                {"cidr_block": vpc.get("CidrBlock"), "is_default": vpc.get("IsDefault", False),
                 "flow_logs_enabled": flow_logs_enabled, "backup_enabled": None, "encrypted": None},
            ))
        return found


class LambdaService(AWSService):
    service_name = "Lambda"
    client_name = "lambda"

    def scan(self) -> list[dict[str, Any]]:
        found = []
        for function in self.paginate("list_functions", "Functions"):
            name = function["FunctionName"]
            state = function.get("State", "Active")
            encrypted = True  # Lambda encrypts environment variables with an AWS-managed key by default.
            customer_key = bool(function.get("KMSKeyArn"))
            risk = "High" if state == "Failed" else "Low"
            found.append(self.item(
                function.get("FunctionArn", name), name, "Lambda function", state, 87 if encrypted else 78,
                risk, "Function configuration collected.",
                {"runtime": function.get("Runtime"), "last_modified": function.get("LastModified"),
                 "encrypted": encrypted, "customer_managed_key": customer_key,
                 "vpc_configured": bool(function.get("VpcConfig", {}).get("VpcId")),
                 "backup_enabled": None},
            ))
        return found


class EBSService(AWSService):
    service_name = "EBS"
    client_name = "ec2"

    def scan(self) -> list[dict[str, Any]]:
        found = []
        snapshots = self.paginate("describe_snapshots", "Snapshots", OwnerIds=["self"])
        snapshot_volumes = {snapshot.get("VolumeId") for snapshot in snapshots}
        for volume in self.paginate("describe_volumes", "Volumes"):
            volume_id = volume["VolumeId"]
            encrypted = bool(volume.get("Encrypted"))
            has_snapshot = volume_id in snapshot_volumes
            risk = "High" if not encrypted else "Medium" if not has_snapshot else "Low"
            found.append(self.item(
                volume_id, tag_name(volume.get("Tags"), volume_id), "EBS volume", volume.get("State", "unknown").title(),
                96 if encrypted and has_snapshot else 78 if encrypted else 58, risk,
                "Volume is encrypted and has a recovery snapshot." if encrypted and has_snapshot else
                "Create a recovery snapshot." if not has_snapshot else "Enable encryption for data at rest.",
                {"encrypted": encrypted, "snapshot_available": has_snapshot, "backup_enabled": has_snapshot,
                 "size_gb": volume.get("Size"), "volume_type": volume.get("VolumeType")},
            ))
        for snapshot in snapshots:
            snapshot_id = snapshot["SnapshotId"]
            found.append(self.item(
                snapshot_id, snapshot_id, "EBS snapshot", snapshot.get("State", "unknown").title(), 96, "Low",
                "Recovery snapshot is available.", {"volume_id": snapshot.get("VolumeId"), "backup_enabled": True,
                 "encrypted": bool(snapshot.get("Encrypted")), "start_time": snapshot.get("StartTime", datetime.now(timezone.utc)).isoformat()},
            ))
        return found


class AvailabilityZonesService(AWSService):
    service_name = "Availability Zones"
    client_name = "ec2"

    def scan(self) -> list[dict[str, Any]]:
        return [self.item(
            zone["ZoneId"], zone["ZoneName"], "Availability Zone", zone.get("State", "available").title(), 100, "Low",
            f"Zone is {zone.get('State', 'available')} in {zone.get('RegionName', self.region)}.",
            {"zone_id": zone["ZoneId"], "zone_type": zone.get("ZoneType")}, zone.get("RegionName", self.region),
        ) for zone in self.paginate("describe_availability_zones", "AvailabilityZones", AllAvailabilityZones=False)]


class RegionsService(AWSService):
    service_name = "Regions"
    client_name = "ec2"

    def scan(self) -> list[dict[str, Any]]:
        return [self.item(
            region["RegionName"], region["RegionName"], "AWS Region", region.get("OptInStatus", "opt-in-not-required").title(),
            100 if region.get("OptInStatus") != "not-opted-in" else 0,
            "Low" if region.get("OptInStatus") != "not-opted-in" else "Medium",
            f"Region opt-in status: {region.get('OptInStatus', 'opt-in-not-required')}.",
            {"opt_in_status": region.get("OptInStatus")}, region["RegionName"],
        ) for region in self.paginate("describe_regions", "Regions", AllRegions=True)]

