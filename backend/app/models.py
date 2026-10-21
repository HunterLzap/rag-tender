import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, TimestampMixin, new_id, utcnow


def enum_column(enum_type: type[enum.Enum], name: str):
    return Enum(
        enum_type,
        name=name,
        native_enum=False,
        values_callable=lambda x: [e.value for e in x],
    )


class ProjectStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class BidStatus(str, enum.Enum):
    DRAFT = "draft"
    PREPARING = "preparing"
    SUBMITTED = "submitted"
    CLOSED = "closed"


class DocumentRole(str, enum.Enum):
    TENDER = "tender"
    ADDENDUM = "addendum"
    QA = "qa"
    TEMPLATE = "template"
    EVIDENCE = "evidence"


class ParseStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class AnalysisStatus(str, enum.Enum):
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"
    STALE = "stale"


class RequirementStatus(str, enum.Enum):
    EXTRACTED = "extracted"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    STALE = "stale"


class RequirementReviewStatus(str, enum.Enum):
    UNREVIEWED = "unreviewed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ConditionGroupLogic(str, enum.Enum):
    ALL = "all"
    ANY = "any"


class EvidenceKind(str, enum.Enum):
    QUALIFICATION = "qualification"
    PERSONNEL = "personnel"
    PERFORMANCE = "performance"
    FINANCIAL = "financial"


class EvidenceStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    NEEDS_REVIEW = "needs_review"
    ARCHIVED = "archived"


class EvidenceReviewStatus(str, enum.Enum):
    UNREVIEWED = "unreviewed"
    VERIFIED = "verified"
    REJECTED = "rejected"


class DecisionStatus(str, enum.Enum):
    MET = "met"
    NOT_MET = "not_met"
    NEEDS_REVIEW = "needs_review"
    NOT_APPLICABLE = "not_applicable"


class CheckSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class FillTargetKind(str, enum.Enum):
    TABLE_CELL = "table_cell"
    TEXT_BOX = "text_box"
    CHECKBOX = "checkbox"
    SIGNATURE = "signature"
    DATE = "date"
    UNKNOWN = "unknown"


class FillSlotStatus(str, enum.Enum):
    DETECTED = "detected"
    VERIFIED = "verified"
    IGNORED = "ignored"


class SuggestionStatus(str, enum.Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    EDITED = "edited"
    MISSING_EVIDENCE = "missing_evidence"
    REJECTED = "rejected"


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(300))
    bidder_name: Mapped[str | None] = mapped_column(String(300))
    purchaser: Mapped[str | None] = mapped_column(String(300))
    tender_no: Mapped[str | None] = mapped_column(String(120))
    bid_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str] = mapped_column(String(60), default="Asia/Shanghai")
    status: Mapped[ProjectStatus] = mapped_column(
        enum_column(ProjectStatus, "project_status"), default=ProjectStatus.ACTIVE
    )
    notes: Mapped[str | None] = mapped_column(Text)

    documents: Mapped[list["Document"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    bids: Mapped[list["Bid"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    response_values: Mapped[list["ResponseValue"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    evidence: Mapped[list["EvidenceItem"]] = relationship(back_populates="project")
    runs: Mapped[list["AnalysisRun"]] = relationship(back_populates="project")


class Bid(Base, TimestampMixin):
    __tablename__ = "bids"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    bidder_name: Mapped[str] = mapped_column(String(300))
    lot_code: Mapped[str | None] = mapped_column(String(120))
    bid_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[BidStatus] = mapped_column(
        enum_column(BidStatus, "bid_status"), default=BidStatus.PREPARING
    )
    as_of_date: Mapped[date | None] = mapped_column(Date)

    project: Mapped[Project] = relationship(back_populates="bids")
    response_values: Mapped[list["ResponseValue"]] = relationship(back_populates="bid")
    runs: Mapped[list["AnalysisRun"]] = relationship(back_populates="bid")


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    role: Mapped[DocumentRole] = mapped_column(enum_column(DocumentRole, "document_role"))
    filename: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str | None] = mapped_column(String(200))
    storage_path: Mapped[str] = mapped_column(String(1000))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    file_size: Mapped[int] = mapped_column(Integer)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    supersedes_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    current_revision_id: Mapped[str | None] = mapped_column(String(32))

    project: Mapped[Project] = relationship(back_populates="documents")
    revisions: Mapped[list["DocumentRevision"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentRevision.revision_no",
    )

    __table_args__ = (
        UniqueConstraint("project_id", "sha256", "role", name="uq_document_project_sha_role"),
    )


class DocumentRevision(Base, TimestampMixin):
    __tablename__ = "document_revisions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    revision_no: Mapped[int] = mapped_column(Integer)
    parser_version: Mapped[str] = mapped_column(String(80), default="v2.0")
    parse_status: Mapped[ParseStatus] = mapped_column(
        enum_column(ParseStatus, "document_revision_parse_status"), default=ParseStatus.PENDING
    )
    parse_error: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    document: Mapped[Document] = relationship(back_populates="revisions")
    pages: Mapped[list["Page"]] = relationship(
        back_populates="revision", cascade="all, delete-orphan", order_by="Page.page_index"
    )

    __table_args__ = (UniqueConstraint("document_id", "revision_no", name="uq_revision_no"),)


class Page(Base, TimestampMixin):
    __tablename__ = "pages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    revision_id: Mapped[str] = mapped_column(
        ForeignKey("document_revisions.id", ondelete="CASCADE")
    )
    page_index: Mapped[int] = mapped_column(Integer)
    printed_label: Mapped[str | None] = mapped_column(String(80))
    width: Mapped[float] = mapped_column(Float)
    height: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text, default="")
    render_path: Mapped[str | None] = mapped_column(String(1000))
    parse_mode: Mapped[str] = mapped_column(String(40), default="text")
    quality_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    native_locator: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    document: Mapped[Document] = relationship()
    revision: Mapped[DocumentRevision] = relationship(back_populates="pages")
    blocks: Mapped[list["Block"]] = relationship(
        back_populates="page", cascade="all, delete-orphan", order_by="Block.reading_order"
    )

    __table_args__ = (UniqueConstraint("revision_id", "page_index", name="uq_page_revision_index"),)


class Block(Base, TimestampMixin):
    __tablename__ = "blocks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(40))
    reading_order: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, default="")
    x0: Mapped[float] = mapped_column(Float)
    y0: Mapped[float] = mapped_column(Float)
    x1: Mapped[float] = mapped_column(Float)
    y1: Mapped[float] = mapped_column(Float)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    page: Mapped[Page] = relationship(back_populates="blocks")
    cells: Mapped[list["TableCell"]] = relationship(
        back_populates="block", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_block_page_order", "page_id", "reading_order"),)


class TableCell(Base):
    __tablename__ = "table_cells"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    block_id: Mapped[str] = mapped_column(ForeignKey("blocks.id", ondelete="CASCADE"))
    row_index: Mapped[int] = mapped_column(Integer)
    col_index: Mapped[int] = mapped_column(Integer)
    row_span: Mapped[int] = mapped_column(Integer, default=1)
    col_span: Mapped[int] = mapped_column(Integer, default=1)
    text: Mapped[str] = mapped_column(Text, default="")
    x0: Mapped[float] = mapped_column(Float)
    y0: Mapped[float] = mapped_column(Float)
    x1: Mapped[float] = mapped_column(Float)
    y1: Mapped[float] = mapped_column(Float)
    native_locator: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    block: Mapped[Block] = relationship(back_populates="cells")

    __table_args__ = (UniqueConstraint("block_id", "row_index", "col_index", name="uq_cell_pos"),)


class SourceSpan(Base):
    __tablename__ = "source_spans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    revision_id: Mapped[str] = mapped_column(
        ForeignKey("document_revisions.id", ondelete="CASCADE")
    )
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"))
    block_id: Mapped[str | None] = mapped_column(ForeignKey("blocks.id", ondelete="SET NULL"))
    table_cell_id: Mapped[str | None] = mapped_column(
        ForeignKey("table_cells.id", ondelete="SET NULL")
    )
    char_start: Mapped[int | None] = mapped_column(Integer)
    char_end: Mapped[int | None] = mapped_column(Integer)
    quote: Mapped[str] = mapped_column(Text)
    quote_hash: Mapped[str] = mapped_column(String(64), index=True)
    bbox_json: Mapped[list[float]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_span_document_page", "document_id", "page_id"),)


class AnalysisRun(Base, TimestampMixin):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    bid_id: Mapped[str | None] = mapped_column(ForeignKey("bids.id", ondelete="SET NULL"))
    status: Mapped[AnalysisStatus] = mapped_column(
        enum_column(AnalysisStatus, "analysis_status"), default=AnalysisStatus.DRAFT
    )
    stage: Mapped[str] = mapped_column(String(80), default="created")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    ruleset_version: Mapped[str] = mapped_column(String(80), default="v2.0")
    prompt_version: Mapped[str] = mapped_column(String(80), default="v2.0")
    model_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    input_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    coverage_notes: Mapped[list[str]] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="runs")
    bid: Mapped[Bid | None] = relationship(back_populates="runs")
    requirements: Mapped[list["Requirement"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    decisions: Mapped[list["Decision"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    fill_plans: Mapped[list["FillPlan"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class Requirement(Base, TimestampMixin):
    __tablename__ = "requirements"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(40))
    evaluation_stage: Mapped[str] = mapped_column(String(40), default="qualification")
    evaluation_type: Mapped[str] = mapped_column(String(30), default="binary")
    obligation: Mapped[str] = mapped_column(String(30), default="mandatory")
    consequence: Mapped[str] = mapped_column(String(30), default="rejection")
    handling_mode: Mapped[str] = mapped_column(String(40), default="evidence")
    title: Mapped[str] = mapped_column(String(500))
    statement: Mapped[str] = mapped_column(Text)
    condition_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[RequirementStatus] = mapped_column(
        enum_column(RequirementStatus, "requirement_status"),
        default=RequirementStatus.EXTRACTED,
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    extraction_method: Mapped[str] = mapped_column(String(40), default="llm")
    source_span_id: Mapped[str] = mapped_column(ForeignKey("source_spans.id"))
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    review_status: Mapped[RequirementReviewStatus] = mapped_column(
        enum_column(RequirementReviewStatus, "requirement_review_status"),
        default=RequirementReviewStatus.UNREVIEWED,
    )
    supersedes_id: Mapped[str | None] = mapped_column(ForeignKey("requirements.id"))

    run: Mapped[AnalysisRun] = relationship(back_populates="requirements")
    source_span: Mapped[SourceSpan] = relationship()
    sources: Mapped[list["RequirementSource"]] = relationship(
        back_populates="requirement", cascade="all, delete-orphan"
    )
    decisions: Mapped[list["Decision"]] = relationship(back_populates="requirement")


class RequirementSource(Base):
    __tablename__ = "requirement_sources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    requirement_id: Mapped[str] = mapped_column(
        ForeignKey("requirements.id", ondelete="CASCADE")
    )
    source_span_id: Mapped[str] = mapped_column(
        ForeignKey("source_spans.id", ondelete="CASCADE")
    )
    relation: Mapped[str] = mapped_column(String(40), default="primary")

    requirement: Mapped[Requirement] = relationship(back_populates="sources")
    source_span: Mapped[SourceSpan] = relationship()

    __table_args__ = (
        UniqueConstraint("requirement_id", "source_span_id", name="uq_requirement_source"),
    )


class EvidenceItem(Base, TimestampMixin):
    __tablename__ = "evidence_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"))
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    kind: Mapped[EvidenceKind] = mapped_column(enum_column(EvidenceKind, "evidence_kind"))
    title: Mapped[str] = mapped_column(String(500))
    holder: Mapped[str | None] = mapped_column(String(300))
    issuer: Mapped[str | None] = mapped_column(String(300))
    identifier: Mapped[str | None] = mapped_column(String(200))
    issued_on: Mapped[date | None] = mapped_column(Date)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    status: Mapped[EvidenceStatus] = mapped_column(
        enum_column(EvidenceStatus, "evidence_status"), default=EvidenceStatus.ACTIVE
    )
    review_status: Mapped[EvidenceReviewStatus] = mapped_column(
        enum_column(EvidenceReviewStatus, "evidence_review_status"),
        default=EvidenceReviewStatus.UNREVIEWED,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_span_id: Mapped[str] = mapped_column(ForeignKey("source_spans.id"))
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)

    project: Mapped[Project | None] = relationship(back_populates="evidence")
    organization: Mapped["Organization | None"] = relationship(back_populates="evidence")
    source_span: Mapped[SourceSpan] = relationship()
    facts: Mapped[list["EvidenceFact"]] = relationship(
        back_populates="evidence", cascade="all, delete-orphan"
    )


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(300), unique=True)
    unified_code: Mapped[str | None] = mapped_column(String(80))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    evidence: Mapped[list[EvidenceItem]] = relationship(back_populates="organization")


class EvidenceFact(Base, TimestampMixin):
    __tablename__ = "evidence_facts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence_items.id", ondelete="CASCADE"))
    fact_key: Mapped[str] = mapped_column(String(120))
    value_text: Mapped[str | None] = mapped_column(Text)
    value_number: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    value_date: Mapped[date | None] = mapped_column(Date)
    unit: Mapped[str | None] = mapped_column(String(40))
    currency: Mapped[str | None] = mapped_column(String(10))
    holder: Mapped[str | None] = mapped_column(String(300))
    source_span_id: Mapped[str | None] = mapped_column(ForeignKey("source_spans.id"))
    extraction_method: Mapped[str] = mapped_column(String(40), default="manual")
    review_status: Mapped[EvidenceReviewStatus] = mapped_column(
        enum_column(EvidenceReviewStatus, "evidence_fact_review_status"),
        default=EvidenceReviewStatus.UNREVIEWED,
    )

    evidence: Mapped[EvidenceItem] = relationship(back_populates="facts")
    source_span: Mapped[SourceSpan | None] = relationship()

    __table_args__ = (
        Index("ix_fact_evidence_key", "evidence_id", "fact_key"),
        Index("ix_fact_number", "fact_key", "value_number"),
        Index("ix_fact_date", "fact_key", "value_date"),
    )


class ResponseValue(Base, TimestampMixin):
    __tablename__ = "response_values"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    bid_id: Mapped[str | None] = mapped_column(ForeignKey("bids.id", ondelete="SET NULL"))
    key: Mapped[str] = mapped_column(String(160))
    label: Mapped[str] = mapped_column(String(300))
    value_text: Mapped[str | None] = mapped_column(Text)
    value_number: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    value_date: Mapped[date | None] = mapped_column(Date)
    unit: Mapped[str | None] = mapped_column(String(40))
    currency: Mapped[str | None] = mapped_column(String(10))
    source: Mapped[str] = mapped_column(String(40), default="manual")
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    review_status: Mapped[str] = mapped_column(String(40), default="unreviewed")
    version: Mapped[int] = mapped_column(Integer, default=1)

    project: Mapped[Project] = relationship(back_populates="response_values")
    bid: Mapped[Bid | None] = relationship(back_populates="response_values")

    __table_args__ = (UniqueConstraint("project_id", "key", name="uq_response_project_key"),)


class Decision(Base, TimestampMixin):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"))
    requirement_id: Mapped[str] = mapped_column(ForeignKey("requirements.id", ondelete="CASCADE"))
    status: Mapped[DecisionStatus] = mapped_column(
        enum_column(DecisionStatus, "decision_status"), default=DecisionStatus.NEEDS_REVIEW
    )
    summary: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    rule_trace: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    model_trace: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    condition_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    stale: Mapped[bool] = mapped_column(Boolean, default=False)

    run: Mapped[AnalysisRun] = relationship(back_populates="decisions")
    requirement: Mapped[Requirement] = relationship(back_populates="decisions")
    reviews: Mapped[list["ReviewRecord"]] = relationship(
        back_populates="decision", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("run_id", "requirement_id", name="uq_decision_run_requirement"),
    )


class ReviewRecord(Base, TimestampMixin):
    __tablename__ = "review_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"))
    reviewer: Mapped[str | None] = mapped_column(String(200))
    previous_status: Mapped[str | None] = mapped_column(String(40))
    new_status: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(Text)
    evidence_snapshot: Mapped[list[str]] = mapped_column(JSON, default=list)

    decision: Mapped[Decision] = relationship(back_populates="reviews")


class FillPlan(Base, TimestampMixin):
    __tablename__ = "fill_plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    template_revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_revisions.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(40), default="draft")

    run: Mapped[AnalysisRun] = relationship(back_populates="fill_plans")
    targets: Mapped[list["FillTarget"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )


class FillTarget(Base, TimestampMixin):
    __tablename__ = "fill_targets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    plan_id: Mapped[str] = mapped_column(ForeignKey("fill_plans.id", ondelete="CASCADE"))
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"))
    block_id: Mapped[str | None] = mapped_column(ForeignKey("blocks.id", ondelete="SET NULL"))
    table_cell_id: Mapped[str | None] = mapped_column(
        ForeignKey("table_cells.id", ondelete="SET NULL")
    )
    kind: Mapped[FillTargetKind] = mapped_column(
        enum_column(FillTargetKind, "fill_target_kind"), default=FillTargetKind.UNKNOWN
    )
    label: Mapped[str] = mapped_column(String(300))
    bbox_json: Mapped[list[float]] = mapped_column(JSON)
    requirement_id: Mapped[str | None] = mapped_column(
        ForeignKey("requirements.id", ondelete="SET NULL")
    )
    fill_slot_id: Mapped[str | None] = mapped_column(
        ForeignKey("fill_slots.id", ondelete="SET NULL")
    )

    plan: Mapped[FillPlan] = relationship(back_populates="targets")
    suggestions: Mapped[list["FillSuggestion"]] = relationship(
        back_populates="target", cascade="all, delete-orphan"
    )


class FillSuggestion(Base, TimestampMixin):
    __tablename__ = "fill_suggestions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    target_id: Mapped[str] = mapped_column(ForeignKey("fill_targets.id", ondelete="CASCADE"))
    value: Mapped[str | None] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[SuggestionStatus] = mapped_column(
        enum_column(SuggestionStatus, "suggestion_status"), default=SuggestionStatus.PROPOSED
    )
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    reviewed_by: Mapped[str | None] = mapped_column(String(200))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)

    target: Mapped[FillTarget] = relationship(back_populates="suggestions")


class AnnotationAsset(Base, TimestampMixin):
    __tablename__ = "annotation_assets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    plan_id: Mapped[str] = mapped_column(ForeignKey("fill_plans.id", ondelete="CASCADE"))
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(40), default="page")
    path: Mapped[str] = mapped_column(String(1000))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    annotations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)


class FillSlot(Base, TimestampMixin):
    __tablename__ = "fill_slots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    template_revision_id: Mapped[str] = mapped_column(
        ForeignKey("document_revisions.id", ondelete="CASCADE")
    )
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"))
    block_id: Mapped[str | None] = mapped_column(ForeignKey("blocks.id", ondelete="SET NULL"))
    table_cell_id: Mapped[str | None] = mapped_column(
        ForeignKey("table_cells.id", ondelete="SET NULL")
    )
    kind: Mapped[FillTargetKind] = mapped_column(enum_column(FillTargetKind, "fill_slot_kind"))
    label: Mapped[str] = mapped_column(String(300))
    locator: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    bbox_json: Mapped[list[float]] = mapped_column(JSON)
    value_schema: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[FillSlotStatus] = mapped_column(
        enum_column(FillSlotStatus, "fill_slot_status"), default=FillSlotStatus.DETECTED
    )


class ChecklistItem(Base, TimestampMixin):
    __tablename__ = "checklist_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"))
    requirement_id: Mapped[str | None] = mapped_column(
        ForeignKey("requirements.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(500))
    detail: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[CheckSeverity] = mapped_column(
        enum_column(CheckSeverity, "check_severity"), default=CheckSeverity.WARNING
    )
    completed: Mapped[bool] = mapped_column(Boolean, default=False)


class ParagraphNode(Base, TimestampMixin):
    __tablename__ = "paragraph_nodes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    revision_id: Mapped[str] = mapped_column(
        ForeignKey("document_revisions.id", ondelete="CASCADE")
    )
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("paragraph_nodes.id"))
    level: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str | None] = mapped_column(String(500))
    path: Mapped[str] = mapped_column(String(1000), default="")
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    source_span_id: Mapped[str | None] = mapped_column(ForeignKey("source_spans.id"))
    block_ids: Mapped[list[str]] = mapped_column(JSON, default=list)

    __table_args__ = (Index("ix_paragraph_revision_level", "revision_id", "level"),)


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[JobStatus] = mapped_column(
        enum_column(JobStatus, "job_status"), default=JobStatus.QUEUED
    )
    progress: Mapped[int] = mapped_column(Integer, default=0)
    stage: Mapped[str] = mapped_column(String(300), default="等待处理")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=1)
    dedupe_key: Mapped[str | None] = mapped_column(String(200), index=True)
    lease_owner: Mapped[str | None] = mapped_column(String(120))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_job_claim", "status", "available_at", "lease_until"),)


class ModelCall(Base):
    __tablename__ = "model_calls"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    purpose: Mapped[str] = mapped_column(String(80))
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(200))
    prompt_version: Mapped[str | None] = mapped_column(String(80))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModelConfig(Base, TimestampMixin):
    __tablename__ = "model_configs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    provider: Mapped[str] = mapped_column(String(80), default="openai-compatible")
    base_url: Mapped[str] = mapped_column(String(500))
    api_key_encrypted: Mapped[str] = mapped_column(Text)
    text_model: Mapped[str] = mapped_column(String(200))
    vision_model: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
