import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  getCurrentPageSelectionState,
  toggleCurrentPageSelection,
  toggleQualificationSelection,
  getBulkDeletePreview,
} from '../src/pages/knowledgeBulkActions.ts';
import type { Qualification } from '../src/types/index.ts';

const makeQualification = (
  id: number,
  fileId: number | null,
  name = `资质${id}`,
): Qualification => ({
  id,
  file_id: fileId,
  name,
  number: `NO-${id}`,
  issue_date: null,
  expiry_date: null,
  issuing_authority: '',
  scope: '',
  level: '',
  holder: '',
  category: 'personnel',
  status: 'valid',
  raw_text: null,
  created_at: '2026-06-26 10:00:00',
});

test('单条选择可切换选中状态', () => {
  assert.deepEqual([...toggleQualificationSelection(new Set(), 1)], [1]);
  assert.deepEqual([...toggleQualificationSelection(new Set([1]), 1)], []);
});

test('当前页全选只影响当前页并保留跨页选择', () => {
  const currentPage = [makeQualification(1, 10), makeQualification(2, 20)];
  const selected = toggleCurrentPageSelection(new Set([99]), currentPage);
  assert.deepEqual([...selected].sort((a, b) => a - b), [1, 2, 99]);

  const cleared = toggleCurrentPageSelection(selected, currentPage);
  assert.deepEqual([...cleared], [99]);
});

test('当前页选择状态区分全选、半选和未选', () => {
  const currentPage = [makeQualification(1, 10), makeQualification(2, 20)];
  assert.deepEqual(getCurrentPageSelectionState(new Set(), currentPage), {
    checked: false,
    indeterminate: false,
  });
  assert.deepEqual(getCurrentPageSelectionState(new Set([1]), currentPage), {
    checked: false,
    indeterminate: true,
  });
  assert.deepEqual(getCurrentPageSelectionState(new Set([1, 2]), currentPage), {
    checked: true,
    indeterminate: false,
  });
});

test('批量删除预览按源文件去重并统计无源文件资质', () => {
  const selected = [
    makeQualification(1, 10),
    makeQualification(2, 10),
    makeQualification(3, null),
  ];
  assert.deepEqual(getBulkDeletePreview(selected), {
    sourceFileCount: 1,
    manualQualificationCount: 1,
    selectedQualificationCount: 3,
  });
});
