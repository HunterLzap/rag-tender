import type {
  MatchEvidenceItem,
  MatchEvidenceStatus,
  MatchResult,
  MatchStatus,
  Qualification,
  RequirementCategory,
  RequirementNature,
  RequirementReviewStatus,
  TenderRequirement,
} from '../types/index.ts';

export type RequirementReviewState =
  | 'all'
  | 'pending'
  | 'location_failed'
  | 'confirmed';

export interface RequirementReviewFilters {
  category: RequirementCategory | 'all';
  state: RequirementReviewState;
  keyword: string;
}

type UnknownRequirement = Record<string, unknown>;
type UnknownMatchResult = Record<string, unknown>;

const normalizeEvidenceItem = (raw: unknown): MatchEvidenceItem | null => {
  if (!raw || typeof raw !== 'object') return null;
  const item = raw as Record<string, unknown>;
  const rawStatus = item.status;
  const status: MatchEvidenceStatus =
    rawStatus === 'pass' || rawStatus === 'fail' ? rawStatus : 'unknown';

  return {
    check_key: String(item.check_key || ''),
    label: String(item.label || item.check_key || '核验项'),
    expected_value:
      item.expected_value == null ? null : String(item.expected_value),
    actual_value: item.actual_value == null ? null : String(item.actual_value),
    status,
    reason: item.reason == null ? null : String(item.reason),
    critical: item.critical == null ? true : Boolean(item.critical),
  };
};
type UnknownQualification = Record<string, unknown>;

export type MatchResultFilter = MatchStatus | 'all' | 'missing';

const CATEGORIES = new Set<RequirementCategory>([
  'qualification',
  'performance',
  'financial',
  'personnel',
  'other',
  'product_spec',
  'submission',
]);

const NATURES = new Set<RequirementNature>(['capability', 'submission']);

export const normalizeRequirement = (
  raw: unknown,
): TenderRequirement => {
  const item = raw as UnknownRequirement;
  const category = CATEGORIES.has(item.category as RequirementCategory)
    ? (item.category as RequirementCategory)
    : 'other';
  const nature: RequirementNature = NATURES.has(
    item.requirement_nature as RequirementNature,
  )
    ? (item.requirement_nature as RequirementNature)
    : 'capability';
  const reviewStatus: RequirementReviewStatus =
    item.review_status === 'confirmed' ? 'confirmed' : 'pending';

  return {
    id: Number(item.id),
    tender_id: Number(item.tender_id),
    category,
    requirement_nature: nature,
    title: String(item.title || ''),
    content: String(item.content || ''),
    is_hard: Boolean(item.is_hard),
    raw_text: String(item.raw_text || item.source_text || ''),
    page_number:
      item.page_number == null && item.source_page == null
        ? null
        : Number(item.page_number ?? item.source_page),
    numeric_value:
      item.numeric_value == null ? null : String(item.numeric_value),
    numeric_operator:
      item.numeric_operator == null ? null : String(item.numeric_operator),
    numeric_unit:
      item.numeric_unit == null ? null : String(item.numeric_unit),
    review_status: reviewStatus,
  };
};

const normalizeQualification = (raw: unknown): Qualification | null => {
  if (!raw || typeof raw !== 'object') return null;
  const item = raw as UnknownQualification;
  return {
    id: Number(item.id),
    file_id: item.file_id == null ? null : Number(item.file_id),
    name: item.name == null ? '' : String(item.name),
    number: item.number == null ? '' : String(item.number),
    issue_date: item.issue_date == null ? null : String(item.issue_date),
    expiry_date: item.expiry_date == null ? null : String(item.expiry_date),
    issuing_authority:
      item.issuing_authority == null ? '' : String(item.issuing_authority),
    scope: item.scope == null ? '' : String(item.scope),
    level: item.level == null ? '' : String(item.level),
    holder: item.holder == null ? '' : String(item.holder),
    category:
      item.category === 'enterprise' ||
      item.category === 'personnel' ||
      item.category === 'performance' ||
      item.category === 'financial'
        ? item.category
        : 'other',
    status:
      item.status === 'valid' ||
      item.status === 'expiring' ||
      item.status === 'expired' ||
      item.status === 'needs_completion'
        ? item.status
        : 'needs_completion',
    raw_text: item.raw_text == null ? null : String(item.raw_text),
    created_at: String(item.created_at || ''),
  };
};

export const normalizeMatchResult = (raw: unknown): MatchResult => {
  const item = raw as UnknownMatchResult;
  const rawStatus = item.match_status ?? item.status;
  const matchStatus: MatchStatus =
    rawStatus === 'matched' || rawStatus === 'unmatched'
      ? rawStatus
      : 'needs_review';

  return {
    id: Number(item.id),
    tender_id: Number(item.tender_id),
    requirement_id: Number(item.requirement_id),
    qualification_id:
      item.qualification_id == null ? null : Number(item.qualification_id),
    match_status: matchStatus,
    reason: String(item.reason || ''),
    mismatch_detail:
      item.mismatch_detail == null ? null : String(item.mismatch_detail),
    expected_qualification:
      item.expected_qualification == null
        ? null
        : String(item.expected_qualification),
    in_knowledge_base:
      item.in_knowledge_base == null ? null : Boolean(item.in_knowledge_base),
    similarity_score: Number(item.similarity_score || 0),
    evidence_items: Array.isArray(item.evidence_items)
      ? item.evidence_items
          .map(normalizeEvidenceItem)
          .filter((evidence): evidence is MatchEvidenceItem => evidence !== null)
      : [],
    confirmed_status:
      item.confirmed_status === 'matched' ||
      item.confirmed_status === 'unmatched' ||
      item.confirmed_status === 'needs_review' ||
      item.confirmed_status === 'confirmed'
        ? item.confirmed_status
        : null,
    created_at: String(item.created_at || ''),
    requirement:
      item.requirement && typeof item.requirement === 'object'
        ? normalizeRequirement(item.requirement)
        : undefined,
    qualification:
      item.qualification && typeof item.qualification === 'object'
        ? normalizeQualification(item.qualification)
        : null,
  };
};

export const getRequirementReviewState = (
  requirement: TenderRequirement,
): Exclude<RequirementReviewState, 'all'> => {
  if (!requirement.page_number) return 'location_failed';
  return requirement.review_status;
};

const REVIEW_PRIORITY: Record<
  Exclude<RequirementReviewState, 'all'>,
  number
> = {
  location_failed: 0,
  pending: 1,
  confirmed: 2,
};

export const sortRequirementsForReview = (
  requirements: TenderRequirement[],
): TenderRequirement[] =>
  [...requirements].sort((left, right) => {
    const stateDelta =
      REVIEW_PRIORITY[getRequirementReviewState(left)] -
      REVIEW_PRIORITY[getRequirementReviewState(right)];
    if (stateDelta !== 0) return stateDelta;
    const leftPage = left.page_number ?? Number.MAX_SAFE_INTEGER;
    const rightPage = right.page_number ?? Number.MAX_SAFE_INTEGER;
    return leftPage - rightPage || left.id - right.id;
  });

export const filterRequirements = (
  requirements: TenderRequirement[],
  filters: RequirementReviewFilters,
): TenderRequirement[] => {
  const keyword = filters.keyword.trim().toLocaleLowerCase();

  return sortRequirementsForReview(
    requirements.filter((requirement) => {
      if (
        filters.category !== 'all' &&
        requirement.category !== filters.category
      ) {
        return false;
      }
      if (
        filters.state !== 'all' &&
        getRequirementReviewState(requirement) !== filters.state
      ) {
        return false;
      }
      if (!keyword) return true;
      return [
        requirement.title,
        requirement.content,
        requirement.raw_text,
        requirement.numeric_value,
      ].some((value) => value?.toLocaleLowerCase().includes(keyword));
    }),
  );
};

export const getRequirementReviewCounts = (
  requirements: TenderRequirement[],
) => ({
  all: requirements.length,
  pending: requirements.filter(
    (item) => getRequirementReviewState(item) === 'pending',
  ).length,
  location_failed: requirements.filter(
    (item) => getRequirementReviewState(item) === 'location_failed',
  ).length,
  confirmed: requirements.filter(
    (item) => getRequirementReviewState(item) === 'confirmed',
  ).length,
});

const MATCH_PRIORITY: Record<MatchStatus | 'missing', number> = {
  unmatched: 0,
  needs_review: 1,
  missing: 2,
  matched: 3,
};

export const getRequirementMatchStatus = (
  requirementId: number,
  results: MatchResult[],
): MatchStatus | 'missing' =>
  results.find((result) => result.requirement_id === requirementId)
    ?.match_status || 'missing';

export const sortRequirementsByMatch = (
  requirements: TenderRequirement[],
  results: MatchResult[],
): TenderRequirement[] => {
  const statusByRequirement = new Map(
    results.map((result) => [result.requirement_id, result.match_status]),
  );
  return [...requirements].sort((left, right) => {
    const leftStatus = statusByRequirement.get(left.id) || 'missing';
    const rightStatus = statusByRequirement.get(right.id) || 'missing';
    return (
      MATCH_PRIORITY[leftStatus] - MATCH_PRIORITY[rightStatus] ||
      left.id - right.id
    );
  });
};

export const filterRequirementsByMatch = (
  requirements: TenderRequirement[],
  results: MatchResult[],
  status: MatchResultFilter,
): TenderRequirement[] => {
  const sorted = sortRequirementsByMatch(requirements, results);
  if (status === 'all') return sorted;
  return sorted.filter(
    (requirement) =>
      getRequirementMatchStatus(requirement.id, results) === status,
  );
};

export const filterRequirementsByNature = (
  requirements: TenderRequirement[],
  nature: RequirementNature | 'all',
): TenderRequirement[] =>
  nature === 'all'
    ? requirements
    : requirements.filter(
        (requirement) => requirement.requirement_nature === nature,
      );
