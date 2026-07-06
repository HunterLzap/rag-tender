import assert from 'node:assert/strict';
import test from 'node:test';

import { getMatchExplanation } from '../src/components/matchExplanation.ts';
import type { MatchEvidenceItem } from '../src/types/index.ts';

const evidence = (
  overrides: Partial<MatchEvidenceItem> = {},
): MatchEvidenceItem => ({
  check_key: 'social_security',
  label: '社保证明',
  expected_value: '近三个月社保证明',
  actual_value: null,
  status: 'fail',
  reason: '未找到社保证明',
  critical: true,
  ...overrides,
});

test('不符合结果解释明确缺失证据和处理动作', () => {
  const explanation = getMatchExplanation({
    matchStatus: 'unmatched',
    reason: '证据核验未通过',
    mismatchDetail: '缺少社保证明',
    evidenceItems: [evidence()],
    inKnowledgeBase: true,
  });

  assert.equal(explanation.title, '判定不符合');
  assert.equal(explanation.basis, '证据核验未通过；缺少社保证明；缺失或不满足：社保证明');
  assert.equal(explanation.action, '需要补充或更换对应资质证据，不能直接按符合处理。');
});

test('需确认结果解释明确不能自动判符合', () => {
  const explanation = getMatchExplanation({
    matchStatus: 'needs_review',
    reason: '候选资质相似但字段不足',
    mismatchDetail: null,
    evidenceItems: [
      evidence({
        label: '证书有效期',
        status: 'unknown',
        reason: '有效期未识别',
      }),
    ],
    inKnowledgeBase: true,
  });

  assert.equal(explanation.title, '暂不能自动判定');
  assert.equal(explanation.action, '需要人工查看标书原文和资质证据后确认，系统不会自动升级为符合。');
  assert.match(explanation.basis, /需复核：证书有效期/);
});

test('符合结果解释仍保留初步判断语义', () => {
  const explanation = getMatchExplanation({
    matchStatus: 'matched',
    reason: '证据字段匹配',
    mismatchDetail: null,
    evidenceItems: [
      evidence({
        label: '营业执照',
        status: 'pass',
        actual_value: '有效营业执照',
      }),
    ],
    inKnowledgeBase: true,
  });

  assert.equal(explanation.title, '可初步判定符合');
  assert.equal(explanation.action, '建议保留人工抽查，尤其是硬性要求或高风险项目。');
});
