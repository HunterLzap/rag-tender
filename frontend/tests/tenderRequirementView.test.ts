import assert from 'node:assert/strict';
import test from 'node:test';

import {
  filterRequirementsByMatch,
  filterRequirementsByNature,
  filterRequirements,
  getRequirementReviewState,
  normalizeMatchResult,
  normalizeRequirement,
  sortRequirementsByMatch,
  sortRequirementsForReview,
} from '../src/pages/tenderRequirementView.ts';
import { clampPage, paginateItems } from '../src/utils/pagination.ts';
import type { MatchResult, TenderRequirement } from '../src/types/index.ts';

const requirement = (
  overrides: Partial<TenderRequirement> = {},
): TenderRequirement => ({
  id: 1,
  tender_id: 10,
  category: 'qualification',
  title: '营业执照',
  content: '须提供有效营业执照',
  is_hard: true,
  raw_text: '原始文本',
  page_number: 29,
  numeric_value: null,
  numeric_operator: null,
  numeric_unit: null,
  review_status: 'pending',
  ...overrides,
});

test('将后端 page_number/raw_text 正确映射到前端模型', () => {
  const normalized = normalizeRequirement({
    id: 15,
    tender_id: 10,
    category: 'qualification',
    title: '营业执照',
    content: '须提供营业执照',
    is_hard: 1,
    raw_text: '第29页原文',
    page_number: 29,
    numeric_value: null,
    numeric_operator: null,
    numeric_unit: null,
    review_status: 'pending',
  });

  assert.equal(normalized.page_number, 29);
  assert.equal(normalized.raw_text, '第29页原文');
  assert.equal(normalized.is_hard, true);
});

test('定位失败优先，其次待确认，最后已确认', () => {
  const sorted = sortRequirementsForReview([
    requirement({ id: 1, review_status: 'confirmed' }),
    requirement({ id: 2, review_status: 'pending' }),
    requirement({ id: 3, page_number: null, review_status: 'pending' }),
  ]);

  assert.deepEqual(sorted.map((item) => item.id), [3, 2, 1]);
  assert.equal(getRequirementReviewState(sorted[0]), 'location_failed');
});

test('支持解析状态、类别和关键词组合筛选', () => {
  const items = [
    requirement({ id: 1, category: 'qualification', review_status: 'confirmed' }),
    requirement({ id: 2, category: 'financial', title: '财务报告' }),
    requirement({ id: 3, category: 'financial', title: '注册资本', page_number: null }),
  ];

  const result = filterRequirements(items, {
    category: 'financial',
    state: 'location_failed',
    keyword: '资本',
  });
  assert.deepEqual(result.map((item) => item.id), [3]);
});

test('将后端 status 字段归一化为 match_status', () => {
  const normalized = normalizeMatchResult({
    id: 8,
    tender_id: 10,
    requirement_id: 3,
    qualification_id: 5,
    status: 'unmatched',
    reason: '等级不足',
    mismatch_detail: null,
    expected_qualification: null,
    in_knowledge_base: true,
    similarity_score: 0.82,
    confirmed_status: null,
    created_at: '2026-06-24T12:00:00',
  });

  assert.equal(normalized.match_status, 'unmatched');
  assert.equal(normalized.qualification_id, 5);
  assert.equal(normalized.reason, '等级不足');
});

test('匹配后按不匹配、待核对、无结果、已匹配排序', () => {
  const items = [
    requirement({ id: 1 }),
    requirement({ id: 2 }),
    requirement({ id: 3 }),
    requirement({ id: 4 }),
  ];
  const results: MatchResult[] = [
    matchResult({ requirement_id: 1, match_status: 'matched' }),
    matchResult({ requirement_id: 2, match_status: 'needs_review' }),
    matchResult({ requirement_id: 3, match_status: 'unmatched' }),
  ];

  assert.deepEqual(
    sortRequirementsByMatch(items, results).map((item) => item.id),
    [3, 2, 4, 1],
  );
});

test('匹配状态筛选保留对应解析项', () => {
  const items = [requirement({ id: 1 }), requirement({ id: 2 })];
  const results: MatchResult[] = [
    matchResult({ requirement_id: 1, match_status: 'matched' }),
    matchResult({ requirement_id: 2, match_status: 'unmatched' }),
  ];

  assert.deepEqual(
    filterRequirementsByMatch(items, results, 'unmatched').map(
      (item) => item.id,
    ),
    [2],
  );
});

test('支持按要求性质筛选', () => {
  const items = [
    requirement({ id: 1, requirement_nature: 'capability' }),
    requirement({ id: 2, requirement_nature: 'submission' }),
    requirement({ id: 3, requirement_nature: 'submission' }),
  ];

  assert.deepEqual(
    filterRequirementsByNature(items, 'submission').map((item) => item.id),
    [2, 3],
  );
  assert.equal(filterRequirementsByNature(items, 'all').length, 3);
});

test('每页10条且第二页序号从11开始', () => {
  const items = Array.from({ length: 25 }, (_, index) =>
    requirement({ id: index + 1 }),
  );

  const result = paginateItems(items, 2, 10);

  assert.equal(result.page, 2);
  assert.equal(result.pageCount, 3);
  assert.equal(result.startIndex, 10);
  assert.equal(result.endIndex, 20);
  assert.deepEqual(result.items.map((item) => item.id), [
    11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
  ]);
});

test('数据减少后将当前页校正到最后有效页', () => {
  assert.equal(clampPage(4, 41, 20), 3);
  assert.equal(clampPage(3, 0, 20), 1);
});

const matchResult = (
  overrides: Partial<MatchResult> = {},
): MatchResult => ({
  id: 1,
  tender_id: 10,
  requirement_id: 1,
  qualification_id: null,
  match_status: 'needs_review',
  reason: '',
  mismatch_detail: null,
  expected_qualification: null,
  in_knowledge_base: false,
  similarity_score: 0,
  confirmed_status: null,
  created_at: '',
  ...overrides,
});
