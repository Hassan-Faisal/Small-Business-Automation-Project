"""tiffin domain tables and order extensions

Revision ID: 0002_tiffin_domain
Revises: 15d2a9ab0b17
Create Date: 2026-07-22 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_tiffin_domain"
down_revision = "15d2a9ab0b17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meal_offerings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("meal_type", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("day_of_week", sa.String(length=20), nullable=False),
        sa.Column("availability", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.UniqueConstraint("day_of_week", "meal_type", "name", name="uq_meal_offerings_day_type_name"),
    )
    op.create_index(op.f("ix_meal_offerings_id"), "meal_offerings", ["id"], unique=False)
    op.create_index(op.f("ix_meal_offerings_name"), "meal_offerings", ["name"], unique=False)
    op.create_index(op.f("ix_meal_offerings_meal_type"), "meal_offerings", ["meal_type"], unique=False)
    op.create_index(op.f("ix_meal_offerings_day_of_week"), "meal_offerings", ["day_of_week"], unique=False)

    op.create_table(
        "subscription_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("duration_type", sa.String(length=20), nullable=False),
        sa.Column("number_of_days", sa.Integer(), nullable=False),
        sa.Column("included_meal_types", sa.JSON(), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
    )
    op.create_index(op.f("ix_subscription_plans_id"), "subscription_plans", ["id"], unique=False)
    op.create_index(op.f("ix_subscription_plans_name"), "subscription_plans", ["name"], unique=True)
    op.create_index(op.f("ix_subscription_plans_duration_type"), "subscription_plans", ["duration_type"], unique=False)

    op.create_table(
        "customer_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_phone", sa.String(length=30), nullable=False),
        sa.Column("subscription_plan_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("delivery_address", sa.String(length=500), nullable=True),
        sa.Column("preferred_meal_choices", sa.JSON(), nullable=False),
        sa.Column("payment_method", sa.String(length=30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["subscription_plan_id"], ["subscription_plans.id"]),
    )
    op.create_index(op.f("ix_customer_subscriptions_id"), "customer_subscriptions", ["id"], unique=False)
    op.create_index(op.f("ix_customer_subscriptions_customer_phone"), "customer_subscriptions", ["customer_phone"], unique=False)
    op.create_index(op.f("ix_customer_subscriptions_subscription_plan_id"), "customer_subscriptions", ["subscription_plan_id"], unique=False)
    op.create_index(op.f("ix_customer_subscriptions_start_date"), "customer_subscriptions", ["start_date"], unique=False)
    op.create_index(op.f("ix_customer_subscriptions_end_date"), "customer_subscriptions", ["end_date"], unique=False)
    op.create_index(op.f("ix_customer_subscriptions_status"), "customer_subscriptions", ["status"], unique=False)

    op.create_table(
        "meal_skips",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("meal_date", sa.Date(), nullable=False),
        sa.Column("meal_type", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.ForeignKeyConstraint(["subscription_id"], ["customer_subscriptions.id"]),
    )
    op.create_index(op.f("ix_meal_skips_id"), "meal_skips", ["id"], unique=False)
    op.create_index(op.f("ix_meal_skips_subscription_id"), "meal_skips", ["subscription_id"], unique=False)
    op.create_index(op.f("ix_meal_skips_meal_date"), "meal_skips", ["meal_date"], unique=False)
    op.create_index(op.f("ix_meal_skips_meal_type"), "meal_skips", ["meal_type"], unique=False)
    op.create_index(op.f("ix_meal_skips_status"), "meal_skips", ["status"], unique=False)

    op.add_column("orders", sa.Column("payment_method", sa.String(length=30), nullable=True))
    op.add_column("orders", sa.Column("is_bulk_order", sa.Boolean(), server_default=sa.text("0"), nullable=False))
    op.add_column("orders", sa.Column("requested_delivery_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("number_of_boxes", sa.Integer(), nullable=True))
    op.add_column("orders", sa.Column("special_instructions", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "special_instructions")
    op.drop_column("orders", "number_of_boxes")
    op.drop_column("orders", "requested_delivery_at")
    op.drop_column("orders", "is_bulk_order")
    op.drop_column("orders", "payment_method")

    op.drop_index(op.f("ix_meal_skips_status"), table_name="meal_skips")
    op.drop_index(op.f("ix_meal_skips_meal_type"), table_name="meal_skips")
    op.drop_index(op.f("ix_meal_skips_meal_date"), table_name="meal_skips")
    op.drop_index(op.f("ix_meal_skips_subscription_id"), table_name="meal_skips")
    op.drop_index(op.f("ix_meal_skips_id"), table_name="meal_skips")
    op.drop_table("meal_skips")

    op.drop_index(op.f("ix_customer_subscriptions_status"), table_name="customer_subscriptions")
    op.drop_index(op.f("ix_customer_subscriptions_end_date"), table_name="customer_subscriptions")
    op.drop_index(op.f("ix_customer_subscriptions_start_date"), table_name="customer_subscriptions")
    op.drop_index(op.f("ix_customer_subscriptions_subscription_plan_id"), table_name="customer_subscriptions")
    op.drop_index(op.f("ix_customer_subscriptions_customer_phone"), table_name="customer_subscriptions")
    op.drop_index(op.f("ix_customer_subscriptions_id"), table_name="customer_subscriptions")
    op.drop_table("customer_subscriptions")

    op.drop_index(op.f("ix_subscription_plans_duration_type"), table_name="subscription_plans")
    op.drop_index(op.f("ix_subscription_plans_name"), table_name="subscription_plans")
    op.drop_index(op.f("ix_subscription_plans_id"), table_name="subscription_plans")
    op.drop_table("subscription_plans")

    op.drop_index(op.f("ix_meal_offerings_day_of_week"), table_name="meal_offerings")
    op.drop_index(op.f("ix_meal_offerings_meal_type"), table_name="meal_offerings")
    op.drop_index(op.f("ix_meal_offerings_name"), table_name="meal_offerings")
    op.drop_index(op.f("ix_meal_offerings_id"), table_name="meal_offerings")
    op.drop_table("meal_offerings")
