"""add admin order operational fields

Revision ID: 0004_admin_order_ops
Revises: 0003_admin_users
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_admin_order_ops"
down_revision = "0003_admin_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("internal_note", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("estimated_delivery_minutes", sa.Integer(), nullable=True))
    op.add_column("orders", sa.Column("delivery_provider", sa.String(length=30), nullable=True))
    op.add_column("orders", sa.Column("rider_note", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for column in ("cancelled_at", "completed_at", "confirmed_at", "rider_note", "delivery_provider", "estimated_delivery_minutes", "internal_note"):
        op.drop_column("orders", column)

