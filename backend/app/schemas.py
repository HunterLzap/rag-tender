from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    bidder_name: str | None = None
    purchaser: str | None = None
    tender_no: str | None = None
    bid_deadline: datetime | None = None
    timezone: str = "Asia/Shanghai"
    notes: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    bidder_name: str | None = None
    purchaser: str | None = None
    tender_no: str | None = None
    bid_deadline: datetime | None = None
    timezone: str | None = None
    notes: str | None = None
    status: Literal["active", "archived"] | None = None


class ProjectRead(ORMModel):
    id: str
    name: str
    bidder_name: str | None
    purchaser: str | None
    tender_no: str | None
    bid_deadline: datetime | None
    timezone: str
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
    document_count: int = 0
    latest_run_id: str | None = None
    latest_run_status: str | None = None


class BidCreate(BaseModel):
    bidder_name: str = Field(min_length=1, max_length=300)
    lot_code: str | None = None
    bid_deadline: datetime | None = None
    as_of_date: date | None = None


class BidUpdate(BaseModel):
    bidder_name: str | None = None
    lot_code: str | None = None
    bid_deadline: datetime | None = None
    as_of_date: date | None = None
    status: Literal["draft", "preparing", "submitted", "closed"] | None = None


class BidRead(ORMModel):
    id: str
    project_id: str
    bidder_name: str
    lot_code: str | None
    bid_deadline: datetime | None
    status: str
    as_of_date: date | None
    created_at: datetime
    updated_at: datetime


class DocumentRead(ORMModel):
    id: str
    project_id: str
    role: str
    filename: str
    content_type: str | None
    sha256: str
    file_size: int
    page_count: int
    current_revision_id: str | None
    current_page_count: int = 0
    parse_status: str = "pending"
    parse_error: str | None = None
    supersedes_id: str | None
    created_at: datetime


class BBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class PageRead(ORMModel):
    id: str
    document_id: str
    page_index: int
    printed_label: str | None
    width: float
    height: float
    text: str
    parse_mode: str
    quality_flags: list[str]
    native_locator: dict[str, Any]


class SourceSpanRead(ORMModel):
    id: str
    document_id: str
    revision_id: str
    page_id: str
    block_id: str | None
    table_cell_id: str | None
    quote: str
    bbox_json: list[float]
    document_filename: str | None = None
    page_index: int | None = None
    created_at: datetime


class RequirementRead(ORMModel):
    id: str
    run_id: str
    category: str
    evaluation_stage: str
    evaluation_type: str
    obligation: str
    consequence: str
    handling_mode: str
    title: str
    statement: str
    condition_json: dict[str, Any]
    status: str
    confidence: float | None
    extraction_method: str
    review_status: str
    fingerprint: str
    source_span: SourceSpanRead | None = None


class RequirementUpdate(BaseModel):
    title: str | None = None
    statement: str | None = None
    category: str | None = None
    evaluation_stage: str | None = None
    evaluation_type: Literal["binary", "score", "submission", "manual"] | None = None
    obligation: str | None = None
    consequence: str | None = None
    handling_mode: str | None = None
    condition_json: dict[str, Any] | None = None
    status: Literal["extracted", "confirmed", "rejected", "stale"] | None = None
    review_status: Literal["unreviewed", "confirmed", "rejected"] | None = None


class DecisionRead(ORMModel):
    id: str
    run_id: str
    requirement_id: str
    status: str
    summary: str
    confidence: float | None
    rule_trace: list[dict[str, Any]]
    model_trace: dict[str, Any]
    evidence_ids: list[str]
    condition_results: list[dict[str, Any]]
    stale: bool
    created_at: datetime
    updated_at: datetime
    requirement: RequirementRead | None = None
    reviews: list["ReviewRecordRead"] = Field(default_factory=list)


class ReviewCreate(BaseModel):
    new_status: Literal["met", "not_met", "needs_review", "not_applicable"]
    reason: str = Field(min_length=1)
    reviewer: str | None = None


class ReviewRecordRead(ORMModel):
    id: str
    decision_id: str
    reviewer: str | None
    previous_status: str | None
    new_status: str
    reason: str
    evidence_snapshot: list[str]
    created_at: datetime


class EvidenceCreate(BaseModel):
    kind: Literal["qualification", "personnel", "performance", "financial"]
    title: str = Field(min_length=1)
    holder: str | None = None
    issuer: str | None = None
    identifier: str | None = None
    issued_on: date | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    amount: Decimal | None = None
    currency: str | None = "CNY"
    payload: dict[str, Any] = Field(default_factory=dict)
    source_span_id: str | None = None
    facts: list["EvidenceFactCreate"] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.valid_from and self.valid_until and self.valid_from > self.valid_until:
            raise ValueError("valid_from must not be after valid_until")
        return self


class EvidenceUpdate(BaseModel):
    title: str | None = None
    holder: str | None = None
    issuer: str | None = None
    identifier: str | None = None
    issued_on: date | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    status: Literal["active", "expired", "needs_review", "archived"] | None = None
    review_status: Literal["unreviewed", "verified", "rejected"] | None = None
    payload: dict[str, Any] | None = None


class EvidenceRead(ORMModel):
    id: str
    project_id: str
    kind: str
    title: str
    holder: str | None
    issuer: str | None
    identifier: str | None
    issued_on: date | None
    valid_from: date | None
    valid_until: date | None
    status: str
    review_status: str
    payload: dict[str, Any]
    source_span: SourceSpanRead | None = None
    facts: list["EvidenceFactRead"] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AnalysisRunCreate(BaseModel):
    model_config_id: str | None = None
    prompt_version: str = "v2.0"
    ruleset_version: str = "v2.0"


class AnalysisRunRead(ORMModel):
    id: str
    project_id: str
    status: str
    stage: str
    progress: int
    ruleset_version: str
    prompt_version: str
    model_snapshot: dict[str, Any]
    input_snapshot: list[dict[str, Any]]
    coverage_notes: list[str]
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    requirement_count: int = 0
    decision_counts: dict[str, int] = Field(default_factory=dict)
    job_id: str | None = None


class FillTargetRead(ORMModel):
    id: str
    plan_id: str
    page_id: str
    block_id: str | None
    table_cell_id: str | None
    kind: str
    label: str
    bbox_json: list[float]
    requirement_id: str | None
    fill_slot_id: str | None
    suggestions: list["FillSuggestionRead"] = Field(default_factory=list)


class FillSuggestionRead(ORMModel):
    id: str
    target_id: str
    value: str | None
    rationale: str
    confidence: float | None
    status: str
    evidence_ids: list[str]
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_note: str | None


class FillSuggestionUpdate(BaseModel):
    value: str | None = None
    status: Literal[
        "proposed", "accepted", "edited", "missing_evidence", "rejected"
    ] | None = None
    review_note: str | None = None
    reviewed_by: str | None = None


class FillPlanRead(ORMModel):
    id: str
    run_id: str
    document_id: str
    status: str
    created_at: datetime
    targets: list[FillTargetRead] = Field(default_factory=list)
    assets: list["AnnotationAssetRead"] = Field(default_factory=list)


class FillPlanRebuild(BaseModel):
    template_document_id: str | None = None


class FillSlotRead(ORMModel):
    id: str
    template_revision_id: str
    page_id: str
    block_id: str | None
    table_cell_id: str | None
    kind: str
    label: str
    locator: dict[str, Any]
    bbox_json: list[float]
    value_schema: dict[str, Any]
    status: str


class FillTargetCreate(BaseModel):
    page_id: str
    block_id: str | None = None
    table_cell_id: str | None = None
    kind: Literal["table_cell", "text_box", "checkbox", "signature", "date", "unknown"] = "text_box"
    label: str
    bbox: list[float] = Field(min_length=4, max_length=4)
    requirement_id: str | None = None


class FillSuggestionCreate(BaseModel):
    value: str | None = None
    rationale: str = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    status: Literal[
        "proposed", "accepted", "edited", "missing_evidence", "rejected"
    ] = "proposed"
    evidence_ids: list[str] = Field(default_factory=list)


class AnnotationAssetRead(ORMModel):
    id: str
    plan_id: str
    page_id: str
    kind: str
    path: str
    width: int
    height: int
    annotations: list[dict[str, Any]]
    created_at: datetime


class ChecklistRead(ORMModel):
    id: str
    run_id: str
    requirement_id: str | None
    title: str
    detail: str | None
    severity: str
    completed: bool


class ChecklistUpdate(BaseModel):
    completed: bool


class EvidenceFactCreate(BaseModel):
    fact_key: str = Field(min_length=1, max_length=120)
    value_text: str | None = None
    value_number: Decimal | None = None
    value_date: date | None = None
    unit: str | None = None
    currency: str | None = None
    holder: str | None = None
    source_span_id: str | None = None
    extraction_method: str = "manual"
    review_status: Literal["unreviewed", "verified", "rejected"] = "unreviewed"


class EvidenceFactRead(ORMModel):
    id: str
    evidence_id: str
    fact_key: str
    value_text: str | None
    value_number: Decimal | None
    value_date: date | None
    unit: str | None
    currency: str | None
    holder: str | None
    source_span_id: str | None
    extraction_method: str
    review_status: str


class ResponseValueCreate(BaseModel):
    key: str = Field(min_length=1, max_length=160)
    label: str = Field(min_length=1, max_length=300)
    value_text: str | None = None
    value_number: Decimal | None = None
    value_date: date | None = None
    unit: str | None = None
    currency: str | None = "CNY"
    source: str = "manual"
    evidence_ids: list[str] = Field(default_factory=list)
    review_status: Literal["unreviewed", "verified", "rejected"] = "unreviewed"
    bid_id: str | None = None


class ResponseValueUpdate(BaseModel):
    key: str | None = Field(default=None, min_length=1, max_length=160)
    label: str | None = Field(default=None, min_length=1, max_length=300)
    value_text: str | None = None
    value_number: Decimal | None = None
    value_date: date | None = None
    unit: str | None = None
    currency: str | None = None
    source: str | None = None
    evidence_ids: list[str] | None = None
    review_status: Literal["unreviewed", "verified", "rejected"] | None = None
    bid_id: str | None = None


class ResponseValueRead(ORMModel):
    id: str
    project_id: str
    bid_id: str | None
    key: str
    label: str
    value_text: str | None
    value_number: Decimal | None
    value_date: date | None
    unit: str | None
    currency: str | None
    source: str
    evidence_ids: list[str]
    review_status: str
    version: int
    created_at: datetime
    updated_at: datetime


class JobRead(ORMModel):
    id: str
    kind: str
    payload: dict[str, Any]
    status: str
    progress: int
    stage: str
    attempts: int
    max_attempts: int
    result: dict[str, Any]
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class JobAccepted(BaseModel):
    job_id: str
    status: str


class ModelConfigCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider: str = "openai-compatible"
    base_url: str
    api_key: str = Field(min_length=1, repr=False)
    text_model: str
    vision_model: str | None = None
    is_active: bool = True
    config_json: dict[str, Any] = Field(default_factory=dict)


class ModelConfigRead(ORMModel):
    id: str
    name: str
    provider: str
    base_url: str
    api_key_masked: str
    text_model: str
    vision_model: str | None
    is_active: bool
    config_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ModelTestRequest(BaseModel):
    base_url: str | None = None
    api_key: str | None = Field(default=None, repr=False)
    config_id: str | None = None
    model: str
    vision_model: str | None = None


class ModelTestResult(BaseModel):
    success: bool
    latency_ms: int
    message: str


class ReportRead(BaseModel):
    run_id: str
    generated_at: datetime
    markdown: str
    summary: dict[str, int]


class PageDetail(PageRead):
    blocks: list["BlockRead"] = Field(default_factory=list)


class BlockRead(ORMModel):
    id: str
    page_id: str
    kind: str
    reading_order: int
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    metadata_json: dict[str, Any]
    cells: list["TableCellRead"] = Field(default_factory=list)


class TableCellRead(ORMModel):
    id: str
    block_id: str
    row_index: int
    col_index: int
    row_span: int
    col_span: int
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    native_locator: dict[str, Any]


DecisionRead.model_rebuild()
FillTargetRead.model_rebuild()
FillPlanRead.model_rebuild()
EvidenceCreate.model_rebuild()
EvidenceRead.model_rebuild()
PageDetail.model_rebuild()
BlockRead.model_rebuild()
