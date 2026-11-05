"""Initial CloudGuard DR schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-19
"""
import sqlalchemy as sa
from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "name", name="uq_workspace_owner_name"),
    )
    op.create_index("ix_workspaces_owner_user_id", "workspaces", ["owner_user_id"], unique=False)
    op.create_table(
        "aws_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("account_name", sa.String(length=160), nullable=False),
        sa.Column("account_id", sa.String(length=32), nullable=False),
        sa.Column("user_arn", sa.String(length=512), nullable=False),
        sa.Column("region", sa.String(length=64), nullable=False),
        sa.Column("access_key_ciphertext", sa.Text(), nullable=False),
        sa.Column("secret_key_ciphertext", sa.Text(), nullable=False),
        sa.Column("connection_status", sa.String(length=24), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_aws_accounts_account_id", "aws_accounts", ["account_id"], unique=False)
    op.create_index("ix_aws_accounts_workspace_id", "aws_accounts", ["workspace_id"], unique=False)
    op.create_table(
        "scans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("aws_account_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=True),
        sa.Column("resource_count", sa.Integer(), nullable=False),
        sa.Column("finding_count", sa.Integer(), nullable=False),
        sa.Column("trend", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["aws_account_id"], ["aws_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scans_aws_account_id", "scans", ["aws_account_id"], unique=False)
    op.create_index("ix_scans_workspace_id", "scans", ["workspace_id"], unique=False)
    op.create_table(
        "scan_resources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("aws_account_id", sa.Uuid(), nullable=True),
        sa.Column("resource_id", sa.String(length=256), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("resource_type", sa.String(length=128), nullable=False),
        sa.Column("service", sa.String(length=64), nullable=False),
        sa.Column("region", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("health", sa.Integer(), nullable=False),
        sa.Column("risk", sa.String(length=16), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["aws_account_id"], ["aws_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scan_id", "aws_account_id", "resource_id", name="uq_scan_resource_identity"),
    )
    op.create_index("ix_scan_resources_aws_account_id", "scan_resources", ["aws_account_id"], unique=False)
    op.create_index("ix_scan_resources_risk", "scan_resources", ["risk"], unique=False)
    op.create_index("ix_scan_resources_region", "scan_resources", ["region"], unique=False)
    op.create_index("ix_scan_resources_scan_id", "scan_resources", ["scan_id"], unique=False)
    op.create_index("ix_scan_resources_scan_service", "scan_resources", ["scan_id", "service"], unique=False)
    op.create_index("ix_scan_resources_service", "scan_resources", ["service"], unique=False)
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("recommendation_key", sa.String(length=96), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("affected_service", sa.String(length=64), nullable=False),
        sa.Column("estimated_score_improvement", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("resource_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scan_id", "recommendation_key", name="uq_scan_recommendation_key"),
    )
    op.create_index("ix_recommendations_priority", "recommendations", ["priority"], unique=False)
    op.create_index("ix_recommendations_scan_id", "recommendations", ["scan_id"], unique=False)
    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reports_scan_id", "reports", ["scan_id"], unique=False)
    op.create_table(
        "scan_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("scan_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("resources_scanned", sa.Integer(), nullable=False),
        sa.Column("findings", sa.Integer(), nullable=False),
        sa.Column("trend", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_history_scan_id", "scan_history", ["scan_id"], unique=True)
    op.create_index("ix_scan_history_workspace_id", "scan_history", ["workspace_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scan_history_workspace_id", table_name="scan_history")
    op.drop_index("ix_scan_history_scan_id", table_name="scan_history")
    op.drop_table("scan_history")
    op.drop_index("ix_reports_scan_id", table_name="reports")
    op.drop_table("reports")
    op.drop_index("ix_recommendations_scan_id", table_name="recommendations")
    op.drop_index("ix_recommendations_priority", table_name="recommendations")
    op.drop_table("recommendations")
    op.drop_index("ix_scan_resources_service", table_name="scan_resources")
    op.drop_index("ix_scan_resources_scan_service", table_name="scan_resources")
    op.drop_index("ix_scan_resources_scan_id", table_name="scan_resources")
    op.drop_index("ix_scan_resources_region", table_name="scan_resources")
    op.drop_index("ix_scan_resources_risk", table_name="scan_resources")
    op.drop_index("ix_scan_resources_aws_account_id", table_name="scan_resources")
    op.drop_table("scan_resources")
    op.drop_index("ix_scans_workspace_id", table_name="scans")
    op.drop_index("ix_scans_aws_account_id", table_name="scans")
    op.drop_table("scans")
    op.drop_index("ix_aws_accounts_workspace_id", table_name="aws_accounts")
    op.drop_index("ix_aws_accounts_account_id", table_name="aws_accounts")
    op.drop_table("aws_accounts")
    op.drop_index("ix_workspaces_owner_user_id", table_name="workspaces")
    op.drop_table("workspaces")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

