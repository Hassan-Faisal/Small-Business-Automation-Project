"""create admin users table

Revision ID: 0003_admin_users
Revises: 0002_tiffin_domain
Create Date: 2026-08-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_admin_users"
down_revision = "0002_tiffin_domain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=30), server_default=sa.text("'owner'"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_admin_users_id", "admin_users", ["id"], unique=False)
    op.create_index("uq_admin_users_email", "admin_users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_admin_users_email", table_name="admin_users")
    op.drop_index("ix_admin_users_id", table_name="admin_users")
    op.drop_table("admin_users")