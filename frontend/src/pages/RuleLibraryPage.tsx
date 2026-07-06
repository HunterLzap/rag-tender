import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Drawer,
  IconButton,
  Paper,
  Pagination,
  Switch,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import RefreshIcon from '@mui/icons-material/Refresh';
import RuleIcon from '@mui/icons-material/Rule';
import { CategoryTag, MandatoryTag, OverflowChipRow } from '../components/StatusTags';
import { colors } from '../theme';
import {
  createRuleDraftFromTemplate,
  getRuleCatalog,
  getRuleChangeLogs,
  getRuleDrafts,
  getRuleRelations,
  getRuleSuggestions,
  getRuleTemplates,
  getRuleVersions,
  getSimilarRulesForDraft,
  mergeCustomRule,
  rollbackCustomRule,
  reuseExistingRuleForDraft,
  reviewRuleDraft,
  reviewRuleSuggestion,
  updateCustomRule,
  updateRuleEnabled,
  updateRuleDraft,
} from '../api/rules';
import type {
  RuleCatalogItem,
  RuleChangeLog,
  RuleDraft,
  RuleRelation,
  RuleTemplate,
  RuleVersion,
  SimilarRuleCandidate,
  RuleStrictness,
  RuleSuggestion,
} from '../types';
import {
  canMergeRuleInto,
  canCreateRuleDraftFromTemplate,
  canPublishSimilarRuleDraft,
  canRollbackCustomRule,
  canUpdateCustomRule,
  getRuleRelationDirectionLabel,
  getRuleRelationTypeLabel,
  getRuleDraftStatusLabel,
  getRuleImpactNotice,
  getRuleSuggestionQualityLabel,
  getRuleTypeLabel,
} from './ruleLibraryDetail';
import { getRuleLibraryTabCounts } from './ruleLibraryTabs';
import { paginateItems } from '../utils/pagination';

const TEMPLATE_RISK_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  high: { label: '高风险', color: '#C62828', bg: '#FFEBEE' },
  medium: { label: '中风险', color: '#EF6C00', bg: '#FFF3E0' },
  low: { label: '低风险', color: '#2E7D32', bg: '#E8F5E9' },
};

const PAGE_SIZE = 10;

const STRICTNESS_LABELS: Record<RuleStrictness, '严格' | '平衡' | '宽松'> = {
  strict: '严格',
  balanced: '平衡',
  loose: '宽松',
};

const ClampedText: React.FC<{
  text: string;
  lines?: number;
  color?: string;
  emptyText?: string;
}> = ({ text, lines = 2, color = 'text.secondary', emptyText = '暂无说明' }) => {
  const displayText = text || emptyText;

  return (
    <Tooltip title={displayText} arrow placement="top-start">
      <Typography
        variant="body2"
        color={color}
        sx={{
          display: '-webkit-box',
          WebkitLineClamp: lines,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
          cursor: 'default',
        }}
      >
        {displayText}
      </Typography>
    </Tooltip>
  );
};

const RuleLibraryPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [rules, setRules] = useState<RuleCatalogItem[]>([]);
  const [changes, setChanges] = useState<RuleChangeLog[]>([]);
  const [suggestions, setSuggestions] = useState<RuleSuggestion[]>([]);
  const [drafts, setDrafts] = useState<RuleDraft[]>([]);
  const [templates, setTemplates] = useState<RuleTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingRuleId, setSavingRuleId] = useState<string | null>(null);
  const [pendingChange, setPendingChange] = useState<{
    rule: RuleCatalogItem;
    enabled: boolean;
  } | null>(null);
  const [changeReason, setChangeReason] = useState('');
  const [pendingSuggestionReview, setPendingSuggestionReview] = useState<{
    suggestion: RuleSuggestion;
    status: 'accepted' | 'rejected';
  } | null>(null);
  const [suggestionReviewReason, setSuggestionReviewReason] = useState('');
  const [pendingDraftReview, setPendingDraftReview] = useState<{
    draft: RuleDraft;
    status: 'published' | 'rejected';
    similarRuleIds?: string[];
    differenceReason?: string;
  } | null>(null);
  const [pendingSimilarPublish, setPendingSimilarPublish] = useState<{
    draft: RuleDraft;
    candidates: SimilarRuleCandidate[];
  } | null>(null);
  const [reuseReason, setReuseReason] = useState('');
  const [differenceReason, setDifferenceReason] = useState('');
  const [reusingRuleId, setReusingRuleId] = useState<string | null>(null);
  const [draftReviewReason, setDraftReviewReason] = useState('');
  const [editingDraft, setEditingDraft] = useState<RuleDraft | null>(null);
  const [draftForm, setDraftForm] = useState({
    name: '',
    rule_type: 'tighten_rule',
    draft_content: '',
    edit_reason: '',
  });
  const [selectedRule, setSelectedRule] = useState<RuleCatalogItem | null>(null);
  const [selectedRuleRelations, setSelectedRuleRelations] = useState<RuleRelation[]>([]);
  const [loadingRuleRelations, setLoadingRuleRelations] = useState(false);
  const [selectedRuleVersions, setSelectedRuleVersions] = useState<RuleVersion[]>([]);
  const [loadingRuleVersions, setLoadingRuleVersions] = useState(false);
  const [editingRule, setEditingRule] = useState<RuleCatalogItem | null>(null);
  const [ruleForm, setRuleForm] = useState({
    name: '',
    rule_type: '',
    description: '',
    edit_reason: '',
  });
  const [savingRuleEdit, setSavingRuleEdit] = useState(false);
  const [pendingRuleRollback, setPendingRuleRollback] = useState<{
    rule: RuleCatalogItem;
    version: RuleVersion;
  } | null>(null);
  const [rollbackReason, setRollbackReason] = useState('');
  const [rollingBackRule, setRollingBackRule] = useState(false);
  const [pendingRuleMerge, setPendingRuleMerge] = useState<{
    sourceRule: RuleCatalogItem;
    relation: RuleRelation;
  } | null>(null);
  const [mergeReason, setMergeReason] = useState('');
  const [mergingRule, setMergingRule] = useState(false);
  const [pendingTemplateDraft, setPendingTemplateDraft] = useState<RuleTemplate | null>(null);
  const [templateDraftReason, setTemplateDraftReason] = useState('');
  const [creatingTemplateDraftId, setCreatingTemplateDraftId] = useState<string | null>(null);
  const [selectedDraft, setSelectedDraft] = useState<RuleDraft | null>(null);
  const [rulePage, setRulePage] = useState(1);
  const [suggestionPage, setSuggestionPage] = useState(1);
  const [draftPage, setDraftPage] = useState(1);
  const [changePage, setChangePage] = useState(1);
  const [templatePage, setTemplatePage] = useState(1);

  const loadRules = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getRuleCatalog();
      setRules(data);
      setChanges(await getRuleChangeLogs(20));
      setSuggestions(await getRuleSuggestions(20));
      setDrafts(await getRuleDrafts(20));
      setTemplates(await getRuleTemplates());
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载规则库失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadRules();
  }, []);

  useEffect(() => {
    if (!selectedRule) {
      setSelectedRuleRelations([]);
      setLoadingRuleRelations(false);
      return;
    }

    let cancelled = false;
    setLoadingRuleRelations(true);
    void getRuleRelations(selectedRule.id)
      .then((relations) => {
        if (!cancelled) {
          setSelectedRuleRelations(relations);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : '加载规则关系失败');
          setSelectedRuleRelations([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingRuleRelations(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedRule]);

  useEffect(() => {
    if (!selectedRule) {
      setSelectedRuleVersions([]);
      setLoadingRuleVersions(false);
      return;
    }

    let cancelled = false;
    setLoadingRuleVersions(true);
    void getRuleVersions(selectedRule.id)
      .then((versions) => {
        if (!cancelled) {
          setSelectedRuleVersions(versions);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : '加载规则版本历史失败');
          setSelectedRuleVersions([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingRuleVersions(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedRule]);

  const handleEnabledChange = async () => {
    if (!pendingChange) return;
    const { rule, enabled } = pendingChange;
    setSavingRuleId(rule.id);
    setError(null);
    try {
      const updated = await updateRuleEnabled(rule.id, enabled, changeReason.trim());
      setRules((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setChanges(await getRuleChangeLogs(20));
      setSuggestions(await getRuleSuggestions(20));
      setPendingChange(null);
      setChangeReason('');
    } catch (err) {
      setError(err instanceof Error ? err.message : '更新规则状态失败');
    } finally {
      setSavingRuleId(null);
    }
  };

  const handleSuggestionReview = async () => {
    if (!pendingSuggestionReview) return;
    setError(null);
    try {
      await reviewRuleSuggestion(
        pendingSuggestionReview.suggestion.id,
        pendingSuggestionReview.status,
        suggestionReviewReason.trim(),
      );
      setSuggestions(await getRuleSuggestions(20));
      setDrafts(await getRuleDrafts(20));
      setPendingSuggestionReview(null);
      setSuggestionReviewReason('');
    } catch (err) {
      setError(err instanceof Error ? err.message : '处理规则建议失败');
    }
  };

  const handleDraftReview = async () => {
    if (!pendingDraftReview) return;
    setError(null);
    try {
      await reviewRuleDraft(
        pendingDraftReview.draft.id,
        pendingDraftReview.status,
        draftReviewReason.trim(),
        pendingDraftReview.status === 'published' && pendingDraftReview.similarRuleIds?.length
          ? {
              similarRuleIds: pendingDraftReview.similarRuleIds,
              differenceReason: pendingDraftReview.differenceReason,
            }
          : undefined,
      );
      setRules(await getRuleCatalog());
      setDrafts(await getRuleDrafts(20));
      setPendingDraftReview(null);
      setDraftReviewReason('');
      setPendingSimilarPublish(null);
      setReuseReason('');
      setDifferenceReason('');
    } catch (err) {
      setError(err instanceof Error ? err.message : '审核规则草案失败');
    }
  };

  const handlePublishDraftClick = async (draft: RuleDraft) => {
    setError(null);
    try {
      const candidates = await getSimilarRulesForDraft(draft.id);
      if (candidates.length > 0) {
        setPendingSimilarPublish({ draft, candidates });
        setDifferenceReason('');
        return;
      }
      setPendingDraftReview({ draft, status: 'published' });
    } catch (err) {
      setError(err instanceof Error ? err.message : '检测相似规则失败');
    }
  };

  const handleReuseExistingRule = async (candidate: SimilarRuleCandidate) => {
    if (!pendingSimilarPublish) return;
    setReusingRuleId(candidate.rule_id);
    setError(null);
    try {
      await reuseExistingRuleForDraft(
        pendingSimilarPublish.draft.id,
        candidate.rule_id,
        reuseReason.trim() || `与已有规则「${candidate.name}」重复，复用该规则`,
      );
      setRules(await getRuleCatalog());
      setChanges(await getRuleChangeLogs(20));
      setDrafts(await getRuleDrafts(20));
      setPendingSimilarPublish(null);
      setReuseReason('');
      setDifferenceReason('');
    } catch (err) {
      setError(err instanceof Error ? err.message : '复用已有规则失败');
    } finally {
      setReusingRuleId(null);
    }
  };

  const handleMergeRule = async () => {
    if (!pendingRuleMerge) return;
    setMergingRule(true);
    setError(null);
    try {
      await mergeCustomRule(
        pendingRuleMerge.sourceRule.id,
        pendingRuleMerge.relation.related_rule_id,
        mergeReason.trim(),
      );
      const updatedRules = await getRuleCatalog();
      setRules(updatedRules);
      setChanges(await getRuleChangeLogs(20));
      const updatedSelectedRule = updatedRules.find((rule) => rule.id === pendingRuleMerge.sourceRule.id);
      setSelectedRule(updatedSelectedRule || { ...pendingRuleMerge.sourceRule, enabled: false });
      setPendingRuleMerge(null);
      setMergeReason('');
    } catch (err) {
      setError(err instanceof Error ? err.message : '归并规则失败');
    } finally {
      setMergingRule(false);
    }
  };

  const openRuleEditor = (rule: RuleCatalogItem) => {
    setEditingRule(rule);
    setRuleForm({
      name: rule.name,
      rule_type: rule.rule_type,
      description: rule.description,
      edit_reason: '',
    });
  };

  const closeRuleEditor = () => {
    setEditingRule(null);
    setRuleForm({
      name: '',
      rule_type: '',
      description: '',
      edit_reason: '',
    });
  };

  const handleUpdateCustomRule = async () => {
    if (!editingRule) return;
    setSavingRuleEdit(true);
    setError(null);
    try {
      const updated = await updateCustomRule(editingRule.id, {
        name: ruleForm.name.trim(),
        rule_type: ruleForm.rule_type.trim(),
        description: ruleForm.description.trim(),
        edit_reason: ruleForm.edit_reason.trim(),
      });
      setRules((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setSelectedRule(updated);
      closeRuleEditor();
    } catch (err) {
      setError(err instanceof Error ? err.message : '编辑规则失败');
    } finally {
      setSavingRuleEdit(false);
    }
  };

  const handleRollbackCustomRule = async () => {
    if (!pendingRuleRollback) return;
    setRollingBackRule(true);
    setError(null);
    try {
      const updated = await rollbackCustomRule(
        pendingRuleRollback.rule.id,
        pendingRuleRollback.version.version_no,
        rollbackReason.trim(),
      );
      setRules((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setSelectedRule(updated);
      setSelectedRuleVersions(await getRuleVersions(updated.id));
      setPendingRuleRollback(null);
      setRollbackReason('');
    } catch (err) {
      setError(err instanceof Error ? err.message : '回滚规则失败');
    } finally {
      setRollingBackRule(false);
    }
  };

  const openDraftEditor = (draft: RuleDraft) => {
    setEditingDraft(draft);
    setDraftForm({
      name: draft.name,
      rule_type: draft.rule_type,
      draft_content: draft.draft_content,
      edit_reason: '',
    });
  };

  const closeDraftEditor = () => {
    setEditingDraft(null);
    setDraftForm({
      name: '',
      rule_type: 'tighten_rule',
      draft_content: '',
      edit_reason: '',
    });
  };

  const handleDraftUpdate = async () => {
    if (!editingDraft) return;
    setError(null);
    try {
      const updated = await updateRuleDraft(editingDraft.id, draftForm);
      setDrafts((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      closeDraftEditor();
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存规则草案失败');
    }
  };

  const handleCreateTemplateDraft = async () => {
    if (!pendingTemplateDraft) return;
    setCreatingTemplateDraftId(pendingTemplateDraft.id);
    setError(null);
    try {
      await createRuleDraftFromTemplate(pendingTemplateDraft.id, templateDraftReason.trim());
      setDrafts(await getRuleDrafts(20));
      setActiveTab(2);
      setDraftPage(1);
      setPendingTemplateDraft(null);
      setTemplateDraftReason('');
    } catch (err) {
      setError(err instanceof Error ? err.message : '从模板生成规则草案失败');
    } finally {
      setCreatingTemplateDraftId(null);
    }
  };

  const stats = useMemo(() => {
    return rules.reduce(
      (acc, rule) => {
        acc.total += 1;
        if (rule.enabled) acc.enabled += 1;
        if (rule.strictness === 'strict') acc.strict += 1;
        if (rule.rule_type === 'red_flag') acc.redFlag += 1;
        return acc;
      },
      { total: 0, enabled: 0, strict: 0, redFlag: 0 },
    );
  }, [rules]);

  const tabCounts = useMemo(
    () => getRuleLibraryTabCounts({ rules, suggestions, drafts, changes, templates }),
    [rules, suggestions, drafts, changes, templates],
  );
  const rulePagination = useMemo(
    () => paginateItems(rules, rulePage, PAGE_SIZE),
    [rules, rulePage],
  );
  const suggestionPagination = useMemo(
    () => paginateItems(suggestions, suggestionPage, PAGE_SIZE),
    [suggestions, suggestionPage],
  );
  const draftPagination = useMemo(
    () => paginateItems(drafts, draftPage, PAGE_SIZE),
    [drafts, draftPage],
  );
  const changePagination = useMemo(
    () => paginateItems(changes, changePage, PAGE_SIZE),
    [changes, changePage],
  );
  const templatePagination = useMemo(
    () => paginateItems(templates, templatePage, PAGE_SIZE),
    [templates, templatePage],
  );

  useEffect(() => {
    if (rulePage !== rulePagination.page) setRulePage(rulePagination.page);
  }, [rulePage, rulePagination.page]);

  useEffect(() => {
    if (suggestionPage !== suggestionPagination.page) {
      setSuggestionPage(suggestionPagination.page);
    }
  }, [suggestionPage, suggestionPagination.page]);

  useEffect(() => {
    if (draftPage !== draftPagination.page) setDraftPage(draftPagination.page);
  }, [draftPage, draftPagination.page]);

  useEffect(() => {
    if (changePage !== changePagination.page) setChangePage(changePagination.page);
  }, [changePage, changePagination.page]);

  useEffect(() => {
    if (templatePage !== templatePagination.page) setTemplatePage(templatePagination.page);
  }, [templatePage, templatePagination.page]);

  return (
    <Box sx={{ p: 3 }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          mb: 2,
        }}
      >
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="h2" sx={{ color: '#333' }}>
            规则库
          </Typography>
        </Box>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={() => void loadRules()}
          sx={{ borderRadius: 0, borderColor: '#7C4DFF', color: '#7C4DFF' }}
        >
          刷新
        </Button>
      </Box>

      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 2, mb: 2 }}>
        {[
          { label: '规则总数', value: stats.total, color: '#5E35B1' },
          { label: '已启用', value: stats.enabled, color: '#2E7D32' },
          { label: '严格规则', value: stats.strict, color: '#C62828' },
          { label: '红线规则', value: stats.redFlag, color: '#EF6C00' },
        ].map((item) => (
          <Paper
            key={item.label}
            sx={{
              p: 2,
              boxShadow: 'none',
              border: '1px solid #EDE7F6',
              borderRadius: 2,
            }}
          >
            <Typography variant="caption" sx={{ color: '#777' }}>
              {item.label}
            </Typography>
            <Typography variant="h5" sx={{ color: item.color, fontWeight: 700 }}>
              {item.value}
            </Typography>
          </Paper>
        ))}
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Tabs
        value={activeTab}
        onChange={(_, value: number) => setActiveTab(value)}
        sx={{
          mb: 2,
          borderBottom: '1px solid #EDE7F6',
          '& .MuiTabs-indicator': { backgroundColor: '#7C4DFF' },
          '& .MuiTab-root': { minHeight: 42, color: '#666' },
          '& .Mui-selected': { color: '#7C4DFF !important', fontWeight: 700 },
        }}
      >
        <Tab label={`规则目录 (${tabCounts.rules})`} />
        <Tab label={`规则建议 (${tabCounts.suggestions})`} />
        <Tab label={`规则草案 (${tabCounts.drafts})`} />
        <Tab label={`变更记录 (${tabCounts.changes})`} />
        <Tab label={`规则模板 (${tabCounts.templates})`} />
      </Tabs>

      {activeTab === 0 && (
      <TableContainer
        component={Paper}
        sx={{ boxShadow: 'none', border: `1px solid ${colors.divider}` }}
      >
        <Table size="small" sx={{ tableLayout: 'fixed' }}>
          <TableHead>
            <TableRow>
              <TableCell sx={{ width: '20%' }}>
                规则
              </TableCell>
              <TableCell sx={{ width: '8%' }}>
                启用
              </TableCell>
              <TableCell sx={{ width: '10%' }}>
                业务域
              </TableCell>
              <TableCell sx={{ width: '9%' }}>
                严格度
              </TableCell>
              <TableCell sx={{ width: '21%' }}>
                关键词
              </TableCell>
              <TableCell sx={{ width: '20%' }}>
                规则说明
              </TableCell>
              <TableCell sx={{ width: '12%' }}>
                命中动作
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading && (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 5 }}>
                  <CircularProgress size={28} sx={{ color: '#7C4DFF' }} />
                </TableCell>
              </TableRow>
            )}
            {!loading && rules.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 5 }}>
                  <Typography variant="body2" sx={{ color: '#999' }}>
                    暂无规则。
                  </Typography>
                </TableCell>
              </TableRow>
            )}
            {!loading &&
              rulePagination.items.map((rule) => {
                return (
                  <TableRow key={rule.id} hover className="zebra" sx={{ height: 40 }}>
                    <TableCell>
                      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', minWidth: 0 }}>
                        <RuleIcon sx={{ color: '#7C4DFF', fontSize: 18 }} />
                        <Box sx={{ minWidth: 0 }}>
                          <Tooltip title={rule.name} arrow>
                            <Typography
                              variant="body2"
                              sx={{
                                color: 'text.primary',
                                fontWeight: 600,
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                              }}
                            >
                            {rule.name}
                            </Typography>
                          </Tooltip>
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            sx={{
                              display: 'block',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {rule.id}
                          </Typography>
                        </Box>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Switch
                        size="small"
                        checked={rule.enabled}
                        disabled={savingRuleId === rule.id}
                        onChange={(event) =>
                          setPendingChange({
                            rule,
                            enabled: event.target.checked,
                          })
                        }
                        sx={{
                          '& .MuiSwitch-switchBase.Mui-checked': {
                            color: '#7C4DFF',
                          },
                          '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                            backgroundColor: '#7C4DFF',
                          },
                        }}
                      />
                    </TableCell>
                    <TableCell>
                      <CategoryTag category={rule.domain} />
                    </TableCell>
                    <TableCell>
                      <MandatoryTag level={STRICTNESS_LABELS[rule.strictness]} />
                    </TableCell>
                    <TableCell>
                      <OverflowChipRow items={rule.keywords} max={3} />
                    </TableCell>
                    <TableCell>
                      <ClampedText text={rule.description} lines={2} />
                      <Typography variant="caption" color="text.secondary">
                        来源：{rule.source}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                        <Box sx={{ flex: 1, minWidth: 0 }}>
                          <ClampedText text={rule.action} lines={2} emptyText="暂无动作说明" />
                        </Box>
                        <Tooltip title="查看详情">
                          <IconButton size="small" onClick={() => setSelectedRule(rule)}>
                            <InfoOutlinedIcon fontSize="small" sx={{ color: 'text.secondary' }} />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    </TableCell>
                  </TableRow>
                );
              })}
          </TableBody>
        </Table>
        <PaginationFooter
          page={rulePagination.page}
          pageCount={rulePagination.pageCount}
          startIndex={rulePagination.startIndex}
          endIndex={rulePagination.endIndex}
          total={rulePagination.total}
          onPageChange={setRulePage}
        />
      </TableContainer>
      )}

      {activeTab === 1 && (
      <Box>
        <TableContainer
          component={Paper}
          sx={{ boxShadow: 'none', border: '1px solid #EDE7F6' }}
        >
          <Table size="small">
            <TableHead>
              <TableRow sx={{ backgroundColor: '#F9F7FF' }}>
                <TableCell sx={{ fontWeight: 600, color: '#666', width: '24%' }}>
                  建议
                </TableCell>
                <TableCell sx={{ fontWeight: 600, color: '#666', width: '24%' }}>
                  来源要求
                </TableCell>
                <TableCell sx={{ fontWeight: 600, color: '#666', width: '34%' }}>
                  原因
                </TableCell>
                <TableCell sx={{ fontWeight: 600, color: '#666', width: '9%' }}>
                  置信度
                </TableCell>
                <TableCell sx={{ fontWeight: 600, color: '#666', width: '9%' }}>
                  状态
                </TableCell>
                <TableCell sx={{ fontWeight: 600, color: '#666', width: '8%' }}>
                  操作
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {suggestions.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} align="center" sx={{ py: 4 }}>
                    <Typography variant="body2" sx={{ color: '#999' }}>
                      暂无规则建议。人工修正匹配误判后，这里会生成候选建议。
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
              {suggestionPagination.items.map((suggestion) => (
                <TableRow key={suggestion.id} hover>
                  <TableCell>
                    <Typography variant="body2" sx={{ color: '#333', fontWeight: 600 }}>
                      {suggestion.title}
                    </Typography>
                    <Chip
                      label={suggestion.suggestion_type === 'tighten_rule' ? '建议收紧' : '规则建议'}
                      size="small"
                      sx={{
                        mt: 0.5,
                        height: 22,
                        color: '#C62828',
                        backgroundColor: '#FFEBEE',
                      }}
                    />
                    <Chip
                      label={getRuleSuggestionQualityLabel(suggestion.quality_status)}
                      size="small"
                      sx={{
                        mt: 0.5,
                        ml: 0.5,
                        height: 22,
                        color: '#2E7D32',
                        backgroundColor: '#E8F5E9',
                      }}
                    />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ color: '#333', fontWeight: 600 }}>
                      {suggestion.requirement_title}
                    </Typography>
                    <Typography variant="caption" sx={{ color: '#777' }}>
                      {suggestion.tender_title || suggestion.tender_filename || `标书 ${suggestion.tender_id}`}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ color: '#555' }}>
                      {suggestion.reason}
                    </Typography>
                    {suggestion.evidence_gaps.length > 0 && (
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.75 }}>
                        {suggestion.evidence_gaps.map((gap) => (
                          <Chip
                            key={gap}
                            label={`缺口：${gap}`}
                            size="small"
                            sx={{ height: 20, fontSize: 11, backgroundColor: '#FFF3E0', color: '#EF6C00' }}
                          />
                        ))}
                      </Box>
                    )}
                    {suggestion.quality_notes && (
                      <Typography variant="caption" sx={{ color: '#777', display: 'block', mt: 0.5 }}>
                        {suggestion.quality_notes}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ color: '#333', fontWeight: 600 }}>
                      {Math.round(suggestion.confidence * 100)}%
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={
                        suggestion.review_status === 'accepted'
                          ? '已采纳'
                          : suggestion.review_status === 'rejected'
                            ? '已忽略'
                            : '待处理'
                      }
                      sx={{
                        backgroundColor:
                          suggestion.review_status === 'accepted'
                            ? '#E8F5E9'
                            : suggestion.review_status === 'rejected'
                              ? '#F0F0F0'
                              : '#FFF3E0',
                        color:
                          suggestion.review_status === 'accepted'
                            ? '#2E7D32'
                            : suggestion.review_status === 'rejected'
                              ? '#666'
                              : '#EF6C00',
                      }}
                    />
                    {suggestion.review_reason && (
                      <Typography variant="caption" sx={{ color: '#777', display: 'block', mt: 0.5 }}>
                        {suggestion.review_reason}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', gap: 0.5 }}>
                      <Button
                        size="small"
                        disabled={suggestion.review_status === 'accepted'}
                        onClick={() =>
                          setPendingSuggestionReview({
                            suggestion,
                            status: 'accepted',
                          })
                        }
                        sx={{ minWidth: 0, color: '#2E7D32', fontSize: 12 }}
                      >
                        采纳
                      </Button>
                      <Button
                        size="small"
                        disabled={suggestion.review_status === 'rejected'}
                        onClick={() =>
                          setPendingSuggestionReview({
                            suggestion,
                            status: 'rejected',
                          })
                        }
                        sx={{ minWidth: 0, color: '#666', fontSize: 12 }}
                      >
                        忽略
                      </Button>
                    </Box>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <PaginationFooter
            page={suggestionPagination.page}
            pageCount={suggestionPagination.pageCount}
            startIndex={suggestionPagination.startIndex}
            endIndex={suggestionPagination.endIndex}
            total={suggestionPagination.total}
            onPageChange={setSuggestionPage}
          />
        </TableContainer>
      </Box>
      )}

      {activeTab === 2 && (
      <Box>
        <TableContainer
          component={Paper}
          sx={{ boxShadow: 'none', border: '1px solid #EDE7F6' }}
        >
          <Table size="small">
            <TableHead>
              <TableRow sx={{ backgroundColor: '#F9F7FF' }}>
                <TableCell sx={{ fontWeight: 600, color: '#666', width: '24%' }}>
                  草案
                </TableCell>
                <TableCell sx={{ fontWeight: 600, color: '#666', width: '14%' }}>
                  状态
                </TableCell>
                <TableCell sx={{ fontWeight: 600, color: '#666', width: '44%' }}>
                  内容
                </TableCell>
                <TableCell sx={{ fontWeight: 600, color: '#666', width: '18%' }}>
                  来源/操作
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {drafts.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} align="center" sx={{ py: 4 }}>
                    <Typography variant="body2" sx={{ color: '#999' }}>
                      暂无规则草案。采纳规则建议后会生成待审核草案。
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
              {draftPagination.items.map((draft) => (
                <TableRow key={draft.id} hover>
                  <TableCell>
                    <Typography variant="body2" sx={{ color: '#333', fontWeight: 600 }}>
                      {draft.name}
                    </Typography>
                    <Typography variant="caption" sx={{ color: '#777' }}>
                      {draft.rule_type}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={draft.draft_status === 'pending_review' ? '待审核' : draft.draft_status}
                      sx={{ backgroundColor: '#FFF3E0', color: '#EF6C00' }}
                    />
                  </TableCell>
                  <TableCell>
                    <Typography
                      variant="body2"
                      sx={{ color: '#555', whiteSpace: 'pre-wrap' }}
                    >
                      {draft.draft_content}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="caption" sx={{ color: '#777' }}>
                      {draft.source_suggestion_id}
                    </Typography>
                    <Typography variant="caption" sx={{ color: '#999', display: 'block' }}>
                      {draft.created_at}
                    </Typography>
                    {draft.review_reason && (
                      <Typography variant="caption" sx={{ color: '#777', display: 'block', mt: 0.5 }}>
                        {draft.review_reason}
                      </Typography>
                    )}
                    <Box sx={{ display: 'flex', gap: 0.5, mt: 0.75 }}>
                      <Button
                        size="small"
                        onClick={() => setSelectedDraft(draft)}
                        sx={{ minWidth: 0, color: '#7C4DFF', fontSize: 12 }}
                      >
                        详情
                      </Button>
                      <Button
                        size="small"
                        disabled={draft.draft_status !== 'pending_review'}
                        onClick={() => openDraftEditor(draft)}
                        sx={{ minWidth: 0, color: '#7C4DFF', fontSize: 12 }}
                      >
                        编辑
                      </Button>
                      <Button
                        size="small"
                        disabled={draft.draft_status === 'published'}
                        onClick={() => void handlePublishDraftClick(draft)}
                        sx={{ minWidth: 0, color: '#2E7D32', fontSize: 12 }}
                      >
                        发布
                      </Button>
                      <Button
                        size="small"
                        disabled={draft.draft_status === 'rejected'}
                        onClick={() =>
                          setPendingDraftReview({
                            draft,
                            status: 'rejected',
                          })
                        }
                        sx={{ minWidth: 0, color: '#666', fontSize: 12 }}
                      >
                        驳回
                      </Button>
                    </Box>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <PaginationFooter
            page={draftPagination.page}
            pageCount={draftPagination.pageCount}
            startIndex={draftPagination.startIndex}
            endIndex={draftPagination.endIndex}
            total={draftPagination.total}
            onPageChange={setDraftPage}
          />
        </TableContainer>
      </Box>
      )}

      {activeTab === 3 && (
      <Box>
        <TableContainer
          component={Paper}
          sx={{ boxShadow: 'none', border: '1px solid #EDE7F6' }}
        >
          <Table size="small">
            <TableHead>
              <TableRow sx={{ backgroundColor: '#F9F7FF' }}>
                <TableCell sx={{ fontWeight: 600, color: '#666', width: '28%' }}>
                  规则
                </TableCell>
                <TableCell sx={{ fontWeight: 600, color: '#666', width: '18%' }}>
                  状态变化
                </TableCell>
                <TableCell sx={{ fontWeight: 600, color: '#666', width: '36%' }}>
                  原因
                </TableCell>
                <TableCell sx={{ fontWeight: 600, color: '#666', width: '18%' }}>
                  时间
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {changes.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} align="center" sx={{ py: 4 }}>
                    <Typography variant="body2" sx={{ color: '#999' }}>
                      暂无变更记录
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
              {changePagination.items.map((change) => (
                <TableRow key={change.id} hover>
                  <TableCell>
                    <Typography variant="body2" sx={{ color: '#333', fontWeight: 600 }}>
                      {rules.find((rule) => rule.id === change.rule_id)?.name || change.rule_id}
                    </Typography>
                    <Typography variant="caption" sx={{ color: '#888' }}>
                      {change.rule_id}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={`${change.previous_enabled ? '启用' : '停用'} → ${
                        change.new_enabled ? '启用' : '停用'
                      }`}
                      sx={{
                        backgroundColor: change.new_enabled ? '#E8F5E9' : '#FFEBEE',
                        color: change.new_enabled ? '#2E7D32' : '#C62828',
                      }}
                    />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ color: '#555' }}>
                      {change.reason || '—'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="caption" sx={{ color: '#777' }}>
                      {change.created_at}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <PaginationFooter
            page={changePagination.page}
            pageCount={changePagination.pageCount}
            startIndex={changePagination.startIndex}
            endIndex={changePagination.endIndex}
            total={changePagination.total}
            onPageChange={setChangePage}
          />
        </TableContainer>
      </Box>
      )}

      {activeTab === 4 && (
      <Box>
        <Alert severity="info" sx={{ mb: 2 }}>
          规则模板仅作为成熟检查项参考，不会直接参与匹配。需要落地时，应先转成规则建议或草案，再审核发布。
        </Alert>
        <TableContainer
          component={Paper}
          sx={{ boxShadow: 'none', border: '1px solid #EDE7F6' }}
        >
          <Table size="small">
            <TableHead>
              <TableRow sx={{ backgroundColor: '#F9F7FF' }}>
                <TableCell sx={{ fontWeight: 600, color: '#666', width: '18%' }}>
                  模板
                </TableCell>
                <TableCell sx={{ fontWeight: 600, color: '#666', width: '12%' }}>
                  分类/风险
                </TableCell>
                <TableCell sx={{ fontWeight: 600, color: '#666', width: '20%' }}>
                  适用场景
                </TableCell>
                <TableCell sx={{ fontWeight: 600, color: '#666', width: '19%' }}>
                  证据要求
                </TableCell>
                <TableCell sx={{ fontWeight: 600, color: '#666', width: '23%' }}>
                  正反例/复核说明
                </TableCell>
                <TableCell sx={{ fontWeight: 600, color: '#666', width: '8%' }}>
                  操作
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading && (
                <TableRow>
                  <TableCell colSpan={6} align="center" sx={{ py: 5 }}>
                    <CircularProgress size={28} sx={{ color: '#7C4DFF' }} />
                  </TableCell>
                </TableRow>
              )}
              {!loading && templates.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} align="center" sx={{ py: 4 }}>
                    <Typography variant="body2" sx={{ color: '#999' }}>
                      暂无规则模板。
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
              {!loading &&
                templatePagination.items.map((template) => {
                  const risk = TEMPLATE_RISK_CONFIG[template.risk_level] || {
                    label: template.risk_level || '未分级',
                    color: '#666',
                    bg: '#F5F5F5',
                  };
                  return (
                    <TableRow key={template.id} hover>
                      <TableCell>
                        <Typography variant="body2" sx={{ color: '#333', fontWeight: 600 }}>
                          {template.name}
                        </Typography>
                        <Typography variant="caption" sx={{ color: '#888' }}>
                          {template.id}
                        </Typography>
                        <Typography variant="caption" sx={{ color: '#777', display: 'block', mt: 0.5 }}>
                          {getRuleTypeLabel(template.rule_type)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={template.category}
                          size="small"
                          sx={{ backgroundColor: '#EDE7F6', color: '#5E35B1', mb: 0.75 }}
                        />
                        <Chip
                          label={risk.label}
                          size="small"
                          sx={{
                            display: 'block',
                            width: 'fit-content',
                            color: risk.color,
                            backgroundColor: risk.bg,
                            border: `1px solid ${risk.color}`,
                          }}
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" sx={{ color: '#555' }}>
                          {template.applicable_scene}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                          {template.evidence_requirements.map((item) => (
                            <Chip key={item} label={item} size="small" sx={{ height: 22 }} />
                          ))}
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" sx={{ color: '#2E7D32', display: 'block' }}>
                          符合：{template.positive_examples[0] || '—'}
                        </Typography>
                        <Typography variant="caption" sx={{ color: '#C62828', display: 'block', mt: 0.5 }}>
                          不符合：{template.negative_examples[0] || '—'}
                        </Typography>
                        <Typography variant="caption" sx={{ color: '#777', display: 'block', mt: 0.75 }}>
                          {template.review_notes}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Button
                          size="small"
                          onClick={() => {
                            setPendingTemplateDraft(template);
                            setTemplateDraftReason('');
                          }}
                          disabled={creatingTemplateDraftId === template.id}
                          sx={{ minWidth: 0, color: '#7C4DFF', fontSize: 12 }}
                        >
                          生成草案
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
            </TableBody>
          </Table>
          <PaginationFooter
            page={templatePagination.page}
            pageCount={templatePagination.pageCount}
            startIndex={templatePagination.startIndex}
            endIndex={templatePagination.endIndex}
            total={templatePagination.total}
            onPageChange={setTemplatePage}
          />
        </TableContainer>
      </Box>
      )}

      <Dialog
        open={Boolean(pendingTemplateDraft)}
        onClose={() => {
          if (!creatingTemplateDraftId) {
            setPendingTemplateDraft(null);
            setTemplateDraftReason('');
          }
        }}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 700, color: '#333' }}>
          从模板生成规则草案
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ color: '#555', mb: 1 }}>
            {pendingTemplateDraft?.name || ''}
          </Typography>
          <Typography variant="caption" sx={{ color: '#777', display: 'block', mb: 2 }}>
            生成后会进入规则草案，仍需人工审核发布才会影响匹配。
          </Typography>
          <TextField
            size="small"
            fullWidth
            multiline
            minRows={3}
            label="使用原因"
            placeholder="说明为什么当前项目需要基于该模板新增规则口径"
            value={templateDraftReason}
            onChange={(event) => setTemplateDraftReason(event.target.value)}
            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button
            onClick={() => {
              setPendingTemplateDraft(null);
              setTemplateDraftReason('');
            }}
            disabled={Boolean(creatingTemplateDraftId)}
            sx={{ color: '#666' }}
          >
            取消
          </Button>
          <Button
            variant="contained"
            onClick={() => void handleCreateTemplateDraft()}
            disabled={
              Boolean(creatingTemplateDraftId) ||
              !canCreateRuleDraftFromTemplate(templateDraftReason)
            }
            sx={{
              backgroundColor: '#7C4DFF',
              '&:hover': { backgroundColor: '#651FFF' },
            }}
          >
            生成草案
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={Boolean(pendingChange)}
        onClose={() => {
          if (!savingRuleId) {
            setPendingChange(null);
            setChangeReason('');
          }
        }}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 700, color: '#333' }}>
          {pendingChange?.enabled ? '启用规则' : '停用规则'}
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ color: '#555', mb: 2 }}>
            {pendingChange?.rule.name || ''}
          </Typography>
          <TextField
            size="small"
            fullWidth
            multiline
            minRows={3}
            label="变更原因"
            value={changeReason}
            onChange={(event) => setChangeReason(event.target.value)}
            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button
            onClick={() => {
              setPendingChange(null);
              setChangeReason('');
            }}
            disabled={Boolean(savingRuleId)}
            sx={{ color: '#666' }}
          >
            取消
          </Button>
          <Button
            variant="contained"
            onClick={() => void handleEnabledChange()}
            disabled={Boolean(savingRuleId)}
            sx={{
              backgroundColor: '#7C4DFF',
              '&:hover': { backgroundColor: '#651FFF' },
            }}
          >
            确认
          </Button>
        </DialogActions>
      </Dialog>

      <Drawer
        anchor="right"
        open={Boolean(selectedRule)}
        onClose={() => setSelectedRule(null)}
        PaperProps={{
          sx: {
            width: { xs: '100%', md: 720 },
            maxWidth: '100%',
            backgroundColor: colors.canvas,
          },
        }}
      >
        <DialogTitle sx={{ fontWeight: 700, color: 'text.primary', backgroundColor: colors.surface }}>
          规则详情
        </DialogTitle>
        <DialogContent sx={{ p: 3 }}>
          {selectedRule && (
            <Box>
              <Typography variant="h6" sx={{ color: '#333', fontWeight: 700, mb: 0.5 }}>
                {selectedRule.name}
              </Typography>
              <Typography variant="caption" sx={{ color: '#888', display: 'block', mb: 2 }}>
                {selectedRule.id}
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                <CategoryTag category={selectedRule.domain} />
                <MandatoryTag level={STRICTNESS_LABELS[selectedRule.strictness]} />
                <Chip label={getRuleTypeLabel(selectedRule.rule_type)} size="small" sx={{ backgroundColor: '#FFF3E0', color: '#EF6C00' }} />
                <Chip
                  label={selectedRule.enabled ? '已启用' : '已停用'}
                  size="small"
                  sx={{
                    backgroundColor: selectedRule.enabled ? '#E8F5E9' : '#FFEBEE',
                    color: selectedRule.enabled ? '#2E7D32' : '#C62828',
                  }}
                />
              </Box>
              <Alert severity={selectedRule.rule_type === 'tighten_rule' ? 'warning' : 'info'} sx={{ mb: 2 }}>
                {getRuleImpactNotice(selectedRule.rule_type)}
              </Alert>
              <Typography variant="subtitle2" sx={{ color: '#333', fontWeight: 700 }}>
                规则说明
              </Typography>
              <Typography variant="body2" sx={{ color: '#555', whiteSpace: 'pre-wrap', mb: 2 }}>
                {selectedRule.description || '暂无说明'}
              </Typography>
              <Typography variant="subtitle2" sx={{ color: '#333', fontWeight: 700 }}>
                命中动作
              </Typography>
              <Typography variant="body2" sx={{ color: '#555', whiteSpace: 'pre-wrap', mb: 2 }}>
                {selectedRule.action || '暂无动作说明'}
              </Typography>
              <Typography variant="subtitle2" sx={{ color: '#333', fontWeight: 700 }}>
                关键词
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.75 }}>
                {selectedRule.keywords.length > 0 ? (
                  selectedRule.keywords.map((keyword) => (
                    <Chip key={keyword} label={keyword} size="small" sx={{ height: 22 }} />
                  ))
                ) : (
                  <Typography variant="body2" sx={{ color: '#888' }}>
                    暂无关键词，通常由草案内容或匹配规则文本决定。
                  </Typography>
                )}
              </Box>
              <Typography variant="subtitle2" sx={{ color: '#333', fontWeight: 700, mt: 2.5, mb: 1 }}>
                关系追溯
              </Typography>
              {loadingRuleRelations ? (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: '#777' }}>
                  <CircularProgress size={16} />
                  <Typography variant="body2">正在加载关系记录</Typography>
                </Box>
              ) : selectedRuleRelations.length > 0 ? (
                <TableContainer component={Paper} sx={{ boxShadow: 'none', border: '1px solid #EDE7F6' }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow sx={{ backgroundColor: '#F9F7FF' }}>
                        <TableCell sx={{ fontWeight: 600, color: '#666', width: '16%' }}>方向</TableCell>
                        <TableCell sx={{ fontWeight: 600, color: '#666', width: '14%' }}>关系</TableCell>
                        <TableCell sx={{ fontWeight: 600, color: '#666', width: '26%' }}>关联规则</TableCell>
                        <TableCell sx={{ fontWeight: 600, color: '#666', width: '32%' }}>说明</TableCell>
                        <TableCell sx={{ fontWeight: 600, color: '#666', width: '12%' }}>处理</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {selectedRuleRelations.map((relation) => (
                        <TableRow key={relation.id} hover>
                          <TableCell>
                            <Typography variant="body2" sx={{ color: '#555' }}>
                              {getRuleRelationDirectionLabel(relation.direction)}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip
                              size="small"
                              label={getRuleRelationTypeLabel(relation.relation_type)}
                              sx={{
                                backgroundColor: relation.relation_type === 'duplicate_of' ? '#E8F5E9' : '#FFF3E0',
                                color: relation.relation_type === 'duplicate_of' ? '#2E7D32' : '#EF6C00',
                              }}
                            />
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" sx={{ color: '#333', fontWeight: 600 }}>
                              {relation.related_rule_name || relation.related_rule_id}
                            </Typography>
                            <Typography variant="caption" sx={{ color: '#888', display: 'block' }}>
                              {relation.related_rule_source} / {relation.related_rule_status}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" sx={{ color: '#555', whiteSpace: 'pre-wrap' }}>
                              {relation.reason || '暂无说明'}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            {selectedRule &&
                            relation.relation_type !== 'merged_into' &&
                            canMergeRuleInto(selectedRule.id, relation.related_rule_id) ? (
                              <Button
                                size="small"
                                disabled={mergingRule}
                                onClick={() => {
                                  setPendingRuleMerge({ sourceRule: selectedRule, relation });
                                  setMergeReason(
                                    `与「${relation.related_rule_name || relation.related_rule_id}」重复，归并到该规则统一维护`,
                                  );
                                }}
                                sx={{ minWidth: 0, color: '#2E7D32', fontSize: 12 }}
                              >
                                归并
                              </Button>
                            ) : (
                              <Typography variant="caption" sx={{ color: '#AAA' }}>
                                -
                              </Typography>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Typography variant="body2" sx={{ color: '#888' }}>
                  暂无复用、相似或合并关系记录。
                </Typography>
              )}
              <Typography variant="subtitle2" sx={{ color: '#333', fontWeight: 700, mt: 2.5, mb: 1 }}>
                版本历史
              </Typography>
              {loadingRuleVersions ? (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: '#777' }}>
                  <CircularProgress size={16} />
                  <Typography variant="body2">正在加载版本历史</Typography>
                </Box>
              ) : selectedRuleVersions.length > 0 ? (
                <TableContainer component={Paper} sx={{ boxShadow: 'none', border: '1px solid #EDE7F6' }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow sx={{ backgroundColor: '#F9F7FF' }}>
                        <TableCell sx={{ fontWeight: 600, color: '#666', width: '9%' }}>版本</TableCell>
                        <TableCell sx={{ fontWeight: 600, color: '#666', width: '23%' }}>原规则名称</TableCell>
                        <TableCell sx={{ fontWeight: 600, color: '#666', width: '16%' }}>原类型</TableCell>
                        <TableCell sx={{ fontWeight: 600, color: '#666', width: '29%' }}>修改原因</TableCell>
                        <TableCell sx={{ fontWeight: 600, color: '#666', width: '13%' }}>时间</TableCell>
                        <TableCell sx={{ fontWeight: 600, color: '#666', width: '10%' }}>处理</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {selectedRuleVersions.map((version) => (
                        <TableRow key={version.id} hover>
                          <TableCell>
                            <Typography variant="body2" sx={{ color: '#333', fontWeight: 700 }}>
                              v{version.version_no}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" sx={{ color: '#333', fontWeight: 600 }}>
                              {version.name}
                            </Typography>
                            <Typography variant="caption" sx={{ color: '#888', display: 'block' }}>
                              {version.description}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" sx={{ color: '#555' }}>
                              {getRuleTypeLabel(version.rule_type)}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" sx={{ color: '#555', whiteSpace: 'pre-wrap' }}>
                              {version.edit_reason || '暂无原因'}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="caption" sx={{ color: '#888' }}>
                              {version.created_at}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            {selectedRule?.id.startsWith('custom.') ? (
                              <Button
                                size="small"
                                disabled={rollingBackRule}
                                onClick={() => {
                                  setPendingRuleRollback({ rule: selectedRule, version });
                                  setRollbackReason(`恢复到 v${version.version_no}：${version.name}`);
                                }}
                                sx={{ minWidth: 0, color: '#C62828', fontSize: 12 }}
                              >
                                回滚
                              </Button>
                            ) : (
                              <Typography variant="caption" sx={{ color: '#AAA' }}>
                                -
                              </Typography>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Typography variant="body2" sx={{ color: '#888' }}>
                  暂无版本历史。自定义规则每次编辑后，修改前内容会自动保存为历史版本。
                </Typography>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          {selectedRule?.id.startsWith('custom.') && (
            <Button
              onClick={() => openRuleEditor(selectedRule)}
              sx={{ color: '#5E35B1' }}
            >
              编辑规则
            </Button>
          )}
          <Button onClick={() => setSelectedRule(null)} sx={{ color: '#666' }}>
            关闭
          </Button>
        </DialogActions>
      </Drawer>

      <Dialog
        open={Boolean(editingRule)}
        onClose={() => {
          if (!savingRuleEdit) {
            closeRuleEditor();
          }
        }}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 700, color: '#333' }}>
          编辑自定义规则
        </DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            编辑已发布规则会影响后续匹配判断。保存时系统会记录修改前版本，便于追溯和回滚分析。
          </Alert>
          <TextField
            size="small"
            fullWidth
            label="规则名称"
            value={ruleForm.name}
            onChange={(event) => setRuleForm((prev) => ({ ...prev, name: event.target.value }))}
            sx={{ mb: 2, '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
          />
          <TextField
            size="small"
            fullWidth
            label="规则类型"
            value={ruleForm.rule_type}
            onChange={(event) => setRuleForm((prev) => ({ ...prev, rule_type: event.target.value }))}
            sx={{ mb: 2, '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
          />
          <TextField
            size="small"
            fullWidth
            multiline
            minRows={4}
            label="规则说明"
            value={ruleForm.description}
            onChange={(event) => setRuleForm((prev) => ({ ...prev, description: event.target.value }))}
            sx={{ mb: 2, '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
          />
          <TextField
            size="small"
            fullWidth
            required
            multiline
            minRows={3}
            label="修改原因"
            value={ruleForm.edit_reason}
            onChange={(event) => setRuleForm((prev) => ({ ...prev, edit_reason: event.target.value }))}
            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button
            onClick={closeRuleEditor}
            disabled={savingRuleEdit}
            sx={{ color: '#666' }}
          >
            取消
          </Button>
          <Button
            variant="contained"
            onClick={() => void handleUpdateCustomRule()}
            disabled={
              savingRuleEdit ||
              !editingRule ||
              !canUpdateCustomRule(
                editingRule.id,
                ruleForm.name,
                ruleForm.rule_type,
                ruleForm.description,
                ruleForm.edit_reason,
              )
            }
            sx={{
              backgroundColor: '#7C4DFF',
              '&:hover': { backgroundColor: '#651FFF' },
            }}
          >
            {savingRuleEdit ? '保存中' : '保存修改'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={Boolean(pendingRuleRollback)}
        onClose={() => {
          if (!rollingBackRule) {
            setPendingRuleRollback(null);
            setRollbackReason('');
          }
        }}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 700, color: '#333' }}>
          回滚规则版本
        </DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            回滚会把当前规则恢复到所选历史版本；系统会先保存当前内容，便于再次恢复。
          </Alert>
          <Typography variant="body2" sx={{ color: '#555', mb: 1 }}>
            当前规则：{pendingRuleRollback?.rule.name || ''}
          </Typography>
          <Typography variant="body2" sx={{ color: '#555', mb: 2 }}>
            回滚到：v{pendingRuleRollback?.version.version_no || ''} {pendingRuleRollback?.version.name || ''}
          </Typography>
          <TextField
            size="small"
            fullWidth
            required
            multiline
            minRows={3}
            label="回滚原因"
            value={rollbackReason}
            onChange={(event) => setRollbackReason(event.target.value)}
            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button
            onClick={() => {
              setPendingRuleRollback(null);
              setRollbackReason('');
            }}
            disabled={rollingBackRule}
            sx={{ color: '#666' }}
          >
            取消
          </Button>
          <Button
            variant="contained"
            onClick={() => void handleRollbackCustomRule()}
            disabled={
              rollingBackRule ||
              !pendingRuleRollback ||
              !canRollbackCustomRule(
                pendingRuleRollback.rule.id,
                pendingRuleRollback.version.version_no,
                rollbackReason,
              )
            }
            sx={{
              backgroundColor: '#7C4DFF',
              '&:hover': { backgroundColor: '#651FFF' },
            }}
          >
            {rollingBackRule ? '回滚中' : '确认回滚'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={Boolean(pendingRuleMerge)}
        onClose={() => {
          if (!mergingRule) {
            setPendingRuleMerge(null);
            setMergeReason('');
          }
        }}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 700, color: '#333' }}>
          归并重复规则
        </DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            归并后，当前自定义规则会被停用，并记录归并关系；目标规则继续作为主规则维护。
          </Alert>
          <Typography variant="body2" sx={{ color: '#555', mb: 1 }}>
            当前规则：{pendingRuleMerge?.sourceRule.name || ''}
          </Typography>
          <Typography variant="body2" sx={{ color: '#555', mb: 2 }}>
            归并到：{pendingRuleMerge?.relation.related_rule_name || pendingRuleMerge?.relation.related_rule_id || ''}
          </Typography>
          <TextField
            size="small"
            fullWidth
            multiline
            minRows={3}
            label="归并原因"
            value={mergeReason}
            onChange={(event) => setMergeReason(event.target.value)}
            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button
            onClick={() => {
              setPendingRuleMerge(null);
              setMergeReason('');
            }}
            disabled={mergingRule}
            sx={{ color: '#666' }}
          >
            取消
          </Button>
          <Button
            variant="contained"
            onClick={() => void handleMergeRule()}
            disabled={mergingRule || !mergeReason.trim()}
            sx={{
              backgroundColor: '#7C4DFF',
              '&:hover': { backgroundColor: '#651FFF' },
            }}
          >
            {mergingRule ? '处理中' : '确认归并'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={Boolean(selectedDraft)}
        onClose={() => setSelectedDraft(null)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 700, color: '#333' }}>
          草案详情
        </DialogTitle>
        <DialogContent>
          {selectedDraft && (
            <Box>
              <Typography variant="h6" sx={{ color: '#333', fontWeight: 700, mb: 0.5 }}>
                {selectedDraft.name}
              </Typography>
              <Typography variant="caption" sx={{ color: '#888', display: 'block', mb: 2 }}>
                来源建议：{selectedDraft.source_suggestion_id}
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                <Chip label={getRuleDraftStatusLabel(selectedDraft.draft_status)} size="small" sx={{ backgroundColor: '#FFF3E0', color: '#EF6C00' }} />
                <Chip label={getRuleTypeLabel(selectedDraft.rule_type)} size="small" sx={{ backgroundColor: '#EDE7F6', color: '#5E35B1' }} />
              </Box>
              <Alert severity={selectedDraft.rule_type === 'tighten_rule' ? 'warning' : 'info'} sx={{ mb: 2 }}>
                {getRuleImpactNotice(selectedDraft.rule_type)}
              </Alert>
              <Typography variant="subtitle2" sx={{ color: '#333', fontWeight: 700 }}>
                草案内容
              </Typography>
              <Typography variant="body2" sx={{ color: '#555', whiteSpace: 'pre-wrap', mb: 2 }}>
                {selectedDraft.draft_content}
              </Typography>
              {selectedDraft.review_reason && (
                <>
                  <Typography variant="subtitle2" sx={{ color: '#333', fontWeight: 700 }}>
                    审核/编辑原因
                  </Typography>
                  <Typography variant="body2" sx={{ color: '#555', whiteSpace: 'pre-wrap', mb: 2 }}>
                    {selectedDraft.review_reason}
                  </Typography>
                </>
              )}
              <Typography variant="caption" sx={{ color: '#888', display: 'block' }}>
                创建时间：{selectedDraft.created_at}
              </Typography>
              <Typography variant="caption" sx={{ color: '#888', display: 'block' }}>
                更新时间：{selectedDraft.updated_at}
              </Typography>
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          {selectedDraft?.draft_status === 'pending_review' && (
            <Button
              onClick={() => {
                const draft = selectedDraft;
                setSelectedDraft(null);
                openDraftEditor(draft);
              }}
              sx={{ color: '#7C4DFF' }}
            >
              编辑草案
            </Button>
          )}
          <Button onClick={() => setSelectedDraft(null)} sx={{ color: '#666' }}>
            关闭
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={Boolean(pendingSuggestionReview)}
        onClose={() => {
          setPendingSuggestionReview(null);
          setSuggestionReviewReason('');
        }}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 700, color: '#333' }}>
          {pendingSuggestionReview?.status === 'accepted' ? '采纳规则建议' : '忽略规则建议'}
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ color: '#555', mb: 2 }}>
            {pendingSuggestionReview?.suggestion.title || ''}
          </Typography>
          <TextField
            size="small"
            fullWidth
            multiline
            minRows={3}
            label="处理原因"
            value={suggestionReviewReason}
            onChange={(event) => setSuggestionReviewReason(event.target.value)}
            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button
            onClick={() => {
              setPendingSuggestionReview(null);
              setSuggestionReviewReason('');
            }}
            sx={{ color: '#666' }}
          >
            取消
          </Button>
          <Button
            variant="contained"
            onClick={() => void handleSuggestionReview()}
            sx={{
              backgroundColor: '#7C4DFF',
              '&:hover': { backgroundColor: '#651FFF' },
            }}
          >
            确认
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={Boolean(editingDraft)}
        onClose={closeDraftEditor}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 700, color: '#333' }}>
          编辑规则草案
        </DialogTitle>
        <DialogContent>
          <Alert severity="info" sx={{ mb: 2 }}>
            草案修改后仍需发布才会成为自定义规则；收紧规则只会把自动符合降级为需确认。
          </Alert>
          <TextField
            size="small"
            fullWidth
            label="规则草案名称"
            value={draftForm.name}
            onChange={(event) => setDraftForm((prev) => ({ ...prev, name: event.target.value }))}
            sx={{ mb: 2, '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
          />
          <TextField
            size="small"
            fullWidth
            label="规则类型"
            value={draftForm.rule_type}
            onChange={(event) =>
              setDraftForm((prev) => ({ ...prev, rule_type: event.target.value }))
            }
            helperText="当前建议保持 tighten_rule，表示只收紧自动通过结论。"
            sx={{ mb: 2, '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
          />
          <TextField
            size="small"
            fullWidth
            multiline
            minRows={6}
            label="草案内容"
            value={draftForm.draft_content}
            onChange={(event) =>
              setDraftForm((prev) => ({ ...prev, draft_content: event.target.value }))
            }
            sx={{ mb: 2, '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
          />
          <TextField
            size="small"
            fullWidth
            multiline
            minRows={2}
            label="编辑原因"
            value={draftForm.edit_reason}
            onChange={(event) =>
              setDraftForm((prev) => ({ ...prev, edit_reason: event.target.value }))
            }
            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={closeDraftEditor} sx={{ color: '#666' }}>
            取消
          </Button>
          <Button
            variant="contained"
            onClick={() => void handleDraftUpdate()}
            disabled={
              !draftForm.name.trim() ||
              !draftForm.rule_type.trim() ||
              !draftForm.draft_content.trim()
            }
            sx={{
              backgroundColor: '#7C4DFF',
              '&:hover': { backgroundColor: '#651FFF' },
            }}
          >
            保存草案
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={Boolean(pendingSimilarPublish)}
        onClose={() => {
          if (!reusingRuleId) {
            setPendingSimilarPublish(null);
            setReuseReason('');
            setDifferenceReason('');
          }
        }}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 700, color: '#333' }}>
          发布前发现相似规则
        </DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            当前草案可能与已有规则重复。建议先确认是否应复用、修改或合并；本次仍可继续发布，但后续会补充复用/合并流程。
          </Alert>
          <Typography variant="body2" sx={{ color: '#555', mb: 1.5 }}>
            待发布草案：{pendingSimilarPublish?.draft.name || ''}
          </Typography>
          <TextField
            size="small"
            fullWidth
            multiline
            minRows={2}
            required
            label="仍然发布的差异说明"
            value={differenceReason}
            onChange={(event) => setDifferenceReason(event.target.value)}
            helperText="如果确认不是重复规则，请写清楚适用对象、判断条件或证据要求的差异。"
            sx={{ mb: 2, '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
          />
          <TextField
            size="small"
            fullWidth
            multiline
            minRows={2}
            label="复用原因"
            value={reuseReason}
            onChange={(event) => setReuseReason(event.target.value)}
            sx={{ mb: 2, '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
          />
          <TableContainer component={Paper} sx={{ boxShadow: 'none', border: '1px solid #EDE7F6' }}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ backgroundColor: '#F9F7FF' }}>
                  <TableCell sx={{ fontWeight: 600, color: '#666', width: '24%' }}>相似规则</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: '#666', width: '14%' }}>来源/状态</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: '#666', width: '10%' }}>相似度</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: '#666', width: '38%' }}>相似原因</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: '#666', width: '14%' }}>处理</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {pendingSimilarPublish?.candidates.map((candidate) => (
                  <TableRow key={candidate.rule_id} hover>
                    <TableCell>
                      <Typography variant="body2" sx={{ color: '#333', fontWeight: 600 }}>
                        {candidate.name}
                      </Typography>
                      <Typography variant="caption" sx={{ color: '#888' }}>
                        {candidate.rule_id}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ color: '#555' }}>
                        {candidate.source}
                      </Typography>
                      <Typography variant="caption" sx={{ color: '#888' }}>
                        {candidate.status}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ color: '#C62828', fontWeight: 700 }}>
                        {Math.round(candidate.similarity * 100)}%
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ color: '#555' }}>
                        {candidate.reasons.join('；') || '文本内容接近'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Button
                        size="small"
                        disabled={Boolean(reusingRuleId)}
                        onClick={() => void handleReuseExistingRule(candidate)}
                        sx={{ minWidth: 0, color: '#2E7D32', fontSize: 12 }}
                      >
                        {reusingRuleId === candidate.rule_id ? '处理中' : '复用此规则'}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button
            onClick={() => {
              setPendingSimilarPublish(null);
              setReuseReason('');
              setDifferenceReason('');
            }}
            disabled={Boolean(reusingRuleId)}
            sx={{ color: '#666' }}
          >
            返回检查
          </Button>
          <Button
            variant="contained"
            onClick={() => {
              if (!pendingSimilarPublish) return;
              setPendingDraftReview({
                draft: pendingSimilarPublish.draft,
                status: 'published',
                similarRuleIds: pendingSimilarPublish.candidates.map((candidate) => candidate.rule_id),
                differenceReason: differenceReason.trim(),
              });
              setPendingSimilarPublish(null);
              setReuseReason('');
            }}
            disabled={Boolean(reusingRuleId) || !canPublishSimilarRuleDraft(differenceReason)}
            sx={{
              backgroundColor: '#7C4DFF',
              '&:hover': { backgroundColor: '#651FFF' },
            }}
          >
            仍然发布
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={Boolean(pendingDraftReview)}
        onClose={() => {
          setPendingDraftReview(null);
          setDraftReviewReason('');
          setDifferenceReason('');
        }}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 700, color: '#333' }}>
          {pendingDraftReview?.status === 'published' ? '发布规则草案' : '驳回规则草案'}
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ color: '#555', mb: 2 }}>
            {pendingDraftReview?.draft.name || ''}
          </Typography>
          <TextField
            size="small"
            fullWidth
            multiline
            minRows={3}
            label="审核原因"
            value={draftReviewReason}
            onChange={(event) => setDraftReviewReason(event.target.value)}
            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button
            onClick={() => {
              setPendingDraftReview(null);
              setDraftReviewReason('');
              setDifferenceReason('');
            }}
            sx={{ color: '#666' }}
          >
            取消
          </Button>
          <Button
            variant="contained"
            onClick={() => void handleDraftReview()}
            sx={{
              backgroundColor: '#7C4DFF',
              '&:hover': { backgroundColor: '#651FFF' },
            }}
          >
            确认
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

const PaginationFooter: React.FC<{
  page: number;
  pageCount: number;
  startIndex: number;
  endIndex: number;
  total: number;
  onPageChange: (page: number) => void;
}> = ({
  page,
  pageCount,
  startIndex,
  endIndex,
  total,
  onPageChange,
}) => (
  <Box
    sx={{
      minHeight: 52,
      px: 2,
      borderTop: '1px solid #EDE7F6',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'flex-end',
      gap: 1.5,
      flexWrap: 'wrap',
    }}
  >
    <Typography variant="caption" sx={{ color: '#888' }}>
      {total > 0 ? `${startIndex + 1}–${endIndex} / 共 ${total} 项` : `0 / 共 ${total} 项`}
    </Typography>
    <Pagination
      count={pageCount}
      page={page}
      onChange={(_event, nextPage) => onPageChange(nextPage)}
      size="small"
      color="primary"
      shape="rounded"
      showFirstButton
      showLastButton
    />
  </Box>
);

export default RuleLibraryPage;
