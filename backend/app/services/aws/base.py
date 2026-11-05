from datetime import datetime, timezone
from typing import Any

from botocore.config import Config
from botocore.exceptions import OperationNotPageableError

from app.core.config import settings


class AWSService:
    service_name = "AWS"
    client_name = "ec2"
    global_service = False

    def __init__(self, session: Any, region: str):
        self.session = session
        self.region = region
        self._client: Any | None = None

    def connect(self) -> Any:
        if self._client is None:
            client_region = self.region
            if self.global_service:
                partition = self.session.get_partition_for_region(self.region)
                preferred = {
                    "aws": "us-east-1",
                    "aws-cn": "cn-north-1",
                    "aws-us-gov": "us-gov-west-1",
                    "aws-iso": "us-iso-east-1",
                    "aws-iso-b": "us-isob-east-1",
                }.get(partition)
                available = self.session.get_available_regions(self.client_name, partition_name=partition)
                client_region = preferred if preferred in available else (available[0] if available else self.region)
            self._client = self.session.client(
                self.client_name,
                region_name=client_region,
                config=Config(
                    connect_timeout=settings.aws_connect_timeout_seconds,
                    read_timeout=settings.aws_read_timeout_seconds,
                    retries={"max_attempts": 3, "mode": "standard"},
                    user_agent_extra="CloudGuardDR/1.0",
                ),
            )
        return self._client

    def paginate(self, operation: str, result_key: str, **kwargs: Any) -> list[dict[str, Any]]:
        client = self.connect()
        try:
            paginator = client.get_paginator(operation)
        except (KeyError, ValueError, OperationNotPageableError):
            response = getattr(client, operation)(**kwargs)
            return list(response.get(result_key, []))
        return [item for page in paginator.paginate(**kwargs) for item in page.get(result_key, [])]

    def item(
        self,
        resource_id: str,
        name: str,
        resource_type: str,
        status: str,
        health: int,
        risk: str,
        details: str,
        metadata: dict[str, Any] | None = None,
        region: str | None = None,
    ) -> dict[str, Any]:
        return {
            "resource_id": str(resource_id),
            "name": str(name or resource_id)[:256],
            "resource_type": resource_type,
            "service": self.service_name,
            "region": region or self.region,
            "status": status,
            "health": max(0, min(100, int(health))),
            "risk": risk,
            "last_updated": datetime.now(timezone.utc),
            "details": details[:4000],
            "metadata": metadata or {},
        }

    def health(self, resource: dict[str, Any]) -> int:
        return int(resource.get("health", 0))

    def risk(self, resource: dict[str, Any]) -> str:
        return str(resource.get("risk", "Medium"))

    def recommendations(self, resource: dict[str, Any]) -> list[dict[str, Any]]:
        from app.services.recommendations import analyze_resources

        return analyze_resources([resource])

    def scan(self) -> list[dict[str, Any]]:
        raise NotImplementedError


def tag_name(tags: list[dict[str, str]] | None, fallback: str) -> str:
    return next((tag.get("Value", "") for tag in tags or [] if tag.get("Key") == "Name"), fallback)

