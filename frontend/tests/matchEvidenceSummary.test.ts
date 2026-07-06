import assert from 'node:assert/strict';
import test from 'node:test';

import { getMatchEvidenceSummary } from '../src/components/matchEvidenceSummary.ts';
import type { MatchEvidenceItem } from '../src/types/index.ts';

const evidence = (
  overrides: Partial<MatchEvidenceItem> = {},
): MatchEvidenceItem => ({
  check_key: 'license',
  label: '营业执照',
  expected_value: '有效营业执照',
  actual_value: null,
  status: 'unknown',
  reason: null,
  critical: true,
  ...overrides,
});

test('证据摘要将失败项归入缺失或不满足', () => {
  const summary = getMatchEvidenceSummary({
    evidenceItems: [
      evidence({
        label: '社保证明',
        status: 'fail',
        expected_value: '近三个月社保',
        actual_value: null,
      }),
    ],
    inKnowledgeBase: true,
  });

  assert.equal(summary.severity, 'error');
  assert.deepEqual(summary.missingLabels, ['社保证明']);
  assert.equal(summary.primaryText, '缺失或不满足：社保证明');
});

test('证据摘要将待确认项归入需复核', () => {
  const summary = getMatchEvidenceSummary({
    evidenceItems: [
      evidence({
        label: '证书有效期',
        status: 'unknown',
        actual_value: '未识别',
      }),
    ],
    inKnowledgeBase: true,
  });

  assert.equal(summary.severity, 'warning');
  assert.deepEqual(summary.reviewLabels, ['证书有效期']);
  assert.equal(summary.primaryText, '需复核：证书有效期');
});

test('资质库无命中时直接提示缺失证据', () => {
  const summary = getMatchEvidenceSummary({
    evidenceItems: [],
    inKnowledgeBase: false,
  });

  assert.equal(summary.severity, 'error');
  assert.deepEqual(summary.missingLabels, ['资质库未找到相关证据']);
});
