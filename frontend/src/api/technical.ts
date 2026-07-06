import client from './client';
import type {
  TechnicalResponse,
  TechnicalResponseInput,
  TechnicalResponseBatchItem,
} from '../types';

/**
 * Technical Response API module.
 */

/** GET /tenders/{id}/technical — fetch technical responses (auto-init on first access). */
export async function getTechnicalResponses(
  tenderId: number,
): Promise<TechnicalResponse[]> {
  const res = await client.get<unknown[]>(`/tenders/${tenderId}/technical`);
  return res.data.map((raw) => normalizeTechnicalResponse(raw));
}

/** PUT /tenders/{id}/technical/{responseId} — update a single technical response. */
export async function updateTechnicalResponse(
  tenderId: number,
  responseId: number,
  data: TechnicalResponseInput,
): Promise<TechnicalResponse> {
  const res = await client.put<unknown>(
    `/tenders/${tenderId}/technical/${responseId}`,
    data,
  );
  return normalizeTechnicalResponse(res.data);
}

/** PUT /tenders/{id}/technical/batch — batch update technical responses. */
export async function batchUpdateTechnicalResponses(
  tenderId: number,
  items: TechnicalResponseBatchItem[],
): Promise<TechnicalResponse[]> {
  const res = await client.put<unknown[]>(
    `/tenders/${tenderId}/technical/batch`,
    { items },
  );
  return res.data.map((raw) => normalizeTechnicalResponse(raw));
}

/** Normalize raw API response to TechnicalResponse. */
function normalizeTechnicalResponse(raw: unknown): TechnicalResponse {
  const item = raw as Record<string, unknown>;
  const status = item.response_status;
  return {
    id: Number(item.id),
    tender_id: Number(item.tender_id),
    requirement_id: Number(item.requirement_id),
    spec_name: item.spec_name == null ? null : String(item.spec_name),
    required_value:
      item.required_value == null ? null : String(item.required_value),
    actual_value:
      item.actual_value == null ? null : String(item.actual_value),
    response_status:
      status === 'met' || status === 'deviated' || status === 'superior'
        ? status
        : 'pending',
    is_hard: Boolean(item.is_hard),
    remark: item.remark == null ? null : String(item.remark),
    created_at: String(item.created_at || ''),
    updated_at: String(item.updated_at || ''),
  };
}
