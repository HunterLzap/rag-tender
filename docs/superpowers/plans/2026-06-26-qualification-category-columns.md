# Qualification Category Columns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the qualification list table use category-specific headers and remove the all-category view.

**Architecture:** Keep the backend `Qualification` schema unchanged and add a small frontend table-column helper that maps each knowledge category to display labels and existing fields. `KnowledgePage` will use this helper to render headers and cells, while the category filter remains a single-category selector with `enterprise` as the default.

**Tech Stack:** React 18, TypeScript, MUI, Node built-in test runner with `--experimental-strip-types`.

---

### Task 1: Add category column definitions

**Files:**
- Create: `frontend/src/pages/knowledgeQualificationColumns.ts`
- Create: `frontend/tests/knowledgeQualificationColumns.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/knowledgeQualificationColumns.test.ts`:

```ts
import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  getQualificationColumns,
  getDefaultKnowledgeCategory,
  getQualificationCategoryOptions,
} from '../src/pages/knowledgeQualificationColumns.ts';

test('默认资质分类是企业资质', () => {
  assert.equal(getDefaultKnowledgeCategory(), 'enterprise');
});

test('分类选项不包含全部分类', () => {
  const values = getQualificationCategoryOptions().map((option) => option.value);
  assert.deepEqual(values, ['enterprise', 'personnel', 'performance', 'financial', 'other']);
});

test('企业资质显示证书字段表头', () => {
  const labels = getQualificationColumns('enterprise').map((column) => column.label);
  assert.deepEqual(labels, [
    '名称',
    '编号',
    '发证日期',
    '有效期至',
    '发证机构',
    '认证范围',
    '等级',
    '持证主体',
  ]);
});

test('财务分类显示财务语义表头', () => {
  const labels = getQualificationColumns('financial').map((column) => column.label);
  assert.deepEqual(labels, [
    '资料名称',
    '年度/编号',
    '出具日期',
    '覆盖期/有效期',
    '出具机构',
    '指标/范围',
    '结论/等级',
    '主体',
  ]);
});

test('人员分类显示人员语义表头', () => {
  const labels = getQualificationColumns('personnel').map((column) => column.label);
  assert.deepEqual(labels, [
    '人员/证书名称',
    '证书编号',
    '发证日期',
    '有效期至',
    '发证机构',
    '专业/范围',
    '等级',
    '持有人',
  ]);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd frontend
node --test --experimental-strip-types tests\knowledgeQualificationColumns.test.ts
```

Expected: FAIL because `src/pages/knowledgeQualificationColumns.ts` does not exist.

- [ ] **Step 3: Implement the helper**

Create `frontend/src/pages/knowledgeQualificationColumns.ts`:

```ts
import type { KnowledgeCategory, Qualification } from '../types';

export type QualificationCategory = KnowledgeCategory | 'other';

export type QualificationColumnKey =
  | 'name'
  | 'number'
  | 'issue_date'
  | 'expiry_date'
  | 'issuing_authority'
  | 'scope'
  | 'level'
  | 'holder';

export interface QualificationColumn {
  key: QualificationColumnKey;
  label: string;
}

export interface QualificationCategoryOption {
  value: QualificationCategory;
  label: string;
}

const DEFAULT_CATEGORY: QualificationCategory = 'enterprise';

const CATEGORY_OPTIONS: QualificationCategoryOption[] = [
  { value: 'enterprise', label: '企业资质' },
  { value: 'personnel', label: '人员资质' },
  { value: 'performance', label: '业绩' },
  { value: 'financial', label: '财务' },
  { value: 'other', label: '其他' },
];

const CATEGORY_COLUMNS: Record<QualificationCategory, QualificationColumn[]> = {
  enterprise: [
    { key: 'name', label: '名称' },
    { key: 'number', label: '编号' },
    { key: 'issue_date', label: '发证日期' },
    { key: 'expiry_date', label: '有效期至' },
    { key: 'issuing_authority', label: '发证机构' },
    { key: 'scope', label: '认证范围' },
    { key: 'level', label: '等级' },
    { key: 'holder', label: '持证主体' },
  ],
  personnel: [
    { key: 'name', label: '人员/证书名称' },
    { key: 'number', label: '证书编号' },
    { key: 'issue_date', label: '发证日期' },
    { key: 'expiry_date', label: '有效期至' },
    { key: 'issuing_authority', label: '发证机构' },
    { key: 'scope', label: '专业/范围' },
    { key: 'level', label: '等级' },
    { key: 'holder', label: '持有人' },
  ],
  performance: [
    { key: 'name', label: '项目/业绩名称' },
    { key: 'number', label: '合同/项目编号' },
    { key: 'issue_date', label: '签订/开始日期' },
    { key: 'expiry_date', label: '完成/有效期' },
    { key: 'issuing_authority', label: '业主/发包方' },
    { key: 'scope', label: '项目范围' },
    { key: 'level', label: '金额/等级' },
    { key: 'holder', label: '主体' },
  ],
  financial: [
    { key: 'name', label: '资料名称' },
    { key: 'number', label: '年度/编号' },
    { key: 'issue_date', label: '出具日期' },
    { key: 'expiry_date', label: '覆盖期/有效期' },
    { key: 'issuing_authority', label: '出具机构' },
    { key: 'scope', label: '指标/范围' },
    { key: 'level', label: '结论/等级' },
    { key: 'holder', label: '主体' },
  ],
  other: [
    { key: 'name', label: '名称' },
    { key: 'number', label: '编号' },
    { key: 'issue_date', label: '日期' },
    { key: 'expiry_date', label: '有效期' },
    { key: 'issuing_authority', label: '来源/机构' },
    { key: 'scope', label: '内容摘要' },
    { key: 'level', label: '等级/类型' },
    { key: 'holder', label: '主体' },
  ],
};

export const getDefaultKnowledgeCategory = (): QualificationCategory => DEFAULT_CATEGORY;

export const getQualificationCategoryOptions = (): QualificationCategoryOption[] =>
  CATEGORY_OPTIONS;

export const getQualificationColumns = (
  category: QualificationCategory,
): QualificationColumn[] => CATEGORY_COLUMNS[category];

export const getQualificationCellValue = (
  qualification: Qualification,
  key: QualificationColumnKey,
): string | null => qualification[key];
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
cd frontend
node --test --experimental-strip-types tests\knowledgeQualificationColumns.test.ts
```

Expected: PASS.

### Task 2: Wire dynamic columns into KnowledgePage

**Files:**
- Modify: `frontend/src/pages/KnowledgePage.tsx`
- Test: `frontend/tests/knowledgeQualificationColumns.test.ts`

- [ ] **Step 1: Update imports and category state**

Use:

```ts
import {
  getDefaultKnowledgeCategory,
  getQualificationCategoryOptions,
  getQualificationColumns,
  getQualificationCellValue,
} from './knowledgeQualificationColumns';
```

Change `qualCategory` state from:

```ts
const [qualCategory, setQualCategory] = useState<KnowledgeCategory | 'all'>('all');
```

to:

```ts
const [qualCategory, setQualCategory] = useState<KnowledgeCategory | 'other'>(
  getDefaultKnowledgeCategory(),
);
```

- [ ] **Step 2: Update the qualification list loader**

Change:

```ts
const list = await getQualifications(qualCategory);
```

Keep the call as-is because `qualCategory` is now always a concrete category.

- [ ] **Step 3: Add computed columns**

Add:

```ts
const qualificationColumns = useMemo(
  () => getQualificationColumns(qualCategory),
  [qualCategory],
);
```

- [ ] **Step 4: Remove the all-category menu item**

Replace the `CATEGORY_OPTIONS.map` usage in the qualification filter with:

```tsx
{getQualificationCategoryOptions().map((opt) => (
  <MenuItem key={opt.value} value={opt.value}>
    {opt.label}
  </MenuItem>
))}
```

Remove:

```tsx
<MenuItem value="all">全部分类</MenuItem>
```

- [ ] **Step 5: Render headers from the active category**

Replace the fixed qualification headers with:

```tsx
{qualificationColumns.map((column) => (
  <TableCell key={column.key} sx={{ fontWeight: 600, color: '#666' }}>
    {column.label}
  </TableCell>
))}
<TableCell sx={{ fontWeight: 600, color: '#666' }}>操作</TableCell>
```

- [ ] **Step 6: Render cells from the active category**

Replace the fixed qualification cells with a column map that preserves the existing date display behavior:

```tsx
{qualificationColumns.map((column) => {
  if (column.key === 'issue_date') {
    return (
      <TableCell key={column.key} sx={{ color: '#666' }}>
        {qual.issue_date ? formatDate(qual.issue_date) : '—'}
      </TableCell>
    );
  }
  if (column.key === 'expiry_date') {
    return (
      <TableCell key={column.key}>
        <Typography
          variant="body2"
          sx={{ color: qualStatusCfg.color, fontWeight: 500 }}
        >
          {qual.expiry_date ? formatDate(qual.expiry_date) : '长期有效'}
        </Typography>
      </TableCell>
    );
  }
  const value = getQualificationCellValue(qual, column.key);
  return (
    <TableCell
      key={column.key}
      sx={{
        color: column.key === 'name' ? '#333' : '#666',
        fontWeight: column.key === 'name' ? 500 : 400,
      }}
    >
      {value || '—'}
    </TableCell>
  );
})}
```

- [ ] **Step 7: Run focused tests**

Run:

```powershell
cd frontend
node --test --experimental-strip-types tests\knowledgeQualificationColumns.test.ts tests\pagination.test.ts
```

Expected: PASS.

### Task 3: Full verification and docs

**Files:**
- Modify: `PROGRESS.md`

- [ ] **Step 1: Run TypeScript build**

Run:

```powershell
cd frontend
npx tsc -b
```

Expected: exit code 0.

- [ ] **Step 2: Run production build**

Run:

```powershell
cd frontend
npm run build
```

Expected: exit code 0. Existing chunk-size warnings are acceptable.

- [ ] **Step 3: Update progress log**

Append a short entry to `PROGRESS.md` stating that the qualification list no longer has all-category mode and now uses category-specific headers.
