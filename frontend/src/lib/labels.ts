export const statusLabels: Record<string, string> = {
  active: '进行中', archived: '已归档', draft: '待开始', pending: '待处理',
  queued: '排队中', running: '处理中', completed: '已完成', failed: '未完成',
  canceled: '已取消', needs_review: '待人工复核', stale: '资料已更新',
  met: '符合', not_met: '不符合', not_applicable: '不适用',
  proposed: '待确认', accepted: '已确认', edited: '已修改',
  missing_evidence: '待补充', rejected: '已拒绝',
  verified: '已核实', unreviewed: '待核实', expired: '已过期',
  waiting_api: '待启用 AI', waiting_config: '待配置模型', ready: '已入库',
  extracted: 'AI 已提取', drafting: '正在起草', drafted: '已起草',
};

export const roleLabels: Record<string, string> = {
  tender: '招标文件', addendum: '补遗文件', qa: '答疑文件', template: '投标模板', evidence: '证明材料',
};

export const categoryLabels: Record<string, string> = {
  qualification: '企业资质', personnel: '人员资质', performance: '业绩材料',
  financial: '财务材料', technical: '技术要求', commercial: '商务要求',
  submission: '文件提交', other: '其他要求',
};

export const stageLabels: Record<string, string> = {
  qualification: '资格审查', compliance: '符合性审查', technical: '技术评审',
  commercial: '商务评审', business: '商务评审',
};

export function statusColor(status: string): 'success' | 'warning' | 'error' | 'info' | 'default' {
  if (['completed', 'met', 'accepted', 'edited', 'verified', 'ready', 'drafted'].includes(status)) return 'success';
  if (['needs_review', 'proposed', 'missing_evidence', 'unreviewed', 'stale'].includes(status)) return 'warning';
  if (['failed', 'not_met', 'expired'].includes(status)) return 'error';
  if (['queued', 'running', 'drafting', 'extracted'].includes(status)) return 'info';
  return 'default';
}

export function documentStatus(document: { parse_status: string; ai_status: string }) {
  return ['pending', 'queued', 'running', 'failed', 'canceled'].includes(document.parse_status)
    ? document.parse_status : document.ai_status;
}

export const factLabels: Record<string, string> = {
  company_name: '企业名称', unified_code: '统一社会信用代码', address: '地址',
  contact: '联系人', phone: '联系电话', bank_name: '开户银行', bank_account: '银行账号',
  certificate_name: '证书名称', certificate_type: '证书类型', level: '等级', scope: '适用范围',
  valid_until: '有效期至', expiry_date: '有效期至', registered_capital: '注册资本',
  revenue: '营业收入', project_name: '业绩名称', project_scope: '项目范围',
  client_name: '客户名称', contract_amount: '合同金额', contract_date: '合同日期',
  acceptance_date: '验收日期', material_type: '材料类型', model: '型号', manufacturer: '制造商',
};
