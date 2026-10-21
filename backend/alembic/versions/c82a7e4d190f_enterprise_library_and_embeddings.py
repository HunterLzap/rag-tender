"""Enterprise document ownership and reusable semantic indexes."""

import sqlalchemy as sa

from alembic import op

revision = "c82a7e4d190f"
down_revision = "a19b2f0e71d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "fill_suggestions",
        sa.Column(
            "source_refs",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
    )
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("organization_id", sa.String(32), nullable=True))
        batch.create_foreign_key(
            "fk_projects_organization", "organizations", ["organization_id"], ["id"]
        )
        batch.add_column(
            sa.Column("auto_analyze", sa.Boolean(), nullable=False, server_default="1")
        )
    with op.batch_alter_table("documents") as batch:
        batch.alter_column("project_id", existing_type=sa.String(32), nullable=True)
        batch.add_column(sa.Column("organization_id", sa.String(32), nullable=True))
        batch.create_foreign_key(
            "fk_documents_organization", "organizations", ["organization_id"], ["id"]
        )
        batch.create_unique_constraint(
            "uq_document_org_sha_role", ["organization_id", "sha256", "role"]
        )
    for name, column_type in (
        ("embedding_model", sa.String(200)),
        ("embedding_base_url", sa.String(500)),
        ("embedding_api_key_encrypted", sa.Text()),
        ("embedding_dimensions", sa.Integer()),
    ):
        op.add_column("model_configs", sa.Column(name, column_type, nullable=True))
    op.create_table(
        "embedding_records",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("model_signature", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("vector", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_embedding_records_model_signature", "embedding_records", ["model_signature"]
    )
    op.create_table(
        "search_chunks",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("document_id", sa.String(32), sa.ForeignKey("documents.id", ondelete="CASCADE")),
        sa.Column(
            "revision_id",
            sa.String(32),
            sa.ForeignKey("document_revisions.id", ondelete="CASCADE"),
        ),
        sa.Column("page_id", sa.String(32), sa.ForeignKey("pages.id", ondelete="CASCADE")),
        sa.Column(
            "source_span_id",
            sa.String(32),
            sa.ForeignKey("source_spans.id", ondelete="CASCADE"),
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("tokens", sa.Text(), nullable=False),
        sa.Column("embedding_id", sa.String(64), sa.ForeignKey("embedding_records.id")),
    )
    op.create_index("ix_search_chunks_document_id", "search_chunks", ["document_id"])
    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS search_chunks_fts "
            "USING fts5(chunk_id UNINDEXED, tokens, tokenize='unicode61')"
        )
        op.execute(
            "CREATE TRIGGER IF NOT EXISTS search_chunks_delete AFTER DELETE ON search_chunks "
            "BEGIN DELETE FROM search_chunks_fts WHERE chunk_id=old.id; END"
        )


def downgrade() -> None:
    op.drop_column("fill_suggestions", "source_refs")
    if op.get_bind().dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS search_chunks_delete")
        op.execute("DROP TABLE IF EXISTS search_chunks_fts")
    op.drop_table("search_chunks")
    op.drop_table("embedding_records")
    for name in (
        "embedding_model",
        "embedding_base_url",
        "embedding_api_key_encrypted",
        "embedding_dimensions",
    ):
        op.drop_column("model_configs", name)
    with op.batch_alter_table("documents") as batch:
        batch.drop_constraint("uq_document_org_sha_role", type_="unique")
        batch.drop_constraint("fk_documents_organization", type_="foreignkey")
        batch.drop_column("organization_id")
    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint("fk_projects_organization", type_="foreignkey")
        batch.drop_column("organization_id")
        batch.drop_column("auto_analyze")
