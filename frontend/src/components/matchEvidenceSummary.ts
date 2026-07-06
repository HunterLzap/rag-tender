import type { MatchEvidenceItem } from '../types';

export type MatchEvidenceSummarySeverity = 'error' | 'warning' | 'success' | 'info';

export interface MatchEvidenceSummary {
  severity: MatchEvidenceSummarySeverity;
  missingLabels: string[];
  reviewLabels: string[];
  passedLabels: string[];
  primaryText: string;
}

interface MatchEvidenceSummaryInput {
  evidenceItems: MatchEvidenceItem[];
  inKnowledgeBase: boolean | null;
}

const unique = (items: string[]) => Array.from(new Set(items.filter(Boolean)));

export function getMatchEvidenceSummary(input: MatchEvidenceSummaryInput): MatchEvidenceSummary {
  const missingLabels = unique(
    input.evidenceItems
      .filter((item) => item.status === 'fail')
      .map((item) => item.label || item.check_key),
  );
  const reviewLabels = unique(
    input.evidenceItems
      .filter((item) => item.status === 'unknown')
      .map((item) => item.label || item.check_key),
  );
  const passedLabels = unique(
    input.evidenceItems
      .filter((item) => item.status === 'pass')
      .map((item) => item.label || item.check_key),
  );

  if (input.inKnowledgeBase === false && missingLabels.length === 0) {
    missingLabels.push('资质库未找到相关证据');
  }

  if (missingLabels.length > 0) {
    return {
      severity: 'error',
      missingLabels,
      reviewLabels,
      passedLabels,
      primaryText: `缺失或不满足：${missingLabels.join('、')}`,
    };
  }

  if (reviewLabels.length > 0) {
    return {
      severity: 'warning',
      missingLabels,
      reviewLabels,
      passedLabels,
      primaryText: `需复核：${reviewLabels.join('、')}`,
    };
  }

  if (passedLabels.length > 0) {
    return {
      severity: 'success',
      missingLabels,
      reviewLabels,
      passedLabels,
      primaryText: `证据通过：${passedLabels.join('、')}`,
    };
  }

  return {
    severity: 'info',
    missingLabels,
    reviewLabels,
    passedLabels,
    primaryText: '暂无结构化证据项',
  };
}
