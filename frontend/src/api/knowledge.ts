import client from './client';
import type {
  KnowledgeFile,
  Qualification,
  QualificationInput,
  KnowledgeCategory,
  ParseStatus,
} from '../types';

export interface BulkUpdateQualificationCategoryResult {
  updated_qualification_count: number;
  updated_file_count: number;
  missing_qualification_ids: number[];
}

export interface BulkDeleteQualificationsBySourceResult {
  deleted_file_count: number;
  deleted_manual_qualification_count: number;
  deleted_related_qualification_count: number;
  missing_qualification_ids: number[];
}

export interface ReparseIncompleteQualificationsResult {
  file_ids: number[];
  submitted_count: number;
}

/**
 * Knowledge base API module (P0-04/05/06).
 */

/** POST /knowledge/upload — upload a knowledge file with category (multipart). */
export async function uploadFile(
  file: File,
  category: string
): Promise<KnowledgeFile> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('category', category);
  const res = await client.post<KnowledgeFile>('/knowledge/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

/** GET /knowledge/files — fetch all uploaded files. */
export async function getFiles(): Promise<KnowledgeFile[]> {
  const res = await client.get<KnowledgeFile[]>('/knowledge/files');
  return res.data;
}

/** Build an inline preview/download URL for a knowledge file. */
export function getKnowledgeFilePreviewUrl(
  fileId: number,
  disposition: 'inline' | 'attachment' = 'inline',
): string {
  return `/api/v1/knowledge/files/${fileId}/preview?disposition=${disposition}`;
}

/** GET /knowledge/qualifications — fetch qualifications, optionally filtered by category. */
export async function getQualifications(
  category?: KnowledgeCategory | 'other' | 'all'
): Promise<Qualification[]> {
  const params: Record<string, string> = {};
  if (category && category !== 'all') {
    params.category = category;
  }
  const res = await client.get<Qualification[]>('/knowledge/qualifications', { params });
  return res.data;
}

/** POST /knowledge/qualifications — manually create a qualification entry. */
export async function createQualification(
  data: QualificationInput
): Promise<Qualification> {
  const res = await client.post<Qualification>('/knowledge/qualifications', data);
  return res.data;
}

/** PUT /knowledge/qualifications/{id} — edit an existing qualification. */
export async function updateQualification(
  id: number,
  data: Partial<QualificationInput>
): Promise<Qualification> {
  const res = await client.put<Qualification>(`/knowledge/qualifications/${id}`, data);
  return res.data;
}

/** DELETE /knowledge/qualifications/{id} — delete a qualification. */
export async function deleteQualification(id: number): Promise<{ message: string }> {
  const res = await client.delete<{ message: string }>(`/knowledge/qualifications/${id}`);
  return res.data;
}

/** POST /knowledge/qualifications/bulk-category — change category for many qualifications. */
export async function bulkUpdateQualificationCategory(
  qualificationIds: number[],
  category: KnowledgeCategory | 'other'
): Promise<BulkUpdateQualificationCategoryResult> {
  const res = await client.post<BulkUpdateQualificationCategoryResult>(
    '/knowledge/qualifications/bulk-category',
    { qualification_ids: qualificationIds, category }
  );
  return res.data;
}

/** POST /knowledge/qualifications/bulk-delete-source — delete selected qualifications by source file. */
export async function bulkDeleteQualificationsBySource(
  qualificationIds: number[]
): Promise<BulkDeleteQualificationsBySourceResult> {
  const res = await client.post<BulkDeleteQualificationsBySourceResult>(
    '/knowledge/qualifications/bulk-delete-source',
    { qualification_ids: qualificationIds }
  );
  return res.data;
}

/** GET /knowledge/files/{fileId}/status — fetch file parse status (for polling). */
export async function getFileStatus(
  fileId: number
): Promise<{ file_id: number; status: ParseStatus }> {
  const res = await client.get<{ file_id: number; status: ParseStatus }>(
    `/knowledge/files/${fileId}/status`
  );
  return res.data;
}

/** DELETE /knowledge/files/{fileId} — delete a file and its associated qualifications. */
export async function deleteFile(fileId: number): Promise<{ message: string }> {
  const res = await client.delete<{ message: string }>(`/knowledge/files/${fileId}`);
  return res.data;
}

/** POST /knowledge/files/{fileId}/reparse — re-trigger file parsing. */
export async function reparseFile(fileId: number): Promise<{ message: string }> {
  const res = await client.post<{ message: string }>(`/knowledge/files/${fileId}/reparse`);
  return res.data;
}

/** POST /knowledge/qualifications/reparse-incomplete — re-analyze incomplete qualifications. */
export async function reparseIncompleteQualifications(
  category?: KnowledgeCategory | 'other'
): Promise<ReparseIncompleteQualificationsResult> {
  const params: Record<string, string> = {};
  if (category) params.category = category;
  const res = await client.post<ReparseIncompleteQualificationsResult>(
    '/knowledge/qualifications/reparse-incomplete',
    null,
    { params },
  );
  return res.data;
}
