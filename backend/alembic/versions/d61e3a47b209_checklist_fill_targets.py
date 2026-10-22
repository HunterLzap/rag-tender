"""Track fill checklist items by position instead of field label."""

from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision = "d61e3a47b209"
down_revision = "c82a7e4d190f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("checklist_items") as batch:
        batch.add_column(sa.Column("fill_target_id", sa.String(32), nullable=True))
        batch.create_foreign_key(
            "fk_checklist_fill_target", "fill_targets", ["fill_target_id"], ["id"],
            ondelete="SET NULL",
        )
    connection = op.get_bind()
    targets = connection.execute(sa.text(
        "SELECT t.id, p.run_id, t.requirement_id, t.label, d.filename, pg.page_index, "
        "c.row_index, c.col_index, "
        "EXISTS (SELECT 1 FROM fill_suggestions s WHERE s.target_id=t.id "
        "AND s.status IN ('accepted', 'edited', 'rejected')) AND NOT EXISTS "
        "(SELECT 1 FROM fill_suggestions s WHERE s.target_id=t.id "
        "AND s.status NOT IN ('accepted', 'edited', 'rejected')) AS reviewed "
        "FROM fill_targets t JOIN fill_plans p ON p.id=t.plan_id "
        "JOIN documents d ON d.id=p.document_id JOIN pages pg ON pg.id=t.page_id "
        "LEFT JOIN table_cells c ON c.id=t.table_cell_id"
    )).mappings().all()
    connection.execute(sa.text("DELETE FROM checklist_items WHERE title LIKE '确认填写：%'"))
    items = sa.table("checklist_items", *[
        sa.column(name, kind) for name, kind in (
            ("id", sa.String), ("run_id", sa.String), ("requirement_id", sa.String),
            ("fill_target_id", sa.String), ("title", sa.String), ("detail", sa.Text),
            ("severity", sa.String), ("completed", sa.Boolean),
            ("created_at", sa.DateTime), ("updated_at", sa.DateTime),
        )
    ])
    now = datetime.now(UTC)
    if targets:
        connection.execute(items.insert(), [{
            "id": uuid4().hex, "run_id": target["run_id"],
            "requirement_id": target["requirement_id"], "fill_target_id": target["id"],
            "title": f"确认填写：{target['label']}",
            "detail": f"{target['filename']} · 第 {target['page_index'] + 1} 页" + (
                f" · 第 {target['row_index'] + 1} 行第 {target['col_index'] + 1} 列"
                if target["row_index"] is not None else ""
            ),
            "severity": "warning", "completed": bool(target["reviewed"]),
            "created_at": now, "updated_at": now,
        } for target in targets])
    connection.execute(sa.text(
        "UPDATE analysis_runs SET status='needs_review' WHERE status='completed' "
        "AND EXISTS (SELECT 1 FROM checklist_items c "
        "WHERE c.run_id=analysis_runs.id AND c.completed=0)"
    ))


def downgrade() -> None:
    with op.batch_alter_table("checklist_items") as batch:
        batch.drop_constraint("fk_checklist_fill_target", type_="foreignkey")
        batch.drop_column("fill_target_id")
