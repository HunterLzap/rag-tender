import client from './client';
import type { MatchCorrection, MatchEvidenceItem, MatchProgress, MatchResult, MatchStatus } from '../types';
import { normalizeMatchResult } from '../pages/tenderRequirementView';

/**
 * Match API module (P0-07/08).
 */

/** POST /match/{tenderId} — trigger matching for a tender. */
export async function matchTender(tenderId: number): Promise<{ message: string }> {
  const res = await client.post<{ message: string }>(`/match/${tenderId}`);
  return res.data;
}

/** GET /match/{tenderId} — fetch match results for a tender. */
export async function getMatchResults(tenderId: number): Promise<MatchResult[]> {
  const res = await client.get<unknown[]>(`/match/${tenderId}`);
  return res.data.map(normalizeMatchResult);
}

/** GET /match/{tenderId}/status — fetch live matching progress. */
export async function getMatchStatus(tenderId: number): Promise<MatchProgress> {
  const res = await client.get<MatchProgress>(`/match/${tenderId}/status`);
  return res.data;
}

function normalizeCorrection(raw: unknown): MatchCorrection {
  const item = raw as Record<string, unknown>;
  return {
    id: Number(item.id),
    match_id: item.match_id == null ? null : Number(item.match_id),
    tender_id: Number(item.tender_id),
    requirement_id: Number(item.requirement_id),
    qualification_id:
      item.qualification_id == null ? null : Number(item.qualification_id),
    previous_status:
      item.previous_status === 'matched' ||
      item.previous_status === 'unmatched' ||
      item.previous_status === 'needs_review'
        ? item.previous_status
        : null,
    confirmed_status:
      item.confirmed_status === 'matched' ||
      item.confirmed_status === 'unmatched' ||
      item.confirmed_status === 'needs_review' ||
      item.confirmed_status === 'confirmed'
        ? item.confirmed_status
        : 'needs_review',
    correction_reason:
      item.correction_reason == null ? null : String(item.correction_reason),
    evidence_snapshot: Array.isArray(item.evidence_snapshot)
      ? (item.evidence_snapshot as MatchEvidenceItem[])
      : [],
    created_at: String(item.created_at || ''),
    tender_title: item.tender_title == null ? null : String(item.tender_title),
    tender_filename:
      item.tender_filename == null ? null : String(item.tender_filename),
    requirement_title:
      item.requirement_title == null ? null : String(item.requirement_title),
    requirement_content:
      item.requirement_content == null ? null : String(item.requirement_content),
    requirement_category:
      item.requirement_category == null ? null : String(item.requirement_category),
    qualification_name:
      item.qualification_name == null ? null : String(item.qualification_name),
  };
}

/** GET /match/corrections — fetch human correction cases. */
export async function getMatchCorrections(limit = 100): Promise<MatchCorrection[]> {
  const res = await client.get<unknown[]>(`/match/corrections`, {
    params: { limit },
  });
  return res.data.map(normalizeCorrection);
}

/** PUT /match/{matchId}/confirm — manually confirm a match result. */
export async function confirmMatch(
  matchId: number,
  status: MatchStatus | 'confirmed',
  correctionReason?: string
): Promise<MatchResult> {
  const res = await client.put<unknown>(`/match/${matchId}/confirm`, {
    confirmed_status: status,
    correction_reason: correctionReason || null,
  });
  return normalizeMatchResult(res.data);
}
