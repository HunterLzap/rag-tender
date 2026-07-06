import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  EMPTY_PERFORMANCE_PROJECT_FORM,
  buildPerformanceProjectPayload,
} from '../src/pages/performanceProjectForm.ts';

test('业绩项目表单默认值为空', () => {
  assert.equal(EMPTY_PERFORMANCE_PROJECT_FORM.project_name, '');
  assert.deepEqual(EMPTY_PERFORMANCE_PROJECT_FORM.file_ids, []);
});

test('业绩项目 payload 会清理空白项目名称并保留文件 ID', () => {
  const payload = buildPerformanceProjectPayload({
    ...EMPTY_PERFORMANCE_PROJECT_FORM,
    project_name: '  智慧园区项目  ',
    contract_amount: '120万元',
    file_ids: [1, 2],
  });
  assert.equal(payload.project_name, '智慧园区项目');
  assert.equal(payload.contract_amount, '120万元');
  assert.deepEqual(payload.file_ids, [1, 2]);
});
