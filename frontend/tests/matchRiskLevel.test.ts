import assert from 'node:assert/strict';
import test from 'node:test';

import { getMatchRiskLevel } from '../src/components/matchRiskLevel.ts';
import type { MatchEvidenceItem } from '../src/types/index.ts';

const evidence = (
  overrides: Partial<MatchEvidenceItem> = {},
): MatchEvidenceItem => ({
  check_key: 'license',
  label: '营业执照',
  expected_value: '有效营业执照',
  actual_value: null,
  status: 'fail',
  reason: null,
  critical: true,
  ...overrides,
});

test('硬性要求存在关键失败证据时标记为硬性高风险', () => {
  const risk = getMatchRiskLevel({
    isHardRequirement: true,
    matchStatus: 'unmatched',
    evidenceItems: [evidence({ label: '社保证明', critical: true })],
    inKnowledgeBase: true,
  });

  assert.equal(risk.level, 'hard_blocker');
  assert.equal(risk.label, '硬性高风险');
  assert.match(risk.action, /不得直接判定符合/);
});

test('硬性要求待确认时标记为硬性待复核', () => {
  const risk = getMatchRiskLevel({
    isHardRequirement: true,
    matchStatus: 'needs_review',
    evidenceItems: [evidence({ status: 'unknown', label: '证书有效期' })],
    inKnowledgeBase: true,
  });

  assert.equal(risk.level, 'hard_review');
  assert.equal(risk.label, '硬性待复核');
});

test('非硬性要求待确认时标记为中风险', () => {
  const risk = getMatchRiskLevel({
    isHardRequirement: false,
    matchStatus: 'needs_review',
    evidenceItems: [evidence({ status: 'unknown', critical: false })],
    inKnowledgeBase: true,
  });

  assert.equal(risk.level, 'medium');
  assert.equal(risk.label, '中风险');
});

test('证据通过且已匹配时标记为低风险', () => {
  const risk = getMatchRiskLevel({
    isHardRequirement: true,
    matchStatus: 'matched',
    evidenceItems: [evidence({ status: 'pass', actual_value: '有效营业执照' })],
    inKnowledgeBase: true,
  });

  assert.equal(risk.level, 'low');
  assert.equal(risk.label, '低风险');
});
