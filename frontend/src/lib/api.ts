import axios, { isAxiosError } from 'axios';

export const api = axios.create({
  baseURL: '/api/v2',
  timeout: 60_000,
});

export function apiError(error: unknown, fallback = '操作失败，请重试'): string {
  if (isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map((item) => item.msg).join('；');
    if (!error.response) return '无法连接本地服务，请确认服务已启动';
  }
  return fallback;
}

export interface Project {
  id: string;
  name: string;
  bidder_name: string | null;
  purchaser: string | null;
  tender_no: string | null;
  bid_deadline: string | null;
  timezone: string;
  status: string;
  notes: string | null;
  document_count: number;
  latest_run_id: string | null;
  latest_run_status: string | null;
  created_at: string;
  updated_at: string;
}

export interface Bid {
  id: string;
  project_id: string;
  bidder_name: string;
  lot_code: string | null;
  bid_deadline: string | null;
  status: string;
  as_of_date: string | null;
}

export interface DocumentItem {
  id: string;
  project_id: string;
  role: string;
  filename: string;
  content_type: string | null;
  sha256: string;
  file_size: number;
  page_count: number;
  current_revision_id: string | null;
  current_page_count: number;
  parse_status: string;
  parse_error: string | null;
  supersedes_id: string | null;
  created_at: string;
}

export interface PageItem {
  id: string;
  document_id: string;
  page_index: number;
  printed_label: string | null;
  width: number;
  height: number;
  text: string;
  parse_mode: string;
  quality_flags: string[];
  native_locator: Record<string, unknown>;
  blocks?: Array<{
    id: string; kind: string; text: string; reading_order: number;
    cells: Array<{
      id: string; row_index: number; col_index: number; row_span: number; col_span: number; text: string;
    }>;
  }>;
}

export interface SourceSpan {
  id: string;
  document_id: string;
  revision_id: string;
  page_id: string;
  block_id: string | null;
  table_cell_id: string | null;
  quote: string;
  bbox_json: number[];
  document_filename?: string | null;
  page_index?: number | null;
}

export interface Requirement {
  id: string;
  run_id: string;
  category: string;
  evaluation_stage: string;
  evaluation_type: string;
  obligation: string;
  consequence: string;
  handling_mode: string;
  title: string;
  statement: string;
  condition_json: Record<string, unknown>;
  status: string;
  confidence: number | null;
  extraction_method: string;
  review_status: string;
  fingerprint: string;
  source_span: SourceSpan | null;
}

export interface Decision {
  id: string;
  run_id: string;
  requirement_id: string;
  status: 'met' | 'not_met' | 'needs_review' | 'not_applicable';
  summary: string;
  confidence: number | null;
  rule_trace: Array<Record<string, unknown>>;
  model_trace: Record<string, unknown>;
  evidence_ids: string[];
  condition_results: Array<Record<string, unknown>>;
  stale: boolean;
  requirement: Requirement | null;
  reviews: ReviewRecord[];
}

export interface FillSuggestion {
  id: string;
  target_id: string;
  value: string | null;
  rationale: string;
  confidence: number | null;
  status: string;
  evidence_ids: string[];
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_note: string | null;
}

export interface FillTarget {
  id: string;
  plan_id: string;
  page_id: string;
  block_id: string | null;
  table_cell_id: string | null;
  kind: string;
  label: string;
  bbox_json: number[];
  requirement_id: string | null;
  fill_slot_id: string | null;
  suggestions: FillSuggestion[];
}

export interface AnnotationAsset {
  id: string;
  plan_id: string;
  page_id: string;
  kind: string;
  path: string;
  width: number;
  height: number;
  annotations: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
}

export interface FillPlan {
  id: string;
  run_id: string;
  document_id: string;
  status: string;
  created_at: string;
  targets: FillTarget[];
  assets: AnnotationAsset[];
}

export interface FillSlot {
  id: string;
  page_id: string;
  block_id: string | null;
  table_cell_id: string | null;
  kind: string;
  label: string;
  locator: Record<string, unknown>;
  bbox_json: number[];
  value_schema: Record<string, unknown>;
  status: string;
}

export interface ChecklistItem {
  id: string;
  run_id: string;
  requirement_id: string | null;
  title: string;
  detail: string | null;
  severity: string;
  completed: boolean;
}

export interface ResponseValue {
  id: string;
  project_id: string;
  key: string;
  label: string;
  value_text: string | null;
  value_number: string | null;
  value_date: string | null;
  unit: string | null;
  currency: string | null;
  source: string;
  evidence_ids: string[];
  review_status: string;
  version: number;
}

export interface ReviewRecord {
  id: string;
  decision_id: string;
  reviewer: string | null;
  previous_status: string | null;
  new_status: string;
  reason: string;
  evidence_snapshot: string[];
  created_at: string;
}

export interface AnalysisRun {
  id: string;
  project_id: string;
  status: string;
  stage: string;
  progress: number;
  ruleset_version: string;
  prompt_version: string;
  model_snapshot: Record<string, unknown>;
  input_snapshot: Array<Record<string, unknown>>;
  coverage_notes: string[];
  error: string | null;
  created_at: string;
  updated_at: string;
  requirement_count: number;
  decision_counts: Record<string, number>;
  job_id: string | null;
}

export interface Job {
  id: string;
  kind: string;
  payload: Record<string, unknown>;
  status: string;
  progress: number;
  stage: string;
  attempts: number;
  error: string | null;
}

export interface AnalysisReport {
  run_id: string;
  generated_at: string;
  markdown: string;
  summary: Record<string, number>;
}

export interface Evidence {
  id: string;
  project_id: string | null;
  kind: string;
  title: string;
  holder: string | null;
  issuer: string | null;
  identifier: string | null;
  issued_on: string | null;
  valid_from: string | null;
  valid_until: string | null;
  status: string;
  review_status: string;
  payload: Record<string, unknown>;
  source_span: SourceSpan | null;
  facts: Array<{
    id: string;
    fact_key: string;
    value_text: string | null;
    value_number: string | null;
    value_date: string | null;
    unit: string | null;
  }>;
}

export async function uploadDocument(
  projectId: string,
  role: string,
  file: File,
): Promise<DocumentItem> {
  const form = new FormData();
  form.append('role', role);
  form.append('file', file);
  return (await api.post(`/projects/${projectId}/documents`, form)).data;
}
