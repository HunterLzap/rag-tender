import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  getCurrentPageFileSelectionState,
  toggleCurrentPageFileSelection,
  toggleFileSelection,
} from '../src/pages/knowledgeFileBulkActions.ts';
import type { KnowledgeFile } from '../src/types/index.ts';

const makeFile = (id: number): KnowledgeFile => ({
  id,
  filename: `文件${id}.pdf`,
  file_type: 'pdf',
  category: 'enterprise',
  file_path: `D:/fake/${id}.pdf`,
  status: 'completed',
  upload_time: '2026-06-26 10:00:00',
  parsed_at: null,
  created_at: '2026-06-26 10:00:00',
});

test('文件单条选择可切换选中状态', () => {
  assert.deepEqual([...toggleFileSelection(new Set(), 1)], [1]);
  assert.deepEqual([...toggleFileSelection(new Set([1]), 1)], []);
});

test('文件当前页全选只影响当前页并保留跨页选择', () => {
  const currentPage = [makeFile(1), makeFile(2)];
  const selected = toggleCurrentPageFileSelection(new Set([99]), currentPage);
  assert.deepEqual([...selected].sort((a, b) => a - b), [1, 2, 99]);

  const cleared = toggleCurrentPageFileSelection(selected, currentPage);
  assert.deepEqual([...cleared], [99]);
});

test('文件当前页选择状态区分全选、半选和未选', () => {
  const currentPage = [makeFile(1), makeFile(2)];
  assert.deepEqual(getCurrentPageFileSelectionState(new Set(), currentPage), {
    checked: false,
    indeterminate: false,
  });
  assert.deepEqual(getCurrentPageFileSelectionState(new Set([1]), currentPage), {
    checked: false,
    indeterminate: true,
  });
  assert.deepEqual(getCurrentPageFileSelectionState(new Set([1, 2]), currentPage), {
    checked: true,
    indeterminate: false,
  });
});
