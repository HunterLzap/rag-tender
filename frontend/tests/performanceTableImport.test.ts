import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  attachPerformanceFilesToProjects,
  getUnlinkedPerformanceFiles,
  parsePerformanceProjectTable,
} from '../src/pages/performanceTableImport.ts';
import type { KnowledgeFile, PerformanceProject } from '../src/types/index.ts';

test('按中文表头解析制表符表格', () => {
  const result = parsePerformanceProjectTable(
    [
      '项目名称\t甲方\t合同编号\t合同金额\t签订日期\t验收日期\t项目内容\t年度\t备注',
      '智慧园区项目\t某某公司\tHT-001\t120万元\t2024-01-02\t2024-10-01\t弱电智能化\t2024\t重点业绩',
    ].join('\n'),
  );

  assert.equal(result.errors.length, 0);
  assert.equal(result.projects.length, 1);
  assert.deepEqual(result.projects[0], {
    project_name: '智慧园区项目',
    client_name: '某某公司',
    contract_no: 'HT-001',
    contract_amount: '120万元',
    sign_date: '2024-01-02',
    completion_date: '2024-10-01',
    project_scope: '弱电智能化',
    year: '2024',
    file_ids: [],
    remark: '重点业绩',
  });
});

test('跳过没有项目名称的空行并报告无有效数据', () => {
  const result = parsePerformanceProjectTable('项目名称\t甲方\n\t某公司');
  assert.equal(result.projects.length, 0);
  assert.deepEqual(result.errors, ['未解析到有效业绩项目']);
});

test('缺少项目名称表头时返回错误', () => {
  const result = parsePerformanceProjectTable('甲方\t合同金额\n某公司\t20万元');
  assert.equal(result.projects.length, 0);
  assert.deepEqual(result.errors, ['表头缺少“项目名称/项目/业绩名称”列']);
});

test('按合同编号或项目名称自动关联业绩文件', () => {
  const projects = parsePerformanceProjectTable(
    '项目名称\t甲方\t合同编号\n智慧园区项目\t某某公司\tHT-001\n数据中心运维\t另一公司\tHT-002',
  ).projects;
  const files = [
    knowledgeFile(11, 'HT-001_智慧园区项目_合同.pdf'),
    knowledgeFile(12, '数据中心运维_验收报告.pdf'),
    knowledgeFile(13, '无关资料.pdf'),
  ];

  const attached = attachPerformanceFilesToProjects(projects, files);

  assert.deepEqual(attached.map((project) => project.file_ids), [[11], [12]]);
});

test('找出没有被任何业绩项目关联的业绩文件', () => {
  const files = [
    knowledgeFile(11, 'HT-001_智慧园区项目_合同.pdf'),
    knowledgeFile(12, '数据中心运维_验收报告.pdf'),
    knowledgeFile(13, '无关资料.pdf'),
  ];
  const projects = [
    performanceProject(1, [11]),
    performanceProject(2, [12, 999]),
  ];

  const unlinked = getUnlinkedPerformanceFiles(files, projects);

  assert.deepEqual(unlinked.map((file) => file.id), [13]);
});

function knowledgeFile(id: number, filename: string): KnowledgeFile {
  return {
    id,
    filename,
    file_type: 'pdf',
    category: 'performance',
    file_path: '',
    status: 'completed',
    upload_time: '2026-06-26 10:00',
    parsed_at: null,
    created_at: '2026-06-26 10:00',
  };
}

function performanceProject(id: number, fileIds: number[]): PerformanceProject {
  return {
    id,
    project_name: `项目${id}`,
    client_name: null,
    contract_no: null,
    contract_amount: null,
    sign_date: null,
    completion_date: null,
    project_scope: null,
    year: null,
    file_ids: fileIds,
    remark: null,
    created_at: '2026-06-26 10:00',
    updated_at: '2026-06-26 10:00',
  };
}
