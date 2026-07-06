import assert from 'node:assert/strict';
import { test } from 'node:test';

import { isRedFlagChecklistItem } from '../src/components/submissionChecklistRisk.ts';
import type { SubmissionChecklist } from '../src/types/index.ts';

const item = (remark: string | null): SubmissionChecklist => ({
  id: 1,
  tender_id: 10,
  requirement_id: 20,
  item_name: '投标保证金',
  description: '须按时缴纳投标保证金',
  status: 'not_started',
  remark,
  created_at: '2026-07-01 10:00:00',
  updated_at: '2026-07-01 10:00:00',
});

test('备注包含红线标记时识别为红线待办', () => {
  assert.equal(isRedFlagChecklistItem(item('【红线】保证金风险')), true);
});

test('普通备注不识别为红线待办', () => {
  assert.equal(isRedFlagChecklistItem(item('请人工确认')), false);
  assert.equal(isRedFlagChecklistItem(item(null)), false);
});
