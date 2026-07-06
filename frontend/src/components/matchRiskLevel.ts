import type { MatchEvidenceItem, MatchStatus } from '../types';

export type MatchRiskLevel = 'hard_blocker' | 'hard_review' | 'high' | 'medium' | 'low';

export interface MatchRisk {
  level: MatchRiskLevel;
  label: string;
  action: string;
}

interface MatchRiskInput {
  isHardRequirement: boolean;
  matchStatus: MatchStatus;
  evidenceItems: MatchEvidenceItem[];
  inKnowledgeBase: boolean | null;
}

export function getMatchRiskLevel(input: MatchRiskInput): MatchRisk {
  const hasCriticalFail = input.evidenceItems.some(
    (item) => item.status === 'fail' && item.critical,
  );
  const hasAnyFail = input.evidenceItems.some((item) => item.status === 'fail');
  const hasUnknown = input.evidenceItems.some((item) => item.status === 'unknown');
  const missingKnowledgeEvidence = input.inKnowledgeBase === false;

  if (
    input.isHardRequirement &&
    (input.matchStatus === 'unmatched' || hasCriticalFail || missingKnowledgeEvidence)
  ) {
    return {
      level: 'hard_blocker',
      label: '硬性高风险',
      action: '硬性要求存在关键证据缺失或不满足，不得直接判定符合。',
    };
  }

  if (input.isHardRequirement && (input.matchStatus === 'needs_review' || hasUnknown)) {
    return {
      level: 'hard_review',
      label: '硬性待复核',
      action: '硬性要求证据尚不完整，需要人工核验后才能定稿。',
    };
  }

  if (input.matchStatus === 'unmatched' || hasAnyFail || missingKnowledgeEvidence) {
    return {
      level: 'high',
      label: '高风险',
      action: '存在证据缺失或不满足，建议补齐材料后重新匹配。',
    };
  }

  if (input.matchStatus === 'needs_review' || hasUnknown) {
    return {
      level: 'medium',
      label: '中风险',
      action: '存在待确认字段，需要人工复核。',
    };
  }

  return {
    level: 'low',
    label: '低风险',
    action: '当前证据支持初步符合，建议保留抽查。',
  };
}
