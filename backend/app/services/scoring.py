from typing import Any


PILLAR_WEIGHTS = {
    "Backup & recovery": 25,
    "Security": 20,
    "Availability": 20,
    "Observability": 15,
    "Network resilience": 10,
    "Data protection": 10,
}


def _ratio_score(values: list[bool], empty_score: int = 50) -> int:
    if not values:
        return empty_score
    return round(sum(values) * 100 / len(values))


def readiness(resources: list[dict[str, Any]]) -> dict[str, Any]:
    by_service: dict[str, list[dict[str, Any]]] = {}
    for resource in resources:
        by_service.setdefault(resource.get("service", ""), []).append(resource)
    data_resources = by_service.get("S3", []) + by_service.get("RDS", []) + [
        item for item in by_service.get("EBS", []) if item.get("resource_type") == "EBS volume"
    ]
    secured_resources = [item for item in resources if item.get("metadata", {}).get("encrypted") is not None]
    access_resources = [item for item in by_service.get("IAM", [])
                        if item.get("resource_type") == "IAM user" and item.get("metadata", {}).get("console_access")]
    public_network_resources = by_service.get("Security Groups", [])
    rds = by_service.get("RDS", [])
    ec2 = by_service.get("EC2", [])
    alarms = by_service.get("CloudWatch", [])
    vpcs = by_service.get("VPC", [])

    backup_values = []
    for item in data_resources:
        meta = item.get("metadata", {})
        if item["service"] == "S3":
            backup_values.append(meta.get("versioning") == "Enabled")
        elif item["service"] == "RDS":
            backup_values.append(bool(meta.get("backup_retention_days", 0)))
        else:
            backup_values.append(bool(meta.get("snapshot_available")))

    security_checks = [item.get("metadata", {}).get("mfa_enabled", False) for item in access_resources]
    security_checks += [item.get("metadata", {}).get("restricted", True) for item in public_network_resources]
    security_checks += [item.get("metadata", {}).get("encrypted", True) for item in secured_resources]
    security_checks += [item.get("metadata", {}).get("public_access_blocked", True)
                        for item in by_service.get("S3", [])]
    multi_az_checks = [item.get("metadata", {}).get("multi_az", False) for item in rds]
    ec2_zones = {item.get("metadata", {}).get("availability_zone") for item in ec2 if item.get("status", "").lower() == "running"}
    availability_checks = multi_az_checks + ([len(ec2_zones) >= 2] if ec2 else [])
    observability_checks = [item.get("metadata", {}).get("state") == "OK" for item in alarms]
    network_checks = [item.get("metadata", {}).get("flow_logs_enabled", False) for item in vpcs]
    data_checks = [item.get("metadata", {}).get("encrypted", False) for item in data_resources]

    scores = {
        "Backup & recovery": _ratio_score(backup_values),
        "Security": _ratio_score(security_checks),
        "Availability": _ratio_score(availability_checks),
        "Observability": _ratio_score(observability_checks),
        "Network resilience": _ratio_score(network_checks),
        "Data protection": _ratio_score(data_checks),
    }
    overall = round(sum(scores[pillar] * weight for pillar, weight in PILLAR_WEIGHTS.items()) / 100)
    risk = "Low" if overall >= 85 else "Medium" if overall >= 65 else "High"
    return {
        "overall_score": overall,
        "risk_indicator": risk,
        "pillars": [{"name": name, "score": scores[name], "weight": weight} for name, weight in PILLAR_WEIGHTS.items()],
    }

