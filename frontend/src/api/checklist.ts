import client from './client';
import type {
  ManualChecklistItemInput,
  CheckReportExport,
  SubmissionChecklist,
  SubmissionChecklistInput,
} from '../types';

/**
 * Submission Checklist API module.
 */

/** GET /tenders/{id}/checklist — fetch checklist items (auto-init on first access). */
export async function getChecklist(
  tenderId: number,
): Promise<SubmissionChecklist[]> {
  const res = await client.get<unknown[]>(`/tenders/${tenderId}/checklist`);
  return res.data.map((raw) => normalizeChecklistItem(raw));
}

/** PUT /tenders/{id}/checklist/{itemId} — update a checklist item. */
export async function updateChecklistItem(
  tenderId: number,
  itemId: number,
  data: SubmissionChecklistInput,
): Promise<SubmissionChecklist> {
  const res = await client.put<unknown>(
    `/tenders/${tenderId}/checklist/${itemId}`,
    data,
  );
  return normalizeChecklistItem(res.data);
}

/** POST /tenders/{id}/checklist — manually add a checklist item. */
export async function addManualChecklistItem(
  tenderId: number,
  data: ManualChecklistItemInput,
): Promise<SubmissionChecklist> {
  const res = await client.post<unknown>(
    `/tenders/${tenderId}/checklist`,
    data,
  );
  return normalizeChecklistItem(res.data);
}

/** GET /tenders/{id}/check-report/export — export Markdown check report. */
export async function exportCheckReport(
  tenderId: number,
): Promise<CheckReportExport> {
  const res = await client.get<CheckReportExport>(
    `/tenders/${tenderId}/check-report/export`,
  );
  return res.data;
}

/** Normalize raw API response to SubmissionChecklist. */
function normalizeChecklistItem(raw: unknown): SubmissionChecklist {
  const item = raw as Record<string, unknown>;
  const status = item.status;
  return {
    id: Number(item.id),
    tender_id: Number(item.tender_id),
    requirement_id:
      item.requirement_id == null ? null : Number(item.requirement_id),
    item_name: String(item.item_name || ''),
    description:
      item.description == null ? null : String(item.description),
    status:
      status === 'in_progress' || status === 'done'
        ? status
        : 'not_started',
    remark: item.remark == null ? null : String(item.remark),
    created_at: String(item.created_at || ''),
    updated_at: String(item.updated_at || ''),
  };
}
