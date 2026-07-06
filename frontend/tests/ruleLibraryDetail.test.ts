import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  canMergeRuleInto,
  canCreateRuleDraftFromTemplate,
  canPublishSimilarRuleDraft,
  canRollbackCustomRule,
  canUpdateCustomRule,
  getRuleSuggestionQualityLabel,
  getRuleRelationDirectionLabel,
  getRuleRelationTypeLabel,
  getRuleDraftStatusLabel,
  getRuleImpactNotice,
  getRuleTypeLabel,
} from '../src/pages/ruleLibraryDetail.ts';

test('收紧规则详情说明只降级自动符合结果', () => {
  assert.equal(getRuleTypeLabel('tighten_rule'), '收紧规则');
  assert.equal(
    getRuleImpactNotice('tighten_rule'),
    '命中后只会把自动符合降级为需确认，不会自动判定为符合或不符合。',
  );
});

test('规则草案状态使用审核语义展示', () => {
  assert.equal(getRuleDraftStatusLabel('pending_review'), '待审核');
  assert.equal(getRuleDraftStatusLabel('published'), '已发布');
  assert.equal(getRuleDraftStatusLabel('rejected'), '已驳回');
});

test('相似规则仍然发布时必须填写差异说明', () => {
  assert.equal(canPublishSimilarRuleDraft(''), false);
  assert.equal(canPublishSimilarRuleDraft('   '), false);
  assert.equal(canPublishSimilarRuleDraft('适用对象不同，仍需单独发布'), true);
});

test('规则关系使用可追溯语义展示', () => {
  assert.equal(getRuleRelationTypeLabel('similar_to'), '相似规则');
  assert.equal(getRuleRelationTypeLabel('duplicate_of'), '复用已有规则');
  assert.equal(getRuleRelationDirectionLabel('outgoing'), '本规则关联到');
  assert.equal(getRuleRelationDirectionLabel('incoming'), '其他规则关联到本规则');
});

test('只允许自定义规则归并到已存在规则', () => {
  assert.equal(canMergeRuleInto('custom.rule_draft.1', 'custom.rule_draft.2'), true);
  assert.equal(canMergeRuleInto('custom.rule_draft.1', 'submission.red_flag.deposit'), true);
  assert.equal(canMergeRuleInto('submission.red_flag.deposit', 'custom.rule_draft.2'), false);
  assert.equal(canMergeRuleInto('custom.rule_draft.1', 'custom.rule_draft.1'), false);
  assert.equal(canMergeRuleInto('custom.rule_draft.1', 'draft.3'), false);
});

test('只有自定义规则且修改原因完整时允许编辑发布规则', () => {
  assert.equal(canUpdateCustomRule('custom.rule_draft.1', '名称', 'tighten_rule', '说明', '补充证据要求'), true);
  assert.equal(canUpdateCustomRule('submission.red_flag.deposit', '名称', 'tighten_rule', '说明', '补充证据要求'), false);
  assert.equal(canUpdateCustomRule('custom.rule_draft.1', '', 'tighten_rule', '说明', '补充证据要求'), false);
  assert.equal(canUpdateCustomRule('custom.rule_draft.1', '名称', 'tighten_rule', '说明', ''), false);
});

test('只有自定义规则且回滚原因完整时允许回滚版本', () => {
  assert.equal(canRollbackCustomRule('custom.rule_draft.1', 1, '恢复到较稳妥版本'), true);
  assert.equal(canRollbackCustomRule('submission.red_flag.deposit', 1, '恢复到较稳妥版本'), false);
  assert.equal(canRollbackCustomRule('custom.rule_draft.1', 0, '恢复到较稳妥版本'), false);
  assert.equal(canRollbackCustomRule('custom.rule_draft.1', 1, ''), false);
});

test('规则建议质量状态使用审核语义展示', () => {
  assert.equal(getRuleSuggestionQualityLabel('actionable'), '可执行建议');
  assert.equal(getRuleSuggestionQualityLabel('low_quality'), '信息不足');
  assert.equal(getRuleSuggestionQualityLabel(''), '待评估');
});

test('从模板生成规则草案必须填写使用原因', () => {
  assert.equal(canCreateRuleDraftFromTemplate(''), false);
  assert.equal(canCreateRuleDraftFromTemplate('   '), false);
  assert.equal(canCreateRuleDraftFromTemplate('本项目需要补充证据核验口径'), true);
});
