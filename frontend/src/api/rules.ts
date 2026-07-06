import client from './client';
import type {
  RuleCatalogItem,
  RuleChangeLog,
  RuleDraft,
  RuleMergeResult,
  RuleRelation,
  RuleTemplate,
  RuleVersion,
  SimilarRuleCandidate,
  RuleStrictness,
  RuleSuggestion,
  RuleSuggestionReview,
} from '../types';

export async function getRuleCatalog(): Promise<RuleCatalogItem[]> {
  const res = await client.get<unknown[]>('/rules');
  return res.data.map(normalizeRuleCatalogItem);
}

export async function getRuleTemplates(): Promise<RuleTemplate[]> {
  const res = await client.get<unknown[]>('/rules/templates');
  return res.data.map(normalizeRuleTemplate);
}

export async function createRuleDraftFromTemplate(
  templateId: string,
  reason: string,
): Promise<RuleDraft> {
  const res = await client.post<unknown>(`/rules/templates/${templateId}/draft`, {
    reason,
  });
  return normalizeRuleDraft(res.data);
}

export async function updateRuleEnabled(
  ruleId: string,
  enabled: boolean,
  reason?: string,
): Promise<RuleCatalogItem> {
  const res = await client.put<unknown>(`/rules/${ruleId}/enabled`, {
    enabled,
    reason: reason || null,
  });
  return normalizeRuleCatalogItem(res.data);
}

export async function getRuleChangeLogs(limit = 100): Promise<RuleChangeLog[]> {
  const res = await client.get<unknown[]>('/rules/changes', {
    params: { limit },
  });
  return res.data.map(normalizeRuleChangeLog);
}

export async function getRuleRelations(ruleId: string): Promise<RuleRelation[]> {
  const res = await client.get<unknown[]>(`/rules/${ruleId}/relations`);
  return res.data.map(normalizeRuleRelation);
}

export async function getRuleVersions(ruleId: string): Promise<RuleVersion[]> {
  const res = await client.get<unknown[]>(`/rules/${ruleId}/versions`);
  return res.data.map(normalizeRuleVersion);
}

export async function updateCustomRule(
  ruleId: string,
  input: {
    name: string;
    rule_type: string;
    description: string;
    edit_reason: string;
  },
): Promise<RuleCatalogItem> {
  const res = await client.put<unknown>(`/rules/${ruleId}`, {
    name: input.name,
    rule_type: input.rule_type,
    description: input.description,
    edit_reason: input.edit_reason,
  });
  return normalizeRuleCatalogItem(res.data);
}

export async function rollbackCustomRule(
  ruleId: string,
  versionNo: number,
  reason: string,
): Promise<RuleCatalogItem> {
  const res = await client.put<unknown>(`/rules/${ruleId}/rollback`, {
    version_no: versionNo,
    reason,
  });
  return normalizeRuleCatalogItem(res.data);
}

export async function mergeCustomRule(
  sourceRuleId: string,
  targetRuleId: string,
  reason?: string,
): Promise<RuleMergeResult> {
  const res = await client.put<unknown>(`/rules/${sourceRuleId}/merge`, {
    target_rule_id: targetRuleId,
    reason: reason || null,
  });
  const item = res.data as Record<string, unknown>;
  return {
    source_rule_id: String(item.source_rule_id || ''),
    target_rule_id: String(item.target_rule_id || ''),
    relation_type: String(item.relation_type || ''),
    reason: item.reason == null ? null : String(item.reason),
    created_at: String(item.created_at || ''),
  };
}

export async function getRuleSuggestions(limit = 100): Promise<RuleSuggestion[]> {
  const res = await client.get<unknown[]>('/rules/suggestions', {
    params: { limit },
  });
  return res.data.map(normalizeRuleSuggestion);
}

export async function reviewRuleSuggestion(
  suggestionId: string,
  reviewStatus: RuleSuggestionReview['review_status'],
  reviewReason?: string,
): Promise<RuleSuggestionReview> {
  const res = await client.put<unknown>(`/rules/suggestions/${suggestionId}/review`, {
    review_status: reviewStatus,
    review_reason: reviewReason || null,
  });
  const item = res.data as Record<string, unknown>;
  return {
    suggestion_id: String(item.suggestion_id || ''),
    review_status:
      item.review_status === 'accepted' || item.review_status === 'rejected'
        ? item.review_status
        : 'pending',
    review_reason: item.review_reason == null ? null : String(item.review_reason),
  };
}

export async function getRuleDrafts(limit = 100): Promise<RuleDraft[]> {
  const res = await client.get<unknown[]>('/rules/drafts', {
    params: { limit },
  });
  return res.data.map(normalizeRuleDraft);
}

export async function reviewRuleDraft(
  draftId: number,
  draftStatus: 'published' | 'rejected' | 'pending_review',
  reviewReason?: string,
  options?: {
    similarRuleIds?: string[];
    differenceReason?: string;
  },
): Promise<RuleDraft> {
  const res = await client.put<unknown>(`/rules/drafts/${draftId}/review`, {
    draft_status: draftStatus,
    review_reason: reviewReason || null,
    similar_rule_ids: options?.similarRuleIds || null,
    difference_reason: options?.differenceReason || null,
  });
  return normalizeRuleDraft(res.data);
}

export async function updateRuleDraft(
  draftId: number,
  input: {
    name: string;
    rule_type: string;
    draft_content: string;
    edit_reason?: string;
  },
): Promise<RuleDraft> {
  const res = await client.put<unknown>(`/rules/drafts/${draftId}`, {
    name: input.name,
    rule_type: input.rule_type,
    draft_content: input.draft_content,
    edit_reason: input.edit_reason || null,
  });
  return normalizeRuleDraft(res.data);
}

export async function getSimilarRulesForDraft(
  draftId: number,
  limit = 10,
): Promise<SimilarRuleCandidate[]> {
  const res = await client.get<unknown[]>(`/rules/drafts/${draftId}/similar`, {
    params: { limit },
  });
  return res.data.map(normalizeSimilarRuleCandidate);
}

export async function reuseExistingRuleForDraft(
  draftId: number,
  targetRuleId: string,
  reason?: string,
): Promise<{
  draft_id: number;
  source_rule_id: string;
  target_rule_id: string;
  relation_type: string;
  reason: string | null;
}> {
  const res = await client.put<unknown>(`/rules/drafts/${draftId}/reuse`, {
    target_rule_id: targetRuleId,
    reason: reason || null,
  });
  const item = res.data as Record<string, unknown>;
  return {
    draft_id: Number(item.draft_id),
    source_rule_id: String(item.source_rule_id || ''),
    target_rule_id: String(item.target_rule_id || ''),
    relation_type: String(item.relation_type || ''),
    reason: item.reason == null ? null : String(item.reason),
  };
}

function normalizeRuleCatalogItem(raw: unknown): RuleCatalogItem {
  const item = raw as Record<string, unknown>;
  const strictness = item.strictness;

  return {
    id: String(item.id || ''),
    name: String(item.name || ''),
    domain: String(item.domain || ''),
    rule_type: String(item.rule_type || ''),
    strictness:
      strictness === 'balanced' || strictness === 'loose'
        ? (strictness as RuleStrictness)
        : 'strict',
    enabled: Boolean(item.enabled),
    keywords: Array.isArray(item.keywords)
      ? item.keywords.map((keyword) => String(keyword))
      : [],
    description: String(item.description || ''),
    source: String(item.source || ''),
    action: String(item.action || ''),
  };
}

function normalizeRuleTemplate(raw: unknown): RuleTemplate {
  const item = raw as Record<string, unknown>;
  const riskLevel = item.risk_level;
  return {
    id: String(item.id || ''),
    name: String(item.name || ''),
    category: String(item.category || ''),
    rule_type: String(item.rule_type || ''),
    risk_level:
      riskLevel === 'high' || riskLevel === 'medium' || riskLevel === 'low'
        ? riskLevel
        : String(riskLevel || ''),
    applicable_scene: String(item.applicable_scene || ''),
    evidence_requirements: Array.isArray(item.evidence_requirements)
      ? item.evidence_requirements.map((evidence) => String(evidence))
      : [],
    positive_examples: Array.isArray(item.positive_examples)
      ? item.positive_examples.map((example) => String(example))
      : [],
    negative_examples: Array.isArray(item.negative_examples)
      ? item.negative_examples.map((example) => String(example))
      : [],
    review_notes: String(item.review_notes || ''),
  };
}

function normalizeRuleChangeLog(raw: unknown): RuleChangeLog {
  const item = raw as Record<string, unknown>;
  return {
    id: Number(item.id),
    rule_id: String(item.rule_id || ''),
    previous_enabled: Boolean(item.previous_enabled),
    new_enabled: Boolean(item.new_enabled),
    reason: item.reason == null ? null : String(item.reason),
    created_at: String(item.created_at || ''),
  };
}

function normalizeRuleRelation(raw: unknown): RuleRelation {
  const item = raw as Record<string, unknown>;
  const direction = String(item.direction || '');
  return {
    id: Number(item.id),
    source_rule_id: String(item.source_rule_id || ''),
    target_rule_id: String(item.target_rule_id || ''),
    relation_type: String(item.relation_type || ''),
    reason: item.reason == null ? null : String(item.reason),
    created_at: String(item.created_at || ''),
    direction: direction === 'outgoing' || direction === 'incoming' ? direction : direction,
    related_rule_id: String(item.related_rule_id || ''),
    related_rule_name: String(item.related_rule_name || ''),
    related_rule_source: String(item.related_rule_source || ''),
    related_rule_status: String(item.related_rule_status || ''),
  };
}

function normalizeRuleVersion(raw: unknown): RuleVersion {
  const item = raw as Record<string, unknown>;
  return {
    id: Number(item.id),
    rule_id: String(item.rule_id || ''),
    version_no: Number(item.version_no || 0),
    name: String(item.name || ''),
    rule_type: String(item.rule_type || ''),
    description: String(item.description || ''),
    edit_reason: item.edit_reason == null ? null : String(item.edit_reason),
    created_at: String(item.created_at || ''),
  };
}

function normalizeRuleSuggestion(raw: unknown): RuleSuggestion {
  const item = raw as Record<string, unknown>;
  return {
    id: String(item.id || ''),
    source: String(item.source || ''),
    source_id: Number(item.source_id),
    suggestion_type: String(item.suggestion_type || ''),
    title: String(item.title || ''),
    reason: String(item.reason || ''),
    confidence: Number(item.confidence || 0),
    quality_status: String(item.quality_status || ''),
    quality_notes: item.quality_notes == null ? null : String(item.quality_notes),
    evidence_gaps: Array.isArray(item.evidence_gaps)
      ? item.evidence_gaps.map((gap) => String(gap))
      : [],
    requirement_id: Number(item.requirement_id),
    requirement_title: String(item.requirement_title || ''),
    requirement_content:
      item.requirement_content == null ? null : String(item.requirement_content),
    requirement_category:
      item.requirement_category == null ? null : String(item.requirement_category),
    tender_id: Number(item.tender_id),
    tender_title: item.tender_title == null ? null : String(item.tender_title),
    tender_filename:
      item.tender_filename == null ? null : String(item.tender_filename),
    evidence_snapshot:
      item.evidence_snapshot == null ? null : String(item.evidence_snapshot),
    review_status:
      item.review_status === 'accepted' || item.review_status === 'rejected'
        ? item.review_status
        : 'pending',
    review_reason: item.review_reason == null ? null : String(item.review_reason),
    created_at: String(item.created_at || ''),
  };
}

function normalizeRuleDraft(raw: unknown): RuleDraft {
  const item = raw as Record<string, unknown>;
  return {
    id: Number(item.id),
    source_suggestion_id: String(item.source_suggestion_id || ''),
    name: String(item.name || ''),
    rule_type: String(item.rule_type || ''),
    draft_content: String(item.draft_content || ''),
    draft_status: String(item.draft_status || ''),
    review_reason: item.review_reason == null ? null : String(item.review_reason),
    created_at: String(item.created_at || ''),
    updated_at: String(item.updated_at || ''),
  };
}

function normalizeSimilarRuleCandidate(raw: unknown): SimilarRuleCandidate {
  const item = raw as Record<string, unknown>;
  return {
    rule_id: String(item.rule_id || ''),
    name: String(item.name || ''),
    rule_type: String(item.rule_type || ''),
    source: String(item.source || ''),
    status: String(item.status || ''),
    similarity: Number(item.similarity || 0),
    reasons: Array.isArray(item.reasons)
      ? item.reasons.map((reason) => String(reason))
      : [],
    description: String(item.description || ''),
  };
}
