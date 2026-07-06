/**
 * Global TypeScript type definitions.
 * Corresponds to backend Pydantic schemas (see ARCHITECTURE.md section 3).
 */

/** Unified API response format: { code, data, message } */
export interface ApiResponse<T = unknown> {
  code: number;
  data: T;
  message: string;
}

// ---------------------------------------------------------------------------
// Tender
// ---------------------------------------------------------------------------

export type TenderStatus = 'pending' | 'converting' | 'parsing' | 'extracting' | 'retrying_vlm' | 'completed' | 'failed';

export interface Tender {
  id: number;
  filename: string;
  title: string | null;
  file_type: string | null;
  status: TenderStatus;
  total_pages: number;
  region: string | null;
  procurement_type: string | null;
  budget: string | null;
  agency: string | null;
  upload_time: string | null;
  parsed_at: string | null;
}

export type RequirementCategory = 'qualification' | 'performance' | 'financial' | 'personnel' | 'other' | 'product_spec' | 'submission';
export type RequirementNature = 'capability' | 'submission';
export type RequirementReviewStatus = 'pending' | 'confirmed';

export interface TenderRequirement {
  id: number;
  tender_id: number;
  category: RequirementCategory;
  requirement_nature: RequirementNature;
  title: string;
  content: string;
  is_hard: boolean;
  raw_text: string;
  page_number: number | null;
  numeric_value: string | null;
  numeric_operator: string | null;
  numeric_unit: string | null;
  review_status: RequirementReviewStatus;
}

export interface TenderRequirementInput {
  category?: RequirementCategory;
  requirement_nature?: RequirementNature;
  title?: string;
  content?: string;
  is_hard?: boolean;
  raw_text?: string;
  page_number?: number | null;
  numeric_value?: string | null;
  numeric_operator?: string | null;
  numeric_unit?: string | null;
  review_status?: RequirementReviewStatus;
}

export interface TenderStatusResponse {
  status: TenderStatus;
  progress?: number;
  stage?: string;
  total_pages?: number;
  parsed_pages?: number;
  attempt?: number;
}

// ---------------------------------------------------------------------------
// Knowledge
// ---------------------------------------------------------------------------

export type KnowledgeCategory = 'enterprise' | 'personnel' | 'performance' | 'financial';

export type ParseStatus = 'pending' | 'parsing' | 'completed' | 'failed';

export interface KnowledgeFile {
  id: number;
  filename: string;
  file_type: string;
  category: KnowledgeCategory | 'other';
  file_path: string;
  status: ParseStatus;
  upload_time: string;
  parsed_at: string | null;
  created_at: string;
}

export type QualificationStatus = 'valid' | 'expiring' | 'expired' | 'needs_completion';

export interface Qualification {
  id: number;
  file_id: number | null;
  name: string;
  number: string;
  issue_date: string | null;
  expiry_date: string | null;
  issuing_authority: string;
  scope: string;
  level: string;
  holder: string;
  category: KnowledgeCategory | 'other';
  status: QualificationStatus;
  raw_text: string | null;
  created_at: string;
}

export interface QualificationInput {
  name: string;
  number: string;
  issue_date: string | null;
  expiry_date: string | null;
  issuing_authority: string;
  scope: string;
  level: string;
  holder: string;
  category: KnowledgeCategory | 'other';
}

export interface PerformanceProject {
  id: number;
  project_name: string;
  client_name: string | null;
  contract_no: string | null;
  contract_amount: string | null;
  sign_date: string | null;
  completion_date: string | null;
  project_scope: string | null;
  year: string | null;
  file_ids: number[];
  remark: string | null;
  created_at: string;
  updated_at: string;
}

export interface PerformanceProjectInput {
  project_name: string;
  client_name?: string | null;
  contract_no?: string | null;
  contract_amount?: string | null;
  sign_date?: string | null;
  completion_date?: string | null;
  project_scope?: string | null;
  year?: string | null;
  file_ids?: number[];
  remark?: string | null;
}

// ---------------------------------------------------------------------------
// Match
// ---------------------------------------------------------------------------

export type MatchStatus = 'matched' | 'unmatched' | 'needs_review';

export type MatchEvidenceStatus = 'pass' | 'fail' | 'unknown';

export interface MatchEvidenceItem {
  check_key: string;
  label: string;
  expected_value: string | null;
  actual_value: string | null;
  status: MatchEvidenceStatus;
  reason: string | null;
  critical: boolean;
}

export interface MatchResult {
  id: number;
  tender_id: number;
  requirement_id: number;
  qualification_id: number | null;
  match_status: MatchStatus;
  reason: string;
  mismatch_detail: string | null;
  expected_qualification: string | null;
  in_knowledge_base: boolean | null;
  similarity_score: number;
  evidence_items: MatchEvidenceItem[];
  confirmed_status: MatchStatus | 'confirmed' | null;
  created_at: string;
  // Denormalized display fields (populated by backend join)
  requirement?: TenderRequirement;
  qualification?: Qualification | null;
}

export interface MatchSummary {
  matched: number;
  unmatched: number;
  needs_review: number;
  total: number;
}

export type MatchProgressStatus = 'idle' | 'queued' | 'running' | 'completed' | 'failed';

export interface MatchProgress {
  tender_id: number;
  status: MatchProgressStatus;
  stage: string;
  current: number;
  total: number;
  matched: number;
  unmatched: number;
  needs_review: number;
  message: string;
  current_requirement: string | null;
  started_at: string | null;
  updated_at: string | null;
  finished_at: string | null;
  error: string | null;
}

export interface MatchCorrection {
  id: number;
  match_id: number | null;
  tender_id: number;
  requirement_id: number;
  qualification_id: number | null;
  previous_status: MatchStatus | null;
  confirmed_status: MatchStatus | 'confirmed';
  correction_reason: string | null;
  evidence_snapshot: MatchEvidenceItem[];
  created_at: string;
  tender_title: string | null;
  tender_filename: string | null;
  requirement_title: string | null;
  requirement_content: string | null;
  requirement_category: RequirementCategory | string | null;
  qualification_name: string | null;
}

// ---------------------------------------------------------------------------
// API Config
// ---------------------------------------------------------------------------

export type ConfigType = 'llm' | 'embedding' | 'vision';

export interface ApiConfig {
  id: number;
  config_type: ConfigType;
  provider: string;
  base_url: string;
  api_key: string; // Masked: ****abcd
  model_name: string;
  is_active: boolean;
  updated_at: string;
}

export interface ApiConfigInput {
  id?: number; // 可选:编辑时回传,便于后端精确更新
  config_type: ConfigType;
  provider: string;
  base_url: string;
  api_key: string;
  model_name: string;
  is_active: boolean;
}

export interface ConfigPreset {
  provider: string;
  label: string;
  config_type: ConfigType; // 新增：标识该预设属于哪个 Tab（llm/embedding/vision）
  base_url: string;
  default_model: string;
  models: string[];
}

export interface TestConnectionRequest {
  config_type: ConfigType;
  base_url: string;
  api_key: string;
  model_name: string;
}

export interface TestConnectionResult {
  success: boolean;
  latency_ms: number;
  message: string;
}

// ---------------------------------------------------------------------------
// Fill Template
// ---------------------------------------------------------------------------

export interface FillTemplate {
  id: number;
  tender_id: number;
  template_path: string;
  template_type: string;
  output_docx_path: string | null;
  output_pdf_path: string | null;
  created_time: string;
  status: string;
}

// ---------------------------------------------------------------------------
// Technical Response (技术响应表)
// ---------------------------------------------------------------------------

export type TechnicalResponseStatus = 'pending' | 'met' | 'deviated' | 'superior';

export interface TechnicalResponse {
  id: number;
  tender_id: number;
  requirement_id: number;
  spec_name: string | null;
  required_value: string | null;
  actual_value: string | null;
  response_status: TechnicalResponseStatus;
  is_hard: boolean;
  remark: string | null;
  created_at: string;
  updated_at: string;
}

export interface TechnicalResponseInput {
  actual_value?: string | null;
  response_status?: TechnicalResponseStatus;
  remark?: string | null;
  is_hard?: boolean;
}

export interface TechnicalResponseBatchItem {
  id: number;
  actual_value?: string | null;
  response_status?: TechnicalResponseStatus;
  remark?: string | null;
}

// ---------------------------------------------------------------------------
// Submission Checklist (投标待办清单)
// ---------------------------------------------------------------------------

export type SubmissionChecklistStatus = 'not_started' | 'in_progress' | 'done';

export interface SubmissionChecklist {
  id: number;
  tender_id: number;
  requirement_id: number | null;
  item_name: string;
  description: string | null;
  status: SubmissionChecklistStatus;
  remark: string | null;
  created_at: string;
  updated_at: string;
}

export interface SubmissionChecklistInput {
  status?: SubmissionChecklistStatus;
  remark?: string | null;
  item_name?: string;
  description?: string | null;
}

export interface ManualChecklistItemInput {
  item_name: string;
  description?: string | null;
  remark?: string | null;
}

export interface CheckReportExport {
  filename: string;
  content_type: string;
  content: string;
}

// ---------------------------------------------------------------------------
// Rule Library (规则库)
// ---------------------------------------------------------------------------

export type RuleStrictness = 'strict' | 'balanced' | 'loose';

export interface RuleCatalogItem {
  id: string;
  name: string;
  domain: string;
  rule_type: string;
  strictness: RuleStrictness;
  enabled: boolean;
  keywords: string[];
  description: string;
  source: string;
  action: string;
}

export interface RuleChangeLog {
  id: number;
  rule_id: string;
  previous_enabled: boolean;
  new_enabled: boolean;
  reason: string | null;
  created_at: string;
}

export interface RuleRelation {
  id: number;
  source_rule_id: string;
  target_rule_id: string;
  relation_type: string;
  reason: string | null;
  created_at: string;
  direction: 'outgoing' | 'incoming' | string;
  related_rule_id: string;
  related_rule_name: string;
  related_rule_source: string;
  related_rule_status: string;
}

export interface RuleMergeResult {
  source_rule_id: string;
  target_rule_id: string;
  relation_type: string;
  reason: string | null;
  created_at: string;
}

export interface RuleVersion {
  id: number;
  rule_id: string;
  version_no: number;
  name: string;
  rule_type: string;
  description: string;
  edit_reason: string | null;
  created_at: string;
}

export interface RuleTemplate {
  id: string;
  name: string;
  category: string;
  rule_type: string;
  risk_level: 'high' | 'medium' | 'low' | string;
  applicable_scene: string;
  evidence_requirements: string[];
  positive_examples: string[];
  negative_examples: string[];
  review_notes: string;
}

export interface RuleSuggestion {
  id: string;
  source: string;
  source_id: number;
  suggestion_type: 'tighten_rule' | 'loosen_rule' | string;
  title: string;
  reason: string;
  confidence: number;
  quality_status: string;
  quality_notes: string | null;
  evidence_gaps: string[];
  requirement_id: number;
  requirement_title: string;
  requirement_content: string | null;
  requirement_category: string | null;
  tender_id: number;
  tender_title: string | null;
  tender_filename: string | null;
  evidence_snapshot: string | null;
  review_status: 'pending' | 'accepted' | 'rejected';
  review_reason: string | null;
  created_at: string;
}

export interface RuleSuggestionReview {
  suggestion_id: string;
  review_status: 'pending' | 'accepted' | 'rejected';
  review_reason: string | null;
}

export interface RuleDraft {
  id: number;
  source_suggestion_id: string;
  name: string;
  rule_type: string;
  draft_content: string;
  draft_status: string;
  review_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface SimilarRuleCandidate {
  rule_id: string;
  name: string;
  rule_type: string;
  source: string;
  status: string;
  similarity: number;
  reasons: string[];
  description: string;
}
