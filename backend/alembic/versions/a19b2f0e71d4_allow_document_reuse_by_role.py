"""allow a document to be reused under different roles

Revision ID: a19b2f0e71d4
Revises: fcb21467dc21
Create Date: 2026-10-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a19b2f0e71d4"
down_revision: str | Sequence[str] | None = "fcb21467dc21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.drop_constraint("uq_document_project_sha", type_="unique")
        batch.create_unique_constraint(
            "uq_document_project_sha_role", ["project_id", "sha256", "role"]
        )
    op.add_column(
        "fill_suggestions", sa.Column("reviewed_by", sa.String(length=200), nullable=True)
    )
    op.add_column(
        "fill_suggestions",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("fill_suggestions", sa.Column("review_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("fill_suggestions", "review_note")
    op.drop_column("fill_suggestions", "reviewed_at")
    op.drop_column("fill_suggestions", "reviewed_by")
    with op.batch_alter_table("documents") as batch:
        batch.drop_constraint("uq_document_project_sha_role", type_="unique")
        batch.create_unique_constraint(
            "uq_document_project_sha", ["project_id", "sha256"]
        )
