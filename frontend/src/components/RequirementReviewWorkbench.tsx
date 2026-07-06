import React, { useDeferredValue, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Divider,
  Drawer,
  FormControl,
  IconButton,
  InputAdornment,
  LinearProgress,
  MenuItem,
  Pagination,
  Select,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import LaunchIcon from '@mui/icons-material/Launch';
import SearchIcon from '@mui/icons-material/Search';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';

import {
  ActionTag,
  CategoryTag,
  MandatoryTag,
  StatusTag,
  type StatusKind,
} from './StatusTags';
import {
  batchDeleteRequirements,
  batchUpdateRequirementStatus,
  createRequirement,
  deleteRequirement,
  getTenderPdfUrl,
  updateRequirement,
} from '../api/tenders';
import {
  filterRequirements,
  filterRequirementsByMatch,
  filterRequirementsByNature,
  getRequirementReviewState,
  type RequirementReviewState,
} from '../pages/tenderRequirementView';
import { paginateItems } from '../utils/pagination';
import type {
  MatchResult,
  MatchProgress,
  MatchStatus,
  Qualification,
  RequirementCategory,
  RequirementNature,
  Tender,
  TenderRequirement,
  TenderRequirementInput,
} from '../types';
import { colors } from '../theme';

const CATEGORY_LABELS: Record<RequirementCategory, string> = {
  qualification: '资质',
  performance: '业绩',
  financial: '财务',
  personnel: '人员',
  other: '其他',
  product_spec: '产品参数',
  submission: '提交件',
};

const NATURE_LABELS: Record<RequirementNature, string> = {
  capability: '能力要求',
  submission: '提交材料',
};

const PAGE_SIZE = 10;

const EMPTY_DRAFT: TenderRequirementInput = {
  category: 'other',
  requirement_nature: 'capability',
  title: '',
  content: '',
  is_hard: false,
  raw_text: '',
  page_number: null,
  numeric_operator: null,
  numeric_value: null,
  numeric_unit: null,
  review_status: 'pending',
};

const getRequirementDetailText = (item: TenderRequirement) =>
  `${item.content}${
    item.numeric_operator && item.numeric_value
      ? ` · ${item.numeric_operator} ${item.numeric_value}${item.numeric_unit || ''}`
      : ''
  }`;

const ClampedRequirementText: React.FC<{ requirement: TenderRequirement }> = ({
  requirement,
}) => {
  const detail = getRequirementDetailText(requirement);

  return (
    <Tooltip title={`${requirement.title}：${detail}`} arrow placement="top-start">
      <Box sx={{ minWidth: 0, cursor: 'default' }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 0.75,
            minWidth: 0,
            mb: 0.25,
          }}
        >
          <MandatoryTag level={requirement.is_hard ? '硬性' : '软性'} />
          <Typography
            variant="body2"
            sx={{
              fontWeight: 650,
              color: 'text.primary',
              minWidth: 0,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {requirement.title}
          </Typography>
        </Box>
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {detail}
        </Typography>
      </Box>
    </Tooltip>
  );
};

interface RequirementReviewWorkbenchProps {
  tender: Tender;
  requirements: TenderRequirement[];
  matchResults: MatchResult[];
  qualifications: Qualification[];
  onRequirementsChange: (
    requirements: TenderRequirement[],
    invalidateMatch?: boolean,
  ) => void;
  onStartMatch: () => void;
  matching: boolean;
  matchProgress: MatchProgress | null;
}

const RequirementReviewWorkbench: React.FC<
  RequirementReviewWorkbenchProps
> = ({
  tender,
  requirements,
  matchResults,
  qualifications,
  onRequirementsChange,
  onStartMatch,
  matching,
  matchProgress,
}) => {
  const [keyword, setKeyword] = useState('');
  const deferredKeyword = useDeferredValue(keyword);
  const [category, setCategory] = useState<RequirementCategory | 'all'>('all');
  const [natureFilter, setNatureFilter] = useState<RequirementNature | 'all'>('all');
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [editingId, setEditingId] = useState<number | 'new' | null>(null);
  const [draft, setDraft] = useState<TenderRequirementInput>(EMPTY_DRAFT);
  const [saving, setSaving] = useState(false);
  const [batchBusy, setBatchBusy] = useState(false);
  const [drawerRequirementId, setDrawerRequirementId] = useState<number | null>(
    null,
  );

  const hasMatchResults = matchResults.length > 0;
  const matchByRequirement = useMemo(
    () =>
      new Map(
        matchResults.map((result) => [result.requirement_id, result] as const),
      ),
    [matchResults],
  );
  const qualificationById = useMemo(
    () =>
      new Map(
        qualifications.map(
          (qualification) => [qualification.id, qualification] as const,
        ),
      ),
    [qualifications],
  );

  const categoryCounts = useMemo(() => {
    const result: Record<RequirementCategory, number> = {
      qualification: 0,
      performance: 0,
      financial: 0,
      personnel: 0,
      other: 0,
      product_spec: 0,
      submission: 0,
    };
    requirements.forEach((item) => {
      if (item.category in result) {
        result[item.category] += 1;
      }
    });
    return result;
  }, [requirements]);
  const natureCounts = useMemo(
    () => ({
      all: requirements.length,
      capability: requirements.filter(
        (item) => item.requirement_nature === 'capability',
      ).length,
      submission: requirements.filter(
        (item) => item.requirement_nature === 'submission',
      ).length,
    }),
    [requirements],
  );
  const filtered = useMemo(() => {
    const base = filterRequirements(requirements, {
      category,
      state: 'all',
      keyword: deferredKeyword,
    });
    const natureFiltered = filterRequirementsByNature(base, natureFilter);
    return hasMatchResults
      ? filterRequirementsByMatch(natureFiltered, matchResults, 'all')
      : natureFiltered;
  }, [
    category,
    deferredKeyword,
    hasMatchResults,
    matchResults,
    natureFilter,
    requirements,
  ]);
  const pagination = useMemo(
    () => paginateItems(filtered, page, PAGE_SIZE),
    [filtered, page],
  );
  const pageItems = pagination.items;

  useEffect(() => {
    setPage(1);
  }, [
    category,
    deferredKeyword,
    hasMatchResults,
    natureFilter,
  ]);

  useEffect(() => {
    if (page !== pagination.page) {
      setPage(pagination.page);
    }
  }, [page, pagination.page]);

  const drawerRequirement =
    requirements.find((item) => item.id === drawerRequirementId) || null;
  const visibleSelectedCount = pageItems.filter((item) =>
    selectedIds.has(item.id),
  ).length;
  const allVisibleSelected =
    pageItems.length > 0 && visibleSelectedCount === pageItems.length;
  const tableColumnCount = hasMatchResults ? 9 : 7;

  const startEdit = (requirement?: TenderRequirement) => {
    if (!requirement) {
      setEditingId('new');
      setDraft(EMPTY_DRAFT);
      return;
    }
    setEditingId(requirement.id);
    setDraft({
      category: requirement.category,
      requirement_nature: requirement.requirement_nature,
      title: requirement.title,
      content: requirement.content,
      is_hard: requirement.is_hard,
      raw_text: requirement.raw_text,
      page_number: requirement.page_number,
      numeric_operator: requirement.numeric_operator,
      numeric_value: requirement.numeric_value,
      numeric_unit: requirement.numeric_unit,
      review_status: requirement.review_status,
    });
  };

  const saveDraft = async () => {
    if (!draft.title?.trim() || !draft.content?.trim()) return;
    setSaving(true);
    try {
      if (editingId === 'new') {
        const created = await createRequirement(tender.id, draft);
        onRequirementsChange([...requirements, created], true);
        setPage(1);
      } else if (typeof editingId === 'number') {
        const updated = await updateRequirement(tender.id, editingId, draft);
        onRequirementsChange(
          requirements.map((item) => (item.id === editingId ? updated : item)),
          true,
        );
      }
      setEditingId(null);
    } finally {
      setSaving(false);
    }
  };

  const confirmOne = async (requirement: TenderRequirement) => {
    const updated = await updateRequirement(tender.id, requirement.id, {
      review_status: 'confirmed',
    });
    onRequirementsChange(
      requirements.map((item) => (item.id === updated.id ? updated : item)),
      false,
    );
  };

  const removeOne = async (requirement: TenderRequirement) => {
    if (!window.confirm(`确定删除“${requirement.title}”吗？`)) return;
    await deleteRequirement(tender.id, requirement.id);
    onRequirementsChange(
      requirements.filter((item) => item.id !== requirement.id),
      true,
    );
    setSelectedIds((current) => {
      const next = new Set(current);
      next.delete(requirement.id);
      return next;
    });
  };

  const confirmSelected = async () => {
    const ids = [...selectedIds];
    if (!ids.length) return;
    setBatchBusy(true);
    try {
      await batchUpdateRequirementStatus(tender.id, ids, 'confirmed');
      onRequirementsChange(
        requirements.map((item) =>
          selectedIds.has(item.id)
            ? { ...item, review_status: 'confirmed' }
            : item,
        ),
        false,
      );
      setSelectedIds(new Set());
    } finally {
      setBatchBusy(false);
    }
  };

  const deleteSelected = async () => {
    const ids = [...selectedIds];
    if (!ids.length) return;
    if (!window.confirm(`确定批量删除已选择的 ${ids.length} 项要求吗？`)) {
      return;
    }
    setBatchBusy(true);
    try {
      await batchDeleteRequirements(tender.id, ids);
      onRequirementsChange(
        requirements.filter((item) => !selectedIds.has(item.id)),
        true,
      );
      setSelectedIds(new Set());
    } finally {
      setBatchBusy(false);
    }
  };

  const openSource = (requirement: TenderRequirement) => {
    setDrawerRequirementId(requirement.id);
  };

  return (
    <Box>
      <Box
        sx={{
          border: '1px solid #E7E1F2',
          backgroundColor: '#FFF',
          p: 1.5,
          mb: 1.5,
        }}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 2,
            flexWrap: 'wrap',
          }}
        >
          <Typography variant="body2" sx={{ color: '#444' }}>
            共提取 <strong>{requirements.length}</strong> 项要求
            {' · '}资质 {categoryCounts.qualification}
            {' · '}业绩 {categoryCounts.performance}
            {' · '}财务 {categoryCounts.financial}
            {' · '}人员 {categoryCounts.personnel}
            {' · '}产品参数 {categoryCounts.product_spec}
            {' · '}提交件 {categoryCounts.submission}
            {' · '}其他 {categoryCounts.other}
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <TextField
              size="small"
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="搜索解析结果…"
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon sx={{ fontSize: 18, color: '#AAA' }} />
                  </InputAdornment>
                ),
              }}
              sx={{
                width: { xs: '100%', sm: 280 },
                '& .MuiOutlinedInput-root': { borderRadius: 0 },
              }}
            />
            <Button
              variant="contained"
              onClick={onStartMatch}
              disabled={matching || requirements.length === 0}
              sx={{
                minWidth: 176,
                borderRadius: 0,
                backgroundColor: '#7C4DFF',
                '&:hover': { backgroundColor: '#651FFF' },
              }}
            >
              {matching ? (
                <>
                  <CircularProgress size={17} color="inherit" sx={{ mr: 1 }} />
                  正在匹配
                </>
              ) : hasMatchResults ? (
                '重新匹配资质库'
              ) : (
                '与资质库匹配'
              )}
            </Button>
          </Box>
        </Box>

        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1.25 }}>
          <ToggleButtonGroup
            value={natureFilter}
            exclusive
            size="small"
            onChange={(_event, value: RequirementNature | 'all' | null) => {
              if (value) setNatureFilter(value);
            }}
            sx={{
              '& .MuiToggleButton-root': {
                height: 30,
                px: 1.5,
                borderColor: colors.divider,
                fontSize: 12,
                fontWeight: 600,
                color: 'text.secondary',
                '&.Mui-selected': {
                  color: 'primary.main',
                  backgroundColor: 'rgba(124, 92, 252, 0.10)',
                },
              },
            }}
          >
            <ToggleButton value="all">全部 {natureCounts.all}</ToggleButton>
            <ToggleButton value="capability">
              能力要求 {natureCounts.capability}
            </ToggleButton>
            <ToggleButton value="submission">
              提交资料 {natureCounts.submission}
            </ToggleButton>
          </ToggleButtonGroup>
          <FormControl size="small" sx={{ minWidth: 130, ml: { sm: 1 } }}>
            <Select
              value={category}
              onChange={(event) =>
                setCategory(event.target.value as RequirementCategory | 'all')
              }
              sx={{ borderRadius: 0, height: 28, fontSize: 12 }}
            >
              <MenuItem value="all">全部类别</MenuItem>
              {(Object.keys(CATEGORY_LABELS) as RequirementCategory[]).map(
                (value) => (
                  <MenuItem key={value} value={value}>
                    {CATEGORY_LABELS[value]}（{categoryCounts[value]}）
                  </MenuItem>
                ),
              )}
            </Select>
          </FormControl>
        </Box>
      </Box>

      {matching && (
        <Alert severity="info" sx={{ mb: 1.5, borderRadius: 0 }}>
          <Box sx={{ width: '100%' }}>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 2,
                mb: 0.75,
              }}
            >
              <Typography variant="body2" sx={{ fontWeight: 650 }}>
                {matchProgress?.message || '正在逐项与资质库匹配'}
              </Typography>
              <Typography variant="caption" sx={{ color: '#555', whiteSpace: 'nowrap' }}>
                {matchProgress?.total
                  ? `${matchProgress.current}/${matchProgress.total}`
                  : matchProgress?.status === 'queued'
                    ? '排队中'
                    : '处理中'}
              </Typography>
            </Box>
            <LinearProgress
              variant={matchProgress?.total ? 'determinate' : 'indeterminate'}
              value={
                matchProgress?.total
                  ? Math.min(100, (matchProgress.current / matchProgress.total) * 100)
                  : undefined
              }
              sx={{
                height: 7,
                borderRadius: 99,
                backgroundColor: '#E9E1FF',
                '& .MuiLinearProgress-bar': { backgroundColor: '#7C4DFF' },
              }}
            />
            <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', mt: 0.75 }}>
              {matchProgress?.current_requirement && (
                <Typography variant="caption" sx={{ color: '#555' }}>
                  当前：{matchProgress.current_requirement}
                </Typography>
              )}
              <Typography variant="caption" sx={{ color: '#2E7D32' }}>
                已匹配 {matchProgress?.matched ?? 0}
              </Typography>
              <Typography variant="caption" sx={{ color: '#C62828' }}>
                不匹配 {matchProgress?.unmatched ?? 0}
              </Typography>
              <Typography variant="caption" sx={{ color: '#B56A00' }}>
                待确认 {matchProgress?.needs_review ?? 0}
              </Typography>
            </Box>
          </Box>
        </Alert>
      )}

      <Box
        sx={{
          border: '1px solid #E7E1F2',
          backgroundColor: '#FFF',
        }}
      >
        <TableContainer>
          <Table
            size="small"
            sx={{
              tableLayout: 'fixed',
              '& .MuiTableCell-root': {
                px: 1.5,
                py: 0.75,
                borderColor: colors.divider,
                fontSize: 13,
              },
              '& .MuiTableRow-root': {
                contentVisibility: 'auto',
              },
            }}
          >
            <TableHead>
              <TableRow>
                <TableCell padding="checkbox" sx={{ width: 38 }}>
                  <Checkbox
                    size="small"
                    checked={allVisibleSelected}
                    indeterminate={
                      visibleSelectedCount > 0 && !allVisibleSelected
                    }
                    onChange={(event) => {
                      setSelectedIds((current) => {
                        const next = new Set(current);
                        pageItems.forEach((item) => {
                          if (event.target.checked) next.add(item.id);
                          else next.delete(item.id);
                        });
                        return next;
                      });
                    }}
                  />
                </TableCell>
                <TableCell sx={{ width: 44 }}>序号</TableCell>
                <TableCell sx={{ width: 78 }}>解析状态</TableCell>
                <TableCell sx={{ width: 60 }}>类别</TableCell>
                <TableCell>AI 提取的需求及核心指标</TableCell>
                {hasMatchResults && (
                  <>
                    <TableCell sx={{ width: 190 }}>我的资质</TableCell>
                    <TableCell sx={{ width: 92 }}>匹配状态</TableCell>
                  </>
                )}
                <TableCell sx={{ width: 92 }}>原文页码</TableCell>
                <TableCell sx={{ width: 104 }}>操作</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {editingId === 'new' && (
                <EditorRow
                  colSpan={tableColumnCount}
                  draft={draft}
                  setDraft={setDraft}
                  saving={saving}
                  onSave={saveDraft}
                  onCancel={() => setEditingId(null)}
                />
              )}
              {pageItems.map((item, index) => {
                const checked = selectedIds.has(item.id);
                const reviewState = getRequirementReviewState(item);
                const matchResult = matchByRequirement.get(item.id);
                const qualification = matchResult?.qualification_id
                  ? qualificationById.get(matchResult.qualification_id)
                  : null;
                return (
                  <React.Fragment key={item.id}>
                    <TableRow
                      hover
                      className="zebra"
                      onClick={() => openSource(item)}
                      sx={{
                        cursor: 'pointer',
                        height: 40,
                        '&:hover': {
                          backgroundColor: 'rgba(124, 92, 252, 0.06) !important',
                        },
                      }}
                    >
                      <TableCell padding="checkbox">
                        <Checkbox
                          size="small"
                          checked={checked}
                          onClick={(event) => event.stopPropagation()}
                          onChange={() =>
                            setSelectedIds((current) => {
                              const next = new Set(current);
                              if (next.has(item.id)) next.delete(item.id);
                              else next.add(item.id);
                              return next;
                            })
                          }
                        />
                      </TableCell>
                      <TableCell>{pagination.startIndex + index + 1}</TableCell>
                      <TableCell>
                        <ReviewStateChip state={reviewState} />
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'grid', gap: 0.25, justifyItems: 'start' }}>
                          <CategoryTag category={CATEGORY_LABELS[item.category]} />
                          <Typography variant="caption" color="text.secondary">
                            {NATURE_LABELS[item.requirement_nature]}
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <ClampedRequirementText requirement={item} />
                      </TableCell>
                      {hasMatchResults && (
                        <>
                          <TableCell>
                            <Typography
                              variant="caption"
                              sx={{
                                display: 'block',
                                color: qualification ? '#333' : '#888',
                                fontWeight: qualification ? 650 : 400,
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                              }}
                            >
                              {qualification?.name ||
                                matchResult?.expected_qualification ||
                                '资质库中未找到对应资质'}
                            </Typography>
                            {qualification?.number && (
                              <Typography
                                variant="caption"
                                sx={{ color: '#888', fontSize: 10 }}
                              >
                                {qualification.number}
                              </Typography>
                            )}
                          </TableCell>
                          <TableCell>
                            <MatchStateChip
                              state={matchResult?.match_status || 'missing'}
                            />
                          </TableCell>
                        </>
                      )}
                      <TableCell>
                        <Button
                          size="small"
                          startIcon={<LaunchIcon sx={{ fontSize: 13 }} />}
                          onClick={(event) => {
                            event.stopPropagation();
                            openSource(item);
                          }}
                          sx={{
                            minWidth: 0,
                            p: 0,
                            fontSize: 11,
                            color: item.page_number ? '#7C4DFF' : '#D96C00',
                          }}
                        >
                          {item.page_number ? `P${item.page_number}` : '定位失败'}
                        </Button>
                      </TableCell>
                      <TableCell>
                        <Box
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'flex-end',
                            gap: 0.5,
                          }}
                        >
                          <Tooltip title="编辑">
                            <IconButton
                              size="small"
                              onClick={(event) => {
                                event.stopPropagation();
                                startEdit(item);
                              }}
                              sx={{ color: 'text.secondary' }}
                            >
                              <EditOutlinedIcon sx={{ fontSize: 16 }} />
                            </IconButton>
                          </Tooltip>
                          {item.review_status !== 'confirmed' && (
                            <Tooltip title="确认无误">
                              <IconButton
                                size="small"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  void confirmOne(item);
                                }}
                                sx={{ color: colors.status.success }}
                              >
                                <CheckIcon sx={{ fontSize: 16 }} />
                              </IconButton>
                            </Tooltip>
                          )}
                          <Divider
                            orientation="vertical"
                            flexItem
                            sx={{ mx: 0.5, height: 16, alignSelf: 'center' }}
                          />
                          <Tooltip title="删除">
                            <IconButton
                              size="small"
                              onClick={(event) => {
                                event.stopPropagation();
                                void removeOne(item);
                              }}
                              sx={{
                                color: 'text.secondary',
                                '&:hover': {
                                  color: 'error.main',
                                  backgroundColor: colors.status.errorBg,
                                },
                              }}
                            >
                              <DeleteOutlineIcon sx={{ fontSize: 16 }} />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      </TableCell>
                    </TableRow>
                    {editingId === item.id && (
                      <EditorRow
                        colSpan={tableColumnCount}
                        draft={draft}
                        setDraft={setDraft}
                        saving={saving}
                        onSave={saveDraft}
                        onCancel={() => setEditingId(null)}
                      />
                    )}
                  </React.Fragment>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>

        <Box
          sx={{
            minHeight: 49,
            px: 1.5,
            borderTop: '1px solid #E7E1F2',
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            flexWrap: 'wrap',
          }}
        >
          <Button
            size="small"
            startIcon={<AddIcon />}
            onClick={() => startEdit()}
            sx={{ color: '#7C4DFF' }}
          >
            手动添加需求项
          </Button>
          <Typography variant="body2" sx={{ color: '#666', ml: 1 }}>
            已选 {selectedIds.size} 项
          </Typography>
          <Button
            size="small"
            variant="outlined"
            disabled={!selectedIds.size || batchBusy}
            onClick={() => void confirmSelected()}
            sx={{ borderRadius: 0 }}
          >
            批量确认无误
          </Button>
          <Button
            size="small"
            color="error"
            disabled={!selectedIds.size || batchBusy}
            onClick={() => void deleteSelected()}
          >
            批量删除
          </Button>
          {batchBusy && <CircularProgress size={18} />}
          <Box
            sx={{
              ml: 'auto',
              display: 'flex',
              alignItems: 'center',
              gap: 1.5,
              flexWrap: 'wrap',
            }}
          >
            <Typography variant="caption" sx={{ color: '#888' }}>
              {pagination.total
                ? `${pagination.startIndex + 1}–${pagination.endIndex} / 共 ${pagination.total} 项`
                : '共 0 项'}
            </Typography>
            <Pagination
              count={pagination.pageCount}
              page={pagination.page}
              onChange={(_event, nextPage) => setPage(nextPage)}
              size="small"
              color="primary"
              shape="rounded"
              showFirstButton
              showLastButton
            />
          </Box>
        </Box>
      </Box>

      <SourceDrawer
        tender={tender}
        requirement={drawerRequirement}
        open={drawerRequirement !== null}
        onClose={() => setDrawerRequirementId(null)}
      />
    </Box>
  );
};

const SourceDrawer: React.FC<{
  tender: Tender;
  requirement: TenderRequirement | null;
  open: boolean;
  onClose: () => void;
}> = ({ tender, requirement, open, onClose }) => {
  const pdfUrl = getTenderPdfUrl(
    tender.id,
    requirement?.page_number || undefined,
  );
  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{
        sx: {
          width: { xs: '100%', md: '48vw' },
          minWidth: { md: 540 },
          maxWidth: 820,
          backgroundColor: '#F7F5FA',
        },
      }}
    >
      <Box
        sx={{
          p: 1.5,
          borderBottom: '1px solid #DDD6E8',
          backgroundColor: '#FFF',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography
            variant="subtitle1"
            sx={{ fontWeight: 700, color: '#333', flex: 1 }}
          >
            {requirement?.title || '标书原文'}
          </Typography>
          {requirement?.page_number ? (
            <Typography variant="caption" sx={{ color: '#666' }}>
              第 {requirement.page_number} 页 / 共 {tender.total_pages || '—'} 页
            </Typography>
          ) : (
            <Chip
              icon={<WarningAmberIcon />}
              label="页码定位失败"
              size="small"
              sx={{
                borderRadius: 0,
                color: '#D96C00',
                backgroundColor: '#FFF1DE',
                '& .MuiChip-icon': { color: '#D96C00' },
              }}
            />
          )}
          <Tooltip title="新窗口打开 PDF">
            <IconButton component="a" href={pdfUrl} target="_blank" size="small">
              <LaunchIcon sx={{ fontSize: 18 }} />
            </IconButton>
          </Tooltip>
          <IconButton size="small" onClick={onClose}>
            <CloseIcon />
          </IconButton>
        </Box>
        {requirement && (
          <Box
            sx={{
              mt: 1,
              px: 1,
              py: 0.75,
              borderLeft: '3px solid #FFB45C',
              backgroundColor: '#FFF8ED',
            }}
          >
            <Typography variant="caption" sx={{ color: '#666' }}>
              AI 定位原文：
            </Typography>
            <Typography
              component="mark"
              variant="caption"
              sx={{
                color: '#4A4035',
                backgroundColor: '#FFE2A8',
                ml: 0.5,
              }}
            >
              {requirement.raw_text || requirement.content}
            </Typography>
          </Box>
        )}
      </Box>
      <Box sx={{ flex: 1, p: 1.25, minHeight: 0 }}>
        {open && (
          <Box
            component="iframe"
            key={`${requirement?.id || 'none'}-${requirement?.page_number || 0}`}
            title="标书原文 PDF"
            src={pdfUrl}
            sx={{
              width: '100%',
              height: '100%',
              minHeight: 600,
              border: '1px solid #D7D1DF',
              backgroundColor: '#FFF',
            }}
          />
        )}
      </Box>
    </Drawer>
  );
};

const ReviewStateChip: React.FC<{
  state: Exclude<RequirementReviewState, 'all'>;
}> = ({ state }) => {
  const config = {
    location_failed: {
      label: '定位失败',
      action: true,
    },
    pending: {
      label: '待确认',
      kind: 'neutral',
    },
    confirmed: {
      label: '已确认',
      kind: 'success',
    },
  }[state];

  return 'action' in config ? (
    <ActionTag label={config.label} />
  ) : (
    <StatusTag kind={config.kind as StatusKind} label={config.label} />
  );
};

const MatchStateChip: React.FC<{ state: MatchStatus | 'missing' }> = ({
  state,
}) => {
  const config = {
    unmatched: {
      label: '不匹配',
      kind: 'error',
    },
    needs_review: {
      label: '待核对',
      action: true,
    },
    missing: {
      label: '无结果',
      kind: 'neutral',
    },
    matched: {
      label: '已匹配',
      kind: 'success',
    },
  }[state];

  return 'action' in config ? (
    <ActionTag label={config.label} />
  ) : (
    <StatusTag kind={config.kind as StatusKind} label={config.label} />
  );
};

interface EditorRowProps {
  colSpan: number;
  draft: TenderRequirementInput;
  setDraft: React.Dispatch<React.SetStateAction<TenderRequirementInput>>;
  saving: boolean;
  onSave: () => void;
  onCancel: () => void;
}

const EditorRow: React.FC<EditorRowProps> = ({
  colSpan,
  draft,
  setDraft,
  saving,
  onSave,
  onCancel,
}) => (
  <TableRow>
    <TableCell
      colSpan={colSpan}
      sx={{ p: '8px !important', backgroundColor: '#FAF8FF' }}
    >
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: {
            xs: '1fr 1fr',
            lg: '100px 80px minmax(140px, 1fr) 80px 80px 80px 80px',
          },
          gap: 0.75,
          alignItems: 'start',
        }}
      >
        <FormControl size="small">
          <Select
            value={draft.category || 'other'}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                category: event.target.value as RequirementCategory,
              }))
            }
            sx={{ borderRadius: 0, fontSize: 12 }}
          >
            {(Object.keys(CATEGORY_LABELS) as RequirementCategory[]).map(
              (value) => (
                <MenuItem key={value} value={value}>
                  {CATEGORY_LABELS[value]}
                </MenuItem>
              ),
            )}
          </Select>
        </FormControl>
        <FormControl size="small">
          <Select
            value={draft.requirement_nature || 'capability'}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                requirement_nature: event.target.value as RequirementNature,
              }))
            }
            sx={{ borderRadius: 0, fontSize: 12 }}
          >
            {(Object.keys(NATURE_LABELS) as RequirementNature[]).map(
              (value) => (
                <MenuItem key={value} value={value}>
                  {NATURE_LABELS[value]}
                </MenuItem>
              ),
            )}
          </Select>
        </FormControl>
        <TextField
          size="small"
          label="要求标题"
          value={draft.title || ''}
          onChange={(event) =>
            setDraft((current) => ({ ...current, title: event.target.value }))
          }
          sx={{ '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
        />
        <TextField
          size="small"
          label="页码"
          type="number"
          value={draft.page_number ?? ''}
          onChange={(event) =>
            setDraft((current) => ({
              ...current,
              page_number: event.target.value
                ? Number(event.target.value)
                : null,
            }))
          }
          sx={{ '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
        />
        <TextField
          size="small"
          label="运算符"
          value={draft.numeric_operator || ''}
          onChange={(event) =>
            setDraft((current) => ({
              ...current,
              numeric_operator: event.target.value || null,
            }))
          }
          sx={{ '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
        />
        <TextField
          size="small"
          label="数值"
          value={draft.numeric_value || ''}
          onChange={(event) =>
            setDraft((current) => ({
              ...current,
              numeric_value: event.target.value || null,
            }))
          }
          sx={{ '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
        />
        <TextField
          size="small"
          label="单位"
          value={draft.numeric_unit || ''}
          onChange={(event) =>
            setDraft((current) => ({
              ...current,
              numeric_unit: event.target.value || null,
            }))
          }
          sx={{ '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
        />
      </Box>
      <TextField
        size="small"
        fullWidth
        multiline
        minRows={2}
        label="完整要求内容"
        value={draft.content || ''}
        onChange={(event) =>
          setDraft((current) => ({ ...current, content: event.target.value }))
        }
        sx={{ mt: 0.75, '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
      />
      <Box sx={{ display: 'flex', alignItems: 'center', mt: 0.75, gap: 1 }}>
        <Button
          size="small"
          variant="contained"
          disabled={saving}
          onClick={onSave}
        >
          保存
        </Button>
        <Button size="small" onClick={onCancel}>
          取消
        </Button>
      </Box>
    </TableCell>
  </TableRow>
);

export default RequirementReviewWorkbench;
