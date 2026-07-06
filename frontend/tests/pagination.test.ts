import assert from 'node:assert/strict';
import test from 'node:test';

import { clampPage, paginateItems } from '../src/utils/pagination.ts';

test('通用分页每页返回10条并保留连续范围', () => {
  const items = Array.from({ length: 25 }, (_, index) => index + 1);

  const result = paginateItems(items, 2, 10);

  assert.deepEqual(result.items, [11, 12, 13, 14, 15, 16, 17, 18, 19, 20]);
  assert.equal(result.page, 2);
  assert.equal(result.pageCount, 3);
  assert.equal(result.startIndex, 10);
  assert.equal(result.endIndex, 20);
  assert.equal(result.total, 25);
});

test('通用分页在数据减少后校正页码', () => {
  assert.equal(clampPage(4, 21, 10), 3);
  assert.equal(clampPage(2, 0, 10), 1);
});
