import client from './client';
import type { FillTemplate } from '../types';

/**
 * Fill API module (P0-09).
 */

/** POST /fill/{tenderId}/template — upload a fill template (multipart). */
export async function uploadTemplate(
  tenderId: number,
  file: File
): Promise<FillTemplate> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await client.post<FillTemplate>(
    `/fill/${tenderId}/template`,
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
    }
  );
  return res.data;
}

/** POST /fill/{tenderId} — trigger auto-fill. */
export async function fillTemplate(tenderId: number): Promise<FillTemplate> {
  const res = await client.post<FillTemplate>(`/fill/${tenderId}`);
  return res.data;
}

/** GET /fill/{tenderId}/download — download filled result (blob). */
export async function downloadFilled(
  tenderId: number,
  format: 'docx' | 'pdf'
): Promise<Blob> {
  const res = await client.get(`/fill/${tenderId}/download`, {
    params: { format },
    responseType: 'blob',
  });
  return res.data as unknown as Blob;
}
