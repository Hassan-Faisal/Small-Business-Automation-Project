"""add persistent conversation memory fields"""

from alembic import op
import sqlalchemy as sa


revision = "15d2a9ab0b17"
down_revision = "0001a_conversation_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add the columns as nullable first so existing rows do not break.
    with op.batch_alter_table("conversation_state_records") as batch_op:
        batch_op.add_column(
            sa.Column(
                "messages",
                sa.JSON(),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "last_response",
                sa.Text(),
                nullable=True,
            )
        )

    # Populate existing rows with an empty message history.
    op.execute(
        sa.text(
            """
            UPDATE conversation_state_records
            SET messages = '[]'
            WHERE messages IS NULL
            """
        )
    )

    # Make messages required after existing rows have been updated.
    with op.batch_alter_table("conversation_state_records") as batch_op:
        batch_op.alter_column(
            "messages",
            existing_type=sa.JSON(),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("conversation_state_records") as batch_op:
        batch_op.drop_column("last_response")
        batch_op.drop_column("messages")