import assert from 'node:assert/strict';
import { test } from 'node:test';
import { getDefaultFileUploadCategoryOptions } from '../src/components/fileUploaderCategories.ts';

test('普通资质上传分类不包含业绩', () => {
  const values = getDefaultFileUploadCategoryOptions().map((option) => option.value);
  assert.deepEqual(values, ['enterprise', 'personnel', 'financial']);
});
