import type { MatchEvidenceItem, MatchStatus } from '../types';

export interface MatchExplanationInput {
  matchStatus: MatchStatus;
  reason: string | null;
  mismatchDetail: string | null;
  evidenceItems: MatchEvidenceItem[];
  inKnowledgeBase: boolean | null;
}

export interface MatchExplanation {
  title: string;
  basis: string;
  action: string;
}

const unique = (items: string[]) => Array.from(new Set(items.filter(Boolean)));

const getEvidenceSummaryText = (
  evidenceItems: MatchEvidenceItem[],
  inKnowledgeBase: boolean | null,
): string => {
  const missingLabels = unique(
    evidenceItems
      .filter((item) => item.status === 'fail')
      .map((item) => item.label || item.check_key),
  );
  const reviewLabels = unique(
    evidenceItems
      .filter((item) => item.status === 'unknown')
      .map((item) => item.label || item.check_key),
  );
  const passedLabels = unique(
    evidenceItems
      .filter((item) => item.status === 'pass')
      .map((item) => item.label || item.check_key),
  );

  if (inKnowledgeBase === false && missingLabels.length === 0) {
    missingLabels.push('资质库未找到相关证据');
  }
  if (missingLabels.length > 0) return `缺失或不满足：${missingLabels.join('、')}`;
  if (reviewLabels.length > 0) return `需复核：${reviewLabels.join('、')}`;
  if (passedLabels.length > 0) return `证据通过：${passedLabels.join('、')}`;
  return '暂无结构化证据项';
};

export function getMatchExplanation(input: MatchExplanationInput): MatchExplanation {
  const evidenceSummaryText = getEvidenceSummaryText(input.evidenceItems, input.inKnowledgeBase);
  const basis = [input.reason, input.mismatchDetail, evidenceSummaryText]
    .map((item) => item?.trim())
    .filter(Boolean)
    .join('；');

  if (input.matchStatus === 'unmatched') {
    return {
      title: '判定不符合',
      basis: basis || '存在缺失或不满足的关键证据。',
      action: '需要补充或更换对应资质证据，不能直接按符合处理。',
    };
  }

  if (input.matchStatus === 'needs_review') {
    return {
      title: '暂不能自动判定',
      basis: basis || '证据不足或字段无法可靠识别。',
      action: '需要人工查看标书原文和资质证据后确认，系统不会自动升级为符合。',
    };
  }

  return {
    title: '可初步判定符合',
    basis: basis || '已有结构化证据支持当前结论。',
    action: '建议保留人工抽查，尤其是硬性要求或高风险项目。',
  };
}
