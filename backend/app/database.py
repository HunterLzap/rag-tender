"""SQLite 数据库初始化与连接管理。

使用 aiosqlite 异步访问 SQLite，启用外键约束。
所有 7 张表的 DDL 在此定义，应用启动时一次性创建。
"""

import aiosqlite

from app.config import DB_PATH, ensure_directories
from app.utils.crypto import encrypt_secret, is_encrypted_secret

# ---------------------------------------------------------------------------
# DDL 建表语句
# ---------------------------------------------------------------------------

_CREATE_TENDERS = """
CREATE TABLE IF NOT EXISTS tenders (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    filename         TEXT    NOT NULL,
    original_path    TEXT    NOT NULL,
    pdf_path         TEXT,
    title            TEXT,
    file_type        TEXT,
    status           TEXT    NOT NULL DEFAULT 'pending',
    total_pages      INTEGER DEFAULT 0,
    region           TEXT,
    procurement_type TEXT,
    budget           TEXT,
    agency           TEXT,
    upload_time      TEXT,
    parsed_at        TEXT,
    created_at       TEXT    NOT NULL
);
"""

_CREATE_TENDER_REQUIREMENTS = """
CREATE TABLE IF NOT EXISTS tender_requirements (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id        INTEGER NOT NULL,
    category         TEXT    NOT NULL,
    title            TEXT,
    content          TEXT,
    is_hard          INTEGER DEFAULT 1,
    raw_text         TEXT,
    page_number      INTEGER,
    numeric_value    TEXT,
    numeric_operator TEXT,
    numeric_unit     TEXT,
    review_status    TEXT    NOT NULL DEFAULT 'pending',
    created_at       TEXT    NOT NULL,
    FOREIGN KEY (tender_id) REFERENCES tenders(id) ON DELETE CASCADE
);
"""

_CREATE_KNOWLEDGE_FILES = """
CREATE TABLE IF NOT EXISTS knowledge_files (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT    NOT NULL,
    file_path   TEXT    NOT NULL,
    file_type   TEXT,
    category    TEXT,
    status      TEXT    NOT NULL DEFAULT 'pending',
    upload_time TEXT,
    parsed_at   TEXT,
    extracted_text TEXT,
    extracted_at   TEXT,
    created_at  TEXT    NOT NULL
);
"""

_CREATE_QUALIFICATIONS = """
CREATE TABLE IF NOT EXISTS qualifications (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id            INTEGER,
    name               TEXT,
    number             TEXT,
    issue_date         TEXT,
    expiry_date        TEXT,
    issuing_authority  TEXT,
    scope              TEXT,
    level              TEXT,
    holder             TEXT,
    category           TEXT,
    status             TEXT,
    raw_text           TEXT,
    created_at         TEXT    NOT NULL,
    FOREIGN KEY (file_id) REFERENCES knowledge_files(id) ON DELETE SET NULL
);
"""

_CREATE_MATCH_RESULTS = """
CREATE TABLE IF NOT EXISTS match_results (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id             INTEGER NOT NULL,
    requirement_id        INTEGER NOT NULL,
    qualification_id      INTEGER,
    status                TEXT    NOT NULL DEFAULT 'needs_review',
    reason                TEXT,
    mismatch_detail       TEXT,
    expected_qualification TEXT,
    in_knowledge_base     INTEGER DEFAULT 0,
    similarity_score      REAL,
    evidence_items        TEXT,
    confirmed_status      TEXT,
    created_at            TEXT    NOT NULL,
    FOREIGN KEY (tender_id) REFERENCES tenders(id) ON DELETE CASCADE,
    FOREIGN KEY (requirement_id) REFERENCES tender_requirements(id) ON DELETE CASCADE,
    FOREIGN KEY (qualification_id) REFERENCES qualifications(id) ON DELETE SET NULL
);
"""

_CREATE_MATCH_CORRECTIONS = """
CREATE TABLE IF NOT EXISTS match_corrections (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id           INTEGER,
    tender_id          INTEGER NOT NULL,
    requirement_id     INTEGER NOT NULL,
    qualification_id   INTEGER,
    previous_status    TEXT,
    confirmed_status   TEXT NOT NULL,
    correction_reason  TEXT,
    evidence_snapshot  TEXT,
    created_at         TEXT NOT NULL
);
"""

_CREATE_RULE_OVERRIDES = """
CREATE TABLE IF NOT EXISTS rule_overrides (
    rule_id     TEXT PRIMARY KEY,
    enabled     INTEGER NOT NULL DEFAULT 1,
    updated_at  TEXT NOT NULL
);
"""

_CREATE_RULE_CHANGE_LOGS = """
CREATE TABLE IF NOT EXISTS rule_change_logs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id           TEXT NOT NULL,
    previous_enabled  INTEGER NOT NULL,
    new_enabled       INTEGER NOT NULL,
    reason            TEXT,
    created_at        TEXT NOT NULL
);
"""

_CREATE_RULE_SUGGESTION_REVIEWS = """
CREATE TABLE IF NOT EXISTS rule_suggestion_reviews (
    suggestion_id   TEXT PRIMARY KEY,
    review_status   TEXT NOT NULL DEFAULT 'pending',
    review_reason   TEXT,
    updated_at      TEXT NOT NULL
);
"""

_CREATE_RULE_DRAFTS = """
CREATE TABLE IF NOT EXISTS rule_drafts (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    source_suggestion_id  TEXT NOT NULL UNIQUE,
    name                  TEXT NOT NULL,
    rule_type             TEXT NOT NULL,
    draft_content         TEXT NOT NULL,
    draft_status          TEXT NOT NULL DEFAULT 'pending_review',
    review_reason         TEXT,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL
);
"""

_CREATE_CUSTOM_RULES = """
CREATE TABLE IF NOT EXISTS custom_rules (
    id              TEXT PRIMARY KEY,
    source_draft_id INTEGER NOT NULL,
    name            TEXT NOT NULL,
    rule_type       TEXT NOT NULL,
    description     TEXT NOT NULL,
    enabled         INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
"""

_CREATE_RULE_VERSIONS = """
CREATE TABLE IF NOT EXISTS rule_versions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id         TEXT NOT NULL,
    version_no      INTEGER NOT NULL,
    name            TEXT NOT NULL,
    rule_type       TEXT NOT NULL,
    description     TEXT NOT NULL,
    edit_reason     TEXT,
    created_at      TEXT NOT NULL
);
"""

_CREATE_RULE_RELATIONS = """
CREATE TABLE IF NOT EXISTS rule_relations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_rule_id  TEXT NOT NULL,
    target_rule_id  TEXT NOT NULL,
    relation_type   TEXT NOT NULL,
    reason          TEXT,
    created_at      TEXT NOT NULL
);
"""

_CREATE_API_CONFIGS = """
CREATE TABLE IF NOT EXISTS api_configs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    config_type  TEXT    NOT NULL,
    provider     TEXT,
    base_url     TEXT,
    api_key      TEXT,
    model_name   TEXT,
    is_active    INTEGER DEFAULT 1,
    created_at   TEXT    NOT NULL,
    updated_at   TEXT    NOT NULL
);
"""

_CREATE_LLM_CALL_LOGS = """
CREATE TABLE IF NOT EXISTS llm_call_logs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type           TEXT    NOT NULL,
    config_type         TEXT    NOT NULL,
    provider            TEXT,
    model_name          TEXT,
    base_url            TEXT,
    success             INTEGER NOT NULL DEFAULT 0,
    duration_ms         INTEGER NOT NULL DEFAULT 0,
    prompt_chars        INTEGER DEFAULT 0,
    response_chars      INTEGER DEFAULT 0,
    error_message       TEXT,
    api_key_fingerprint TEXT,
    created_at          TEXT    NOT NULL
);
"""

_CREATE_FILL_TEMPLATES = """
CREATE TABLE IF NOT EXISTS fill_templates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id       INTEGER NOT NULL,
    filename        TEXT,
    file_path       TEXT,
    file_type       TEXT,
    filled_path     TEXT,
    output_pdf_path TEXT,
    status          TEXT    NOT NULL DEFAULT 'pending',
    created_at      TEXT    NOT NULL,
    FOREIGN KEY (tender_id) REFERENCES tenders(id) ON DELETE CASCADE
);
"""

_CREATE_TECHNICAL_RESPONSES = """
CREATE TABLE IF NOT EXISTS technical_responses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id       INTEGER NOT NULL,
    requirement_id  INTEGER NOT NULL,
    spec_name       TEXT,
    required_value  TEXT,
    actual_value    TEXT,
    response_status TEXT    DEFAULT 'pending',
    is_hard         INTEGER DEFAULT 1,
    remark          TEXT,
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL,
    FOREIGN KEY (tender_id) REFERENCES tenders(id) ON DELETE CASCADE,
    FOREIGN KEY (requirement_id) REFERENCES tender_requirements(id) ON DELETE CASCADE
);
"""

_CREATE_SUBMISSION_CHECKLIST = """
CREATE TABLE IF NOT EXISTS submission_checklist (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id       INTEGER NOT NULL,
    requirement_id  INTEGER,
    item_name       TEXT    NOT NULL,
    description     TEXT,
    status          TEXT    NOT NULL DEFAULT 'not_started',
    remark          TEXT,
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL,
    FOREIGN KEY (tender_id) REFERENCES tenders(id) ON DELETE CASCADE,
    FOREIGN KEY (requirement_id) REFERENCES tender_requirements(id) ON DELETE SET NULL
);
"""

_CREATE_PERFORMANCE_PROJECTS = """
CREATE TABLE IF NOT EXISTS performance_projects (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name    TEXT    NOT NULL,
    client_name     TEXT,
    contract_no     TEXT,
    contract_amount TEXT,
    sign_date       TEXT,
    completion_date TEXT,
    project_scope   TEXT,
    year            TEXT,
    file_ids        TEXT,
    remark          TEXT,
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL
);
"""

# 索引
_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_tender_req_tender ON tender_requirements(tender_id);",
    "CREATE INDEX IF NOT EXISTS idx_qual_file ON qualifications(file_id);",
    "CREATE INDEX IF NOT EXISTS idx_match_tender ON match_results(tender_id);",
    "CREATE INDEX IF NOT EXISTS idx_match_req ON match_results(requirement_id);",
    "CREATE INDEX IF NOT EXISTS idx_match_correction_tender ON match_corrections(tender_id);",
    "CREATE INDEX IF NOT EXISTS idx_match_correction_req ON match_corrections(requirement_id);",
    "CREATE INDEX IF NOT EXISTS idx_rule_change_logs_rule ON rule_change_logs(rule_id);",
    "CREATE INDEX IF NOT EXISTS idx_rule_suggestion_reviews_status ON rule_suggestion_reviews(review_status);",
    "CREATE INDEX IF NOT EXISTS idx_rule_drafts_status ON rule_drafts(draft_status);",
    "CREATE INDEX IF NOT EXISTS idx_custom_rules_enabled ON custom_rules(enabled);",
    "CREATE INDEX IF NOT EXISTS idx_rule_versions_rule ON rule_versions(rule_id, version_no);",
    "CREATE INDEX IF NOT EXISTS idx_rule_relations_source ON rule_relations(source_rule_id);",
    "CREATE INDEX IF NOT EXISTS idx_rule_relations_target ON rule_relations(target_rule_id);",
    "CREATE INDEX IF NOT EXISTS idx_api_config_type ON api_configs(config_type, is_active);",
    "CREATE INDEX IF NOT EXISTS idx_llm_call_logs_task ON llm_call_logs(task_type, created_at);",
    "CREATE INDEX IF NOT EXISTS idx_fill_tender ON fill_templates(tender_id);",
    "CREATE INDEX IF NOT EXISTS idx_tech_resp_tender ON technical_responses(tender_id);",
    "CREATE INDEX IF NOT EXISTS idx_tech_resp_req ON technical_responses(requirement_id);",
    "CREATE INDEX IF NOT EXISTS idx_checklist_tender ON submission_checklist(tender_id);",
    "CREATE INDEX IF NOT EXISTS idx_perf_project_year ON performance_projects(year);",
]

# 所有 DDL 按顺序执行
_ALL_DDL: list[str] = [
    _CREATE_TENDERS,
    _CREATE_TENDER_REQUIREMENTS,
    _CREATE_KNOWLEDGE_FILES,
    _CREATE_QUALIFICATIONS,
    _CREATE_MATCH_RESULTS,
    _CREATE_MATCH_CORRECTIONS,
    _CREATE_RULE_OVERRIDES,
    _CREATE_RULE_CHANGE_LOGS,
    _CREATE_RULE_SUGGESTION_REVIEWS,
    _CREATE_RULE_DRAFTS,
    _CREATE_CUSTOM_RULES,
    _CREATE_RULE_VERSIONS,
    _CREATE_RULE_RELATIONS,
    _CREATE_API_CONFIGS,
    _CREATE_LLM_CALL_LOGS,
    _CREATE_FILL_TEMPLATES,
    _CREATE_TECHNICAL_RESPONSES,
    _CREATE_SUBMISSION_CHECKLIST,
    _CREATE_PERFORMANCE_PROJECTS,
] + _CREATE_INDEXES


async def init_db() -> None:
    """初始化数据库：创建目录、打开连接、执行所有 DDL。

    此函数在应用启动时调用，幂等操作（IF NOT EXISTS）。
    同时执行 ALTER TABLE 迁移，为旧表添加缺失的列。
    """
    ensure_directories()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON;")
        for ddl in _ALL_DDL:
            await db.execute(ddl)
        await db.commit()

        # 为已有 tenders 表添加缺失的列（幂等迁移）
        _MIGRATIONS = [
            "ALTER TABLE tenders ADD COLUMN region TEXT",
            "ALTER TABLE tenders ADD COLUMN procurement_type TEXT",
            "ALTER TABLE tenders ADD COLUMN budget TEXT",
            "ALTER TABLE tenders ADD COLUMN agency TEXT",
            "ALTER TABLE tender_requirements ADD COLUMN review_status TEXT NOT NULL DEFAULT 'pending'",
            "ALTER TABLE tender_requirements ADD COLUMN requirement_nature TEXT NOT NULL DEFAULT 'capability'",
            "ALTER TABLE technical_responses ADD COLUMN response_status TEXT DEFAULT 'pending'",
            "ALTER TABLE knowledge_files ADD COLUMN extracted_text TEXT",
            "ALTER TABLE knowledge_files ADD COLUMN extracted_at TEXT",
            "ALTER TABLE match_results ADD COLUMN evidence_items TEXT",
            "ALTER TABLE rule_drafts ADD COLUMN review_reason TEXT",
        ]
        for ddl in _MIGRATIONS:
            try:
                await db.execute(ddl)
            except Exception:
                pass  # 列已存在，忽略
        await db.commit()

        await _migrate_api_keys_to_encrypted(db)
        await db.commit()


async def _migrate_api_keys_to_encrypted(db: aiosqlite.Connection) -> None:
    """Encrypt legacy plaintext API keys in ``api_configs``.

    This keeps old local databases usable after enabling encryption. If legacy
    plaintext keys exist and the master key is missing, startup fails with a
    clear setup error instead of silently continuing to store secrets in plain
    text.
    """
    cursor = await db.execute("SELECT id, api_key FROM api_configs")
    rows = await cursor.fetchall()
    for row in rows:
        raw_key = row["api_key"]
        if not raw_key or is_encrypted_secret(raw_key) or raw_key.startswith("****"):
            continue
        encrypted_key = encrypt_secret(raw_key)
        await db.execute(
            "UPDATE api_configs SET api_key = ? WHERE id = ?",
            (encrypted_key, row["id"]),
        )


async def get_db() -> aiosqlite.Connection:
    """获取一个异步数据库连接。

    调用方负责在使用后关闭连接（推荐使用 ``async with``）。

    Returns:
        aiosqlite.Connection: 已开启外键约束的数据库连接。
    """
    db = await aiosqlite.connect(DB_PATH)
    await db.execute("PRAGMA foreign_keys = ON;")
    db.row_factory = aiosqlite.Row
    return db
