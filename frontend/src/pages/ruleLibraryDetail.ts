export function getRuleTypeLabel(ruleType: string): string {
  if (ruleType === 'red_flag') return '红线规则';
  if (ruleType === 'tighten_rule') return '收紧规则';
  if (ruleType === 'required_evidence_rule') return '强制证据规则';
  if (ruleType === 'exclusion_rule') return '排除规则';
  if (ruleType === 'relax_rule') return '放宽规则';
  if (ruleType === 'parse_hint_rule') return '解析提示规则';
  return ruleType || '未分类规则';
}

export function getRuleImpactNotice(ruleType: string): string {
  if (ruleType === 'red_flag') {
    return '命中后会标记为投标待办红线，需要人工确认处理状态。';
  }
  if (ruleType === 'tighten_rule') {
    return '命中后只会把自动符合降级为需确认，不会自动判定为符合或不符合。';
  }
  if (ruleType === 'required_evidence_rule') {
    return '命中后会要求补齐指定证据项，证据不足时进入需确认。';
  }
  if (ruleType === 'exclusion_rule') {
    return '命中后可能直接判定不符合，属于高风险规则，发布前必须谨慎复核。';
  }
  if (ruleType === 'relax_rule') {
    return '放宽规则风险最高，默认不应自动把需确认升级为符合。';
  }
  if (ruleType === 'parse_hint_rule') {
    return '命中后只应影响解析提示或字段提取建议，不应直接改变匹配结论。';
  }
  return '当前规则类型暂无专用影响说明，发布前需要人工确认影响范围。';
}

export function getRuleDraftStatusLabel(status: string): string {
  if (status === 'pending_review') return '待审核';
  if (status === 'published') return '已发布';
  if (status === 'rejected') return '已驳回';
  return status || '未知状态';
}

export function canPublishSimilarRuleDraft(differenceReason: string): boolean {
  return differenceReason.trim().length > 0;
}

export function canCreateRuleDraftFromTemplate(reason: string): boolean {
  return reason.trim().length > 0;
}

export function getRuleRelationTypeLabel(relationType: string): string {
  if (relationType === 'similar_to') return '相似规则';
  if (relationType === 'duplicate_of') return '复用已有规则';
  if (relationType === 'merged_into') return '已合并到';
  return relationType || '未知关系';
}

export function getRuleRelationDirectionLabel(direction: string): string {
  if (direction === 'outgoing') return '本规则关联到';
  if (direction === 'incoming') return '其他规则关联到本规则';
  return direction || '未知方向';
}

export function canMergeRuleInto(sourceRuleId: string, targetRuleId: string): boolean {
  return (
    sourceRuleId.startsWith('custom.') &&
    Boolean(targetRuleId) &&
    sourceRuleId !== targetRuleId &&
    !targetRuleId.startsWith('draft.')
  );
}

export function canUpdateCustomRule(
  ruleId: string,
  name: string,
  ruleType: string,
  description: string,
  editReason: string,
): boolean {
  return (
    ruleId.startsWith('custom.') &&
    name.trim().length > 0 &&
    ruleType.trim().length > 0 &&
    description.trim().length > 0 &&
    editReason.trim().length > 0
  );
}

export function canRollbackCustomRule(
  ruleId: string,
  versionNo: number,
  reason: string,
): boolean {
  return ruleId.startsWith('custom.') && versionNo > 0 && reason.trim().length > 0;
}

export function getRuleSuggestionQualityLabel(qualityStatus: string): string {
  if (qualityStatus === 'actionable') return '可执行建议';
  if (qualityStatus === 'low_quality') return '信息不足';
  return '待评估';
}
