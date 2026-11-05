from collections import defaultdict
from typing import Any


def analyze_resources(resources: list[dict[str, Any]], unavailable_services: set[str] | None = None) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for resource in resources:
        meta = resource.get("metadata", {})
        service = resource.get("service", "")
        if service == "IAM" and resource.get("resource_type") == "IAM user" and meta.get("console_access") and meta.get("mfa_enabled") is False:
            grouped["enable-mfa"].append(resource)
        if service == "S3":
            if meta.get("versioning") != "Enabled":
                grouped["s3-versioning"].append(resource)
            if not meta.get("encrypted", False):
                grouped["encryption"].append(resource)
            if not meta.get("public_access_blocked", True):
                grouped["s3-public-access"].append(resource)
            if not meta.get("lifecycle_policy", False):
                grouped["s3-lifecycle"].append(resource)
        if service == "RDS":
            if not meta.get("encrypted", False):
                grouped["encryption"].append(resource)
            if not meta.get("multi_az", False):
                grouped["rds-multi-az"].append(resource)
            if int(meta.get("backup_retention_days", 0)) == 0:
                grouped["backup-plans"].append(resource)
        if service == "EBS" and resource.get("resource_type") == "EBS volume":
            if not meta.get("encrypted", False):
                grouped["encryption"].append(resource)
            if not meta.get("snapshot_available", False):
                grouped["ebs-snapshots"].append(resource)
        if service == "Security Groups" and not meta.get("restricted", True):
            grouped["security-groups"].append(resource)
        if service == "VPC" and not meta.get("flow_logs_enabled", False):
            grouped["vpc-flow-logs"].append(resource)

    if "CloudWatch" not in (unavailable_services or set()) and not any(
        item.get("service") == "CloudWatch" for item in resources
    ):
        grouped["cloudwatch-alarms"].extend(
            item for item in resources if item.get("service") in {"EC2", "RDS"}
        )

    descriptors = {
        "enable-mfa": ("Enable MFA for IAM users", "High", "IAM", 8,
                       "Require multi-factor authentication for each IAM user to reduce credential compromise risk."),
        "s3-versioning": ("Enable S3 bucket versioning", "High", "S3", 6,
                          "Enable versioning to recover from accidental deletion and overwrite."),
        "s3-public-access": ("Block public S3 access", "High", "S3", 9,
                             "Enable all S3 Block Public Access controls unless public hosting is explicitly required."),
        "encryption": ("Enable encryption at rest", "High", "Data protection", 7,
                       "Encrypt stored data with AWS-managed or customer-managed keys."),
        "s3-lifecycle": ("Configure S3 lifecycle policies", "Low", "S3", 2,
                         "Add lifecycle transitions and expiration rules to protect retention goals and control storage costs."),
        "rds-multi-az": ("Create Multi-AZ RDS deployments", "High", "RDS", 7,
                         "Use Multi-AZ deployment for synchronous standby failover in the primary region."),
        "backup-plans": ("Enable automated backup plans", "High", "RDS", 8,
                         "Configure and retain automated recovery points that meet your recovery objectives."),
        "ebs-snapshots": ("Enable EBS snapshots", "High", "EBS", 6,
                          "Create scheduled, retained snapshots so volumes can be restored after data loss."),
        "security-groups": ("Restrict open security group rules", "High", "Security Groups", 8,
                            "Remove unrestricted inbound rules and allow only required sources and ports."),
        "vpc-flow-logs": ("Enable VPC Flow Logs", "Medium", "VPC", 4,
                          "Capture network traffic metadata to support incident response and resilience analysis."),
        "cloudwatch-alarms": ("Enable CloudWatch alarms", "Medium", "CloudWatch", 5,
                              "Create actionable health, availability, and recovery objective alarms for critical workloads."),
    }
    output = []
    for key, affected in grouped.items():
        title, priority, service, improvement, description = descriptors[key]
        output.append({
            "recommendation_key": key,
            "title": title,
            "priority": priority,
            "affected_service": service,
            "estimated_score_improvement": min(improvement * len(affected), improvement * 3),
            "description": description,
            "status": "open",
            "resource_ids": [item["resource_id"] for item in affected],
        })
    return output

