import assert from 'node:assert/strict';
import { test } from 'node:test';

import { getRuleLibraryTabCounts } from '../src/pages/ruleLibraryTabs.ts';

test('规则库标签页统计五类数据数量', () => {
  const counts = getRuleLibraryTabCounts({
    rules: [1, 2, 3],
    suggestions: [1],
    drafts: [1, 2],
    changes: [],
    templates: [1, 2, 3, 4],
  });

  assert.deepEqual(counts, {
    rules: 3,
    suggestions: 1,
    drafts: 2,
    changes: 0,
    templates: 4,
  });
});
