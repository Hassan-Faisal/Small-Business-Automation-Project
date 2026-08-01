
"""create conversation state records table"""

from alembic import op
import sqlalchemy as sa

revision = "0001a_conversation_state"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_state_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.String(length=100), nullable=False),
        sa.Column("customer_phone", sa.String(length=30), nullable=True),
        sa.Column("cart", sa.JSON(), nullable=False),
        sa.Column("processed_message_ids", sa.JSON(), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("order_number", sa.String(length=50), nullable=True),
        sa.Column("order_status", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index(op.f("ix_conversation_state_records_id"), "conversation_state_records", ["id"], unique=False)
    op.create_index(op.f("ix_conversation_state_records_conversation_id"), "conversation_state_records", ["conversation_id"], unique=True)
    op.create_index(op.f("ix_conversation_state_records_customer_phone"), "conversation_state_records", ["customer_phone"], unique=False)
    op.create_index(op.f("ix_conversation_state_records_order_number"), "conversation_state_records", ["order_number"], unique=False)
    op.create_index(op.f("ix_conversation_state_records_order_status"), "conversation_state_records", ["order_status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_conversation_state_records_order_status"), table_name="conversation_state_records")
    op.drop_index(op.f("ix_conversation_state_records_order_number"), table_name="conversation_state_records")
    op.drop_index(op.f("ix_conversation_state_records_customer_phone"), table_name="conversation_state_records")
    op.drop_index(op.f("ix_conversation_state_records_conversation_id"), table_name="conversation_state_records")
    op.drop_index(op.f("ix_conversation_state_records_id"), table_name="conversation_state_records")
    op.drop_table("conversation_state_records")
