import client from './client';
import type {
  RequirementReviewStatus,
  Tender,
  TenderRequirement,
  TenderRequirementInput,
  TenderStatusResponse,
} from '../types';
import { normalizeRequirement } from '../pages/tenderRequirementView';

/**
 * Tender API module (P0-01/02/03).
 */

/** POST /tenders/upload — upload a tender document (multipart). */
export async function uploadTender(file: File): Promise<Tender> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await client.post<{ tender_id: number; status: string }>('/tenders/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  // Backend returns { tender_id, status }, normalize to Tender shape for callers
  return { id: res.data.tender_id, status: res.data.status } as Tender;
}

/** POST /tenders/{id}/parse — trigger parsing for a tender. */
export async function parseTender(id: number): Promise<{ message: string }> {
  const res = await client.post<{ message: string }>(`/tenders/${id}/parse`);
  return res.data;
}

/** POST /tenders/{id}/reparse — re-parse with new classification system. */
export async function reparseRequirements(
  id: number,
): Promise<{ message: string }> {
  const res = await client.post<{ message: string }>(
    `/tenders/${id}/reparse`,
  );
  return res.data;
}

/** GET /tenders — fetch list of all tenders, with optional search/filter. */
export async function getTenders(params?: {
  search?: string;
  status?: string;
  region?: string;
}): Promise<Tender[]> {
  const query = new URLSearchParams();
  if (params?.search) query.set('search', params.search);
  if (params?.status) query.set('status', params.status);
  if (params?.region) query.set('region', params.region);
  const qs = query.toString();
  const res = await client.get<Tender[]>(`/tenders${qs ? '?' + qs : ''}`);
  return res.data;
}

/** GET /tenders/{id} — fetch tender detail and requirements. */
export async function getTenderDetail(id: number): Promise<{
  tender: Tender;
  requirements: TenderRequirement[];
}> {
  const res = await client.get<{
    tender: Tender;
    requirements: unknown[];
  }>(`/tenders/${id}`);
  return {
    tender: res.data.tender,
    requirements: res.data.requirements.map(normalizeRequirement),
  };
}

/** GET /tenders/{id}/requirements — fetch structured requirements for a tender. */
export async function getRequirements(id: number): Promise<TenderRequirement[]> {
  const res = await client.get<unknown[]>(`/tenders/${id}/requirements`);
  return res.data.map(normalizeRequirement);
}

export async function updateRequirement(
  tenderId: number,
  requirementId: number,
  data: TenderRequirementInput,
): Promise<TenderRequirement> {
  const res = await client.put<unknown>(
    `/tenders/${tenderId}/requirements/${requirementId}`,
    data,
  );
  return normalizeRequirement(res.data);
}

export async function createRequirement(
  tenderId: number,
  data: TenderRequirementInput,
): Promise<TenderRequirement> {
  const res = await client.post<unknown>(
    `/tenders/${tenderId}/requirements`,
    data,
  );
  return normalizeRequirement(res.data);
}

export async function deleteRequirement(
  tenderId: number,
  requirementId: number,
): Promise<{ deleted: boolean }> {
  const res = await client.delete<{ deleted: boolean }>(
    `/tenders/${tenderId}/requirements/${requirementId}`,
  );
  return res.data;
}

export async function batchUpdateRequirementStatus(
  tenderId: number,
  requirementIds: number[],
  reviewStatus: RequirementReviewStatus,
): Promise<{ updated: number }> {
  const res = await client.post<{ updated: number }>(
    `/tenders/${tenderId}/requirements/batch-status`,
    { requirement_ids: requirementIds, review_status: reviewStatus },
  );
  return res.data;
}

export async function batchDeleteRequirements(
  tenderId: number,
  requirementIds: number[],
): Promise<{ deleted: number }> {
  const res = await client.post<{ deleted: number }>(
    `/tenders/${tenderId}/requirements/batch-delete`,
    { requirement_ids: requirementIds },
  );
  return res.data;
}

export const getTenderPdfUrl = (tenderId: number, page?: number): string => {
  const fragment = page ? `#page=${page}&zoom=page-width` : '#zoom=page-width';
  return `/api/v1/tenders/${tenderId}/pdf${fragment}`;
};

/** GET /tenders/{id}/status — poll parsing progress. */
export async function getStatus(id: number): Promise<TenderStatusResponse> {
  const res = await client.get<TenderStatusResponse>(`/tenders/${id}/status`);
  return res.data;
}

/** DELETE /tenders/{id} — delete a tender and all its associated data. */
export async function deleteTender(id: number): Promise<{ deleted: boolean }> {
  const res = await client.delete<{ deleted: boolean }>(`/tenders/${id}`);
  return res.data;
}
