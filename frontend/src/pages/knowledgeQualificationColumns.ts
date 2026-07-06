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

export type PersonnelQualificationType =
  | 'all'
  | 'identity'
  | 'social_security'
  | 'professional_title'
  | 'special_operation'
  | 'other_personnel';

export type FinancialQualificationType =
  | 'summary'
  | 'tax'
  | 'financial_report'
  | 'bank'
  | 'other_financial';

export interface PersonnelTypeOption {
  value: PersonnelQualificationType;
  label: string;
}

export interface FinancialTypeOption {
  value: FinancialQualificationType;
  label: string;
}

const DEFAULT_CATEGORY: QualificationCategory = 'enterprise';

const CATEGORY_OPTIONS: QualificationCategoryOption[] = [
  { value: 'enterprise', label: '企业资质' },
  { value: 'personnel', label: '人员资质' },
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
    { key: 'name', label: '资料类型' },
    { key: 'number', label: '证件/证书编号' },
    { key: 'issue_date', label: '签发/出具日期' },
    { key: 'expiry_date', label: '有效期/截止日期' },
    { key: 'issuing_authority', label: '出具机构/发证机关' },
    { key: 'scope', label: '专业/岗位/证明内容' },
    { key: 'level', label: '级别/职称/资格' },
    { key: 'holder', label: '人员姓名' },
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

const PERSONNEL_TYPE_LABELS: Record<PersonnelQualificationType, string> = {
  all: '全部类型',
  identity: '身份证明',
  social_security: '社保证明',
  professional_title: '职称/资格证明',
  special_operation: '特种作业证',
  other_personnel: '其他人员证明',
};

const FINANCIAL_TYPE_LABELS: Record<FinancialQualificationType, string> = {
  summary: '汇总视图',
  tax: '纳税/完税证明明细',
  financial_report: '财务报表/审计报告明细',
  bank: '银行/开户证明',
  other_financial: '其他财务资料',
};

const PERSONNEL_TYPE_COLUMNS: Record<
  Exclude<PersonnelQualificationType, 'all'>,
  QualificationColumn[]
> = {
  identity: [
    { key: 'name', label: '资料类型' },
    { key: 'number', label: '身份证号' },
    { key: 'issue_date', label: '签发日期' },
    { key: 'expiry_date', label: '有效期' },
    { key: 'issuing_authority', label: '签发机关' },
    { key: 'scope', label: '身份/角色' },
    { key: 'level', label: '备注' },
    { key: 'holder', label: '人员姓名' },
  ],
  social_security: [
    { key: 'name', label: '资料类型' },
    { key: 'number', label: '证件号/社保号' },
    { key: 'issue_date', label: '出具日期' },
    { key: 'expiry_date', label: '缴费截止/证明期' },
    { key: 'issuing_authority', label: '出具机构' },
    { key: 'scope', label: '参保/缴费情况' },
    { key: 'level', label: '缴费期间/月数' },
    { key: 'holder', label: '人员姓名' },
  ],
  professional_title: [
    { key: 'name', label: '证书类型' },
    { key: 'number', label: '证书编号' },
    { key: 'issue_date', label: '取得/签发日期' },
    { key: 'expiry_date', label: '有效期' },
    { key: 'issuing_authority', label: '发证机构' },
    { key: 'scope', label: '专业' },
    { key: 'level', label: '职称/资格等级' },
    { key: 'holder', label: '人员姓名' },
  ],
  special_operation: [
    { key: 'name', label: '证书类型' },
    { key: 'number', label: '证书编号' },
    { key: 'issue_date', label: '初领/签发日期' },
    { key: 'expiry_date', label: '有效期' },
    { key: 'issuing_authority', label: '发证机关' },
    { key: 'scope', label: '作业类别/准操项目' },
    { key: 'level', label: '复审/资格级别' },
    { key: 'holder', label: '人员姓名' },
  ],
  other_personnel: [
    { key: 'name', label: '资料类型' },
    { key: 'number', label: '编号' },
    { key: 'issue_date', label: '出具日期' },
    { key: 'expiry_date', label: '截止日期' },
    { key: 'issuing_authority', label: '出具方' },
    { key: 'scope', label: '证明内容' },
    { key: 'level', label: '角色/岗位' },
    { key: 'holder', label: '人员/主体' },
  ],
};

const FINANCIAL_TYPE_COLUMNS: Record<
  Exclude<FinancialQualificationType, 'summary'>,
  QualificationColumn[]
> = {
  tax: [
    { key: 'name', label: '证明类型' },
    { key: 'number', label: '证明/凭证编号' },
    { key: 'issue_date', label: '出具日期' },
    { key: 'expiry_date', label: '税款所属期/有效期' },
    { key: 'issuing_authority', label: '税务机关' },
    { key: 'scope', label: '证明内容' },
    { key: 'level', label: '税种/结论' },
    { key: 'holder', label: '纳税主体' },
  ],
  financial_report: [
    { key: 'name', label: '报告类型' },
    { key: 'number', label: '会计期间/年度' },
    { key: 'issue_date', label: '申报/出具日期' },
    { key: 'expiry_date', label: '报告截止日' },
    { key: 'issuing_authority', label: '申报系统/出具方' },
    { key: 'scope', label: '关键财务指标' },
    { key: 'level', label: '审计结论/报表口径' },
    { key: 'holder', label: '会计主体' },
  ],
  bank: [
    { key: 'name', label: '资料类型' },
    { key: 'number', label: '账号/许可证号' },
    { key: 'issue_date', label: '出具日期' },
    { key: 'expiry_date', label: '有效期' },
    { key: 'issuing_authority', label: '开户行/银行' },
    { key: 'scope', label: '账户/资信内容' },
    { key: 'level', label: '账户性质/评级' },
    { key: 'holder', label: '主体' },
  ],
  other_financial: [
    { key: 'name', label: '资料类型' },
    { key: 'number', label: '编号' },
    { key: 'issue_date', label: '出具日期' },
    { key: 'expiry_date', label: '覆盖期/有效期' },
    { key: 'issuing_authority', label: '出具机构' },
    { key: 'scope', label: '内容摘要' },
    { key: 'level', label: '结论/备注' },
    { key: 'holder', label: '主体' },
  ],
};

export const getDefaultKnowledgeCategory = (): QualificationCategory => DEFAULT_CATEGORY;

export const getQualificationCategoryOptions = (): QualificationCategoryOption[] =>
  CATEGORY_OPTIONS;

export const getQualificationColumns = (
  category: QualificationCategory,
  personnelType: PersonnelQualificationType = 'all',
  financialType: FinancialQualificationType = 'summary',
): QualificationColumn[] => {
  if (category === 'personnel' && personnelType !== 'all') {
    return PERSONNEL_TYPE_COLUMNS[personnelType];
  }
  if (category === 'financial' && financialType === 'summary') {
    return [
      { key: 'name', label: '资料类型' },
      { key: 'number', label: '份数/编号' },
      { key: 'issue_date', label: '最近出具日期' },
      { key: 'expiry_date', label: '覆盖期/有效期' },
      { key: 'issuing_authority', label: '主要出具机构' },
      { key: 'scope', label: '覆盖内容' },
      { key: 'level', label: '结论/指标' },
      { key: 'holder', label: '主体' },
    ];
  }
  if (category === 'financial' && financialType !== 'summary') {
    return FINANCIAL_TYPE_COLUMNS[financialType];
  }
  return CATEGORY_COLUMNS[category];
};

export const getPersonnelQualificationType = (
  qualification: Pick<Qualification, 'name'>,
): Exclude<PersonnelQualificationType, 'all'> => {
  const name = qualification.name || '';
  if (name.includes('身份证')) return 'identity';
  if (name.includes('社保') || name.includes('社会保险') || name.includes('养老保险')) {
    return 'social_security';
  }
  if (name.includes('职称') || name.includes('资格')) return 'professional_title';
  if (name.includes('特种作业') || name.includes('作业证') || name.includes('操作证')) {
    return 'special_operation';
  }
  return 'other_personnel';
};

export const getPersonnelTypeOptions = (
  qualifications: Pick<Qualification, 'name'>[],
): PersonnelTypeOption[] => {
  const values = new Set<PersonnelQualificationType>(['all']);
  qualifications.forEach((qualification) => {
    values.add(getPersonnelQualificationType(qualification));
  });
  return Array.from(values).map((value) => ({
    value,
    label: PERSONNEL_TYPE_LABELS[value],
  }));
};

export const getFinancialQualificationType = (
  qualification: Pick<Qualification, 'name' | 'scope' | 'issuing_authority'>,
): Exclude<FinancialQualificationType, 'summary'> => {
  const text = `${qualification.name || ''} ${qualification.scope || ''} ${qualification.issuing_authority || ''}`;
  if (text.includes('审计') || text.includes('财务') || text.includes('会计')) return 'financial_report';
  if (text.includes('纳税') || text.includes('完税') || text.includes('税务')) return 'tax';
  if (text.includes('银行') || text.includes('开户') || text.includes('资信')) return 'bank';
  return 'other_financial';
};

export const getFinancialTypeOptions = (
  qualifications: Pick<Qualification, 'name' | 'scope' | 'issuing_authority'>[],
): FinancialTypeOption[] => {
  const values = new Set<FinancialQualificationType>(['summary']);
  qualifications.forEach((qualification) => {
    values.add(getFinancialQualificationType(qualification));
  });
  return Array.from(values).map((value) => ({
    value,
    label: FINANCIAL_TYPE_LABELS[value],
  }));
};

export const normalizeFinancialSummaryAuthority = (
  authority: string | null | undefined,
): string | null => {
  if (!authority) return null;
  const compact = authority.replace(/\s+/g, '');

  const taxBureauMatch = compact.match(/(国家税务总局[\u4e00-\u9fff]+?税务局)/);
  if (taxBureauMatch?.[1]) {
    return taxBureauMatch[1];
  }

  return compact || null;
};

export type DisplayQualification = Qualification & {
  sourceIds?: number[];
  sourceCount?: number;
};

export const summarizeFinancialQualifications = (
  qualifications: Qualification[],
): DisplayQualification[] => {
  const groups = new Map<string, Qualification[]>();
  qualifications.forEach((qualification) => {
    const type = getFinancialQualificationType(qualification);
    const summaryAuthority =
      normalizeFinancialSummaryAuthority(qualification.issuing_authority) || '未识别机构';
    const groupKey = [
      type,
      qualification.holder || '未识别主体',
      summaryAuthority,
    ].join('|');
    const group = groups.get(groupKey) || [];
    group.push(qualification);
    groups.set(groupKey, group);
  });

  let syntheticId = -1;
  return Array.from(groups.entries()).map(([key, group]) => {
    const [type, , summaryAuthority] = key.split('|');
    const first = group[0];
    const label = FINANCIAL_TYPE_LABELS[type as FinancialQualificationType].replace('明细', '');
    const count = group.length;
    const sortedIssueDates = group
      .map((item) => item.issue_date)
      .filter(Boolean)
      .sort();
    return {
      ...first,
      id: syntheticId--,
      name: count > 1 ? `${label}汇总` : first.name,
      number: count > 1 ? `${count} 份` : first.number,
      issue_date: sortedIssueDates.length > 0
        ? sortedIssueDates[sortedIssueDates.length - 1] || null
        : first.issue_date,
      issuing_authority:
        summaryAuthority && summaryAuthority !== '未识别机构'
          ? summaryAuthority
          : first.issuing_authority,
      scope: count > 1 ? `${first.scope || label}（共 ${count} 份证明，切换到明细可逐份查看/操作）` : first.scope,
      sourceIds: group.map((item) => item.id),
      sourceCount: count,
    };
  });
};

export const getQualificationCellValue = (
  qualification: Qualification,
  key: QualificationColumnKey,
): string | null => qualification[key];
