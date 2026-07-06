import assert from 'node:assert/strict';
import test from 'node:test';

import { canSubmitMatchConfirmation } from '../src/components/matchConfirmation.ts';

test('人工确认匹配结果必须填写修正原因', () => {
  assert.equal(canSubmitMatchConfirmation(''), false);
  assert.equal(canSubmitMatchConfirmation('   '), false);
  assert.equal(canSubmitMatchConfirmation('证书范围不覆盖本项目服务内容'), true);
});
