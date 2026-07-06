import assert from 'node:assert/strict';
import { test } from 'node:test';
import { shouldClearSelectedFiles } from '../src/components/fileUploaderClearSignal.ts';

test('首次渲染不因为 clearKey 初始化而清空文件', () => {
  assert.equal(shouldClearSelectedFiles(undefined, 0), false);
});

test('clearKey 未变化时不清空文件', () => {
  assert.equal(shouldClearSelectedFiles(3, 3), false);
});

test('clearKey 变化时清空文件', () => {
  assert.equal(shouldClearSelectedFiles(3, 4), true);
});

test('未传 clearKey 时不清空文件', () => {
  assert.equal(shouldClearSelectedFiles(3, undefined), false);
});
