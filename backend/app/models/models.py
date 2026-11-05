from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.utils.clock import utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    workspaces: Mapped[list["Workspace"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    owner: Mapped[User] = relationship(back_populates="workspaces")
    aws_accounts: Mapped[list["AWSAccount"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")
    scans: Mapped[list["Scan"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("owner_user_id", "name", name="uq_workspace_owner_name"),)


class AWSAccount(Base):
    __tablename__ = "aws_accounts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    account_name: Mapped[str] = mapped_column(String(160), nullable=False)
    account_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    user_arn: Mapped[str] = mapped_column(String(512), nullable=False)
    region: Mapped[str] = mapped_column(String(64), nullable=False)
    access_key_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    secret_key_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    connection_status: Mapped[str] = mapped_column(String(24), default="connected", nullable=False)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    workspace: Mapped[Workspace] = relationship(back_populates="aws_accounts")
    scans: Mapped[list["Scan"]] = relationship(back_populates="aws_account")


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    aws_account_id: Mapped[UUID | None] = mapped_column(ForeignKey("aws_accounts.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="running", nullable=False)
    overall_score: Mapped[int | None] = mapped_column(Integer)
    resource_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    finding_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    trend: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    workspace: Mapped[Workspace] = relationship(back_populates="scans")
    aws_account: Mapped[AWSAccount | None] = relationship(back_populates="scans")
    resources: Mapped[list["ScanResource"]] = relationship(back_populates="scan", cascade="all, delete-orphan")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="scan", cascade="all, delete-orphan")
    reports: Mapped[list["Report"]] = relationship(back_populates="scan", cascade="all, delete-orphan")
    history: Mapped["ScanHistory | None"] = relationship(back_populates="scan", cascade="all, delete-orphan", uselist=False)


class ScanResource(Base):
    __tablename__ = "scan_resources"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    scan_id: Mapped[UUID] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), index=True)
    aws_account_id: Mapped[UUID | None] = mapped_column(ForeignKey("aws_accounts.id", ondelete="SET NULL"), index=True)
    resource_id: Mapped[str] = mapped_column(String(256), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(128), nullable=False)
    service: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    health: Mapped[int] = mapped_column(Integer, nullable=False)
    risk: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    details: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    scan: Mapped[Scan] = relationship(back_populates="resources")
    __table_args__ = (
        UniqueConstraint("scan_id", "aws_account_id", "resource_id", name="uq_scan_resource_identity"),
        Index("ix_scan_resources_scan_service", "scan_id", "service"),
    )


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    scan_id: Mapped[UUID] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), index=True)
    recommendation_key: Mapped[str] = mapped_column(String(96), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    affected_service: Mapped[str] = mapped_column(String(64), nullable=False)
    estimated_score_improvement: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="open", nullable=False)
    resource_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    scan: Mapped[Scan] = relationship(back_populates="recommendations")
    __table_args__ = (UniqueConstraint("scan_id", "recommendation_key", name="uq_scan_recommendation_key"),)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    scan_id: Mapped[UUID] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    scan: Mapped[Scan] = relationship(back_populates="reports")


class ScanHistory(Base):
    __tablename__ = "scan_history"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    scan_id: Mapped[UUID] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), unique=True, index=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    scan_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    resources_scanned: Mapped[int] = mapped_column(Integer, nullable=False)
    findings: Mapped[int] = mapped_column(Integer, nullable=False)
    trend: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scan: Mapped[Scan] = relationship(back_populates="history")

