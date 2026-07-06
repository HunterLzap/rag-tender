import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  getQualificationColumns,
  getDefaultKnowledgeCategory,
  getFinancialQualificationType,
  getFinancialTypeOptions,
  getQualificationCategoryOptions,
  getPersonnelQualificationType,
  getPersonnelTypeOptions,
  normalizeFinancialSummaryAuthority,
  summarizeFinancialQualifications,
} from '../src/pages/knowledgeQualificationColumns.ts';
import type { Qualification } from '../src/types/index.ts';

test('默认资质分类是企业资质', () => {
  assert.equal(getDefaultKnowledgeCategory(), 'enterprise');
});

test('资质分类选项不包含全部分类和业绩', () => {
  const values = getQualificationCategoryOptions().map((option) => option.value);
  assert.deepEqual(values, ['enterprise', 'personnel', 'financial', 'other']);
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

test('财务分类明细显示财务语义表头', () => {
  const labels = getQualificationColumns('financial', 'all', 'financial_report').map((column) => column.label);
  assert.deepEqual(labels, [
    '报告类型',
    '会计期间/年度',
    '申报/出具日期',
    '报告截止日',
    '申报系统/出具方',
    '关键财务指标',
    '审计结论/报表口径',
    '会计主体',
  ]);
});

test('纳税完税证明明细显示税务语义表头', () => {
  const labels = getQualificationColumns('financial', 'all', 'tax').map((column) => column.label);
  assert.deepEqual(labels, [
    '证明类型',
    '证明/凭证编号',
    '出具日期',
    '税款所属期/有效期',
    '税务机关',
    '证明内容',
    '税种/结论',
    '纳税主体',
  ]);
});

test('银行开户证明明细显示银行语义表头', () => {
  const labels = getQualificationColumns('financial', 'all', 'bank').map((column) => column.label);
  assert.deepEqual(labels, [
    '资料类型',
    '账号/许可证号',
    '出具日期',
    '有效期',
    '开户行/银行',
    '账户/资信内容',
    '账户性质/评级',
    '主体',
  ]);
});

test('财务汇总视图显示汇总语义表头', () => {
  const labels = getQualificationColumns('financial', 'all', 'summary').map((column) => column.label);
  assert.deepEqual(labels, [
    '资料类型',
    '份数/编号',
    '最近出具日期',
    '覆盖期/有效期',
    '主要出具机构',
    '覆盖内容',
    '结论/指标',
    '主体',
  ]);
});

test('人员分类显示人员语义表头', () => {
  const labels = getQualificationColumns('personnel').map((column) => column.label);
  assert.deepEqual(labels, [
    '资料类型',
    '证件/证书编号',
    '签发/出具日期',
    '有效期/截止日期',
    '出具机构/发证机关',
    '专业/岗位/证明内容',
    '级别/职称/资格',
    '人员姓名',
  ]);
});

test('人员资质支持按资料类型切换表头', () => {
  const idCardLabels = getQualificationColumns('personnel', 'identity').map((column) => column.label);
  assert.deepEqual(idCardLabels, [
    '资料类型',
    '身份证号',
    '签发日期',
    '有效期',
    '签发机关',
    '身份/角色',
    '备注',
    '人员姓名',
  ]);

  const socialSecurityLabels = getQualificationColumns('personnel', 'social_security').map((column) => column.label);
  assert.deepEqual(socialSecurityLabels, [
    '资料类型',
    '证件号/社保号',
    '出具日期',
    '缴费截止/证明期',
    '出具机构',
    '参保/缴费情况',
    '缴费期间/月数',
    '人员姓名',
  ]);
});

test('人员资质类型选项来自当前已有资料类型', () => {
  const options = getPersonnelTypeOptions([
    qualification('身份证明'),
    qualification('社保证明'),
    qualification('特种作业操作证（低压电工作业）'),
  ]);

  assert.deepEqual(options.map((option) => option.value), [
    'all',
    'identity',
    'social_security',
    'special_operation',
  ]);
});

test('根据资料名称归一化人员资料类型', () => {
  assert.equal(getPersonnelQualificationType(qualification('身份证明')), 'identity');
  assert.equal(getPersonnelQualificationType(qualification('社保证明')), 'social_security');
  assert.equal(getPersonnelQualificationType(qualification('职称/资格证明')), 'professional_title');
  assert.equal(getPersonnelQualificationType(qualification('特种作业操作证（低压电工作业）')), 'special_operation');
  assert.equal(getPersonnelQualificationType(qualification('人员证明材料')), 'other_personnel');
});

test('财务资料类型选项来自当前已有资料类型', () => {
  const options = getFinancialTypeOptions([
    financialQualification('纳税证明', '纳税/完税证明', '国家税务总局上海市嘉定区税务局第一税务'),
    financialQualification('审计报告', '2023年度；营业收入100万元', '上海某某会计师事务所'),
  ]);

  assert.deepEqual(options.map((option) => option.value), [
    'summary',
    'tax',
    'financial_report',
  ]);
});

test('根据财务资料内容归一化财务类型', () => {
  assert.equal(getFinancialQualificationType(financialQualification('纳税证明', '纳税/完税证明', '税务局')), 'tax');
  assert.equal(getFinancialQualificationType(financialQualification('审计报告', '财务审计报告', '会计师事务所')), 'financial_report');
  assert.equal(getFinancialQualificationType(financialQualification('财务会计报告（季报）', '所属期2025-10-01至2025-12-31', '电子税务局/纳税申报系统')), 'financial_report');
  assert.equal(getFinancialQualificationType(financialQualification('开户许可证', '基本存款账户', '中国工商银行')), 'bank');
  assert.equal(getFinancialQualificationType(financialQualification('其他证明', '其他', '机构')), 'other_financial');
});

test('财务汇总把同主体同机构的纳税证明聚合成一行', () => {
  const rows = summarizeFinancialQualifications([
    financialQualification('纳税证明', '纳税/完税证明', '国家税务总局上海市嘉定区税务局第一税务', 1),
    financialQualification('纳税证明', '纳税/完税证明', '国家税务总局上海市嘉定区税务局第一税务', 2),
  ]);

  assert.equal(rows.length, 1);
  assert.equal(rows[0].name, '纳税/完税证明汇总');
  assert.equal(rows[0].number, '2 份');
  assert.deepEqual(rows[0].sourceIds, [1, 2]);
});

test('财务汇总按主管税务局归一化不同税务层级', () => {
  assert.equal(
    normalizeFinancialSummaryAuthority('国家税务总局上海市嘉定区税务局第一税务'),
    '国家税务总局上海市嘉定区税务局',
  );

  const rows = summarizeFinancialQualifications([
    financialQualification('纳税证明', '纳税/完税证明', '国家税务总局上海市嘉定区税务局', 1),
    financialQualification('纳税证明', '纳税/完税证明', '国家税务总局上海市嘉定区税务局第一税务', 2),
  ]);

  assert.equal(rows.length, 1);
  assert.equal(rows[0].number, '2 份');
  assert.equal(rows[0].issuing_authority, '国家税务总局上海市嘉定区税务局');
  assert.deepEqual(rows[0].sourceIds, [1, 2]);
});

function qualification(name: string): Qualification {
  return {
    id: 1,
    file_id: 1,
    name,
    number: null,
    issue_date: null,
    expiry_date: null,
    issuing_authority: null,
    scope: null,
    level: null,
    holder: null,
    category: 'personnel',
    status: 'needs_completion',
    raw_text: null,
    created_at: '2026-06-26 10:00:00',
  };
}

function financialQualification(
  name: string,
  scope: string,
  issuingAuthority: string,
  id = 1,
): Qualification {
  return {
    id,
    file_id: id,
    name,
    number: null,
    issue_date: null,
    expiry_date: null,
    issuing_authority: issuingAuthority,
    scope,
    level: null,
    holder: '上海苏靖机电工程有限公司',
    category: 'financial',
    status: 'valid',
    raw_text: null,
    created_at: '2026-06-29 10:00:00',
  };
}
