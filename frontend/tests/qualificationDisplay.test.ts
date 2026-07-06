import assert from 'node:assert/strict';
import { test } from 'node:test';
import { getQualificationExpiryDisplay } from '../src/pages/qualificationDisplay.ts';

test('待补全资质的有效期显示为待补全而不是长期有效', () => {
  const display = getQualificationExpiryDisplay(
    { expiry_date: null, status: 'needs_completion' },
    (value) => value,
  );

  assert.equal(display.text, '待补全');
  assert.equal(display.color, '#F57C00');
});

test('无有效期的有效资质显示长期有效', () => {
  const display = getQualificationExpiryDisplay(
    { expiry_date: null, status: 'valid' },
    (value) => value,
  );

  assert.equal(display.text, '长期有效');
});
