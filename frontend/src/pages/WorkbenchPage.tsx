import { useMemo, useState } from 'react';
import {
  Alert,
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Button,
  Chip,
  Divider,
  Drawer,
  Grid,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import ExpandMoreRounded from '@mui/icons-material/ExpandMoreRounded';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import PageViewer from '../components/PageViewer';
import ChecklistPanel from './ChecklistPanel';
import FillPanel from './FillPanel';
import { api, type AnalysisRun, type Decision, type DocumentItem, type Evidence, type PageItem } from '../lib/api';
import { categoryLabels, stageLabels } from '../lib/labels';
import { EmptyState, Guidance, NextButton, PageHeader, WorkflowNav } from '../components/Workspace';

const decisionLabel = {
  met: '符合',
  not_met: '不符合',
  needs_review: '待确认',
  not_applicable: '不适用',
} as const;

const decisionColor = {
  met: 'success',
  not_met: 'error',
  needs_review: 'warning',
  not_applicable: 'default',
} as const;

const analysisLabel: Record<string, string> = {
  draft: '等待分析',
  running: '正在分析',
  needs_review: '分析完成，待人工复核',
  completed: '已完成',
  failed: '分析未完成',
  stale: '资料已更新，需重新分析',
};

export default function WorkbenchPage() {
  const { runId = '' } = useParams();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const tabNames = ['requirements', 'fill', 'checklist'];
  const tab = Math.max(0, tabNames.indexOf(searchParams.get('tab') ?? 'requirements'));
  const [selectedId, setSelectedId] = useState('');
  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewStatus, setReviewStatus] = useState('met');
  const [reviewReason, setReviewReason] = useState('');
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');

  const run = useQuery({
    queryKey: ['run', runId],
    queryFn: async () => (await api.get<AnalysisRun>(`/analysis-runs/${runId}`)).data,
    refetchInterval: 2500,
  });
  const decisions = useQuery({
    queryKey: ['decisions', runId],
    queryFn: async () => (await api.get<Decision[]>(`/analysis-runs/${runId}/decisions`)).data,
    refetchInterval: 3000,
  });
  const documents = useQuery({
    queryKey: ['documents', run.data?.project_id],
    enabled: Boolean(run.data),
    queryFn: async () => (await api.get<DocumentItem[]>(`/projects/${run.data!.project_id}/documents`)).data,
  });
  const evidence = useQuery({
    queryKey: ['evidence', run.data?.project_id],
    enabled: Boolean(run.data),
    queryFn: async () => (await api.get<Evidence[]>(`/projects/${run.data!.project_id}/evidence`)).data,
  });
  const pages = useQuery({
    queryKey: ['run-pages', runId],
    queryFn: async () => {
      const docs = documents.data?.filter((doc) => ['tender', 'addendum', 'qa'].includes(doc.role)) ?? [];
      return (await Promise.all(docs.map(async (doc) => (await api.get<PageItem[]>(`/documents/${doc.id}/pages`)).data))).flat();
    },
    enabled: Boolean(documents.data),
  });
  const filtered = decisions.data?.filter((item) =>
    (filter === 'all' || item.status === filter)
    && `${item.requirement?.title} ${item.requirement?.statement}`.toLowerCase().includes(search.toLowerCase()),
  ) ?? [];
  const selected = filtered.find((item) => item.id === selectedId) ?? filtered[0];
  const selectedPage =
    pages.data?.find((page) => page.id === selected?.requirement?.source_span?.page_id) ??
    pages.data?.[0];
  const review = useMutation({
    mutationFn: async () =>
      (
        await api.post(`/decisions/${selected?.id}/reviews`, {
          new_status: reviewStatus,
          reason: reviewReason,
        })
      ).data,
    onSuccess: async () => {
      setReviewOpen(false);
      setReviewReason('');
      await queryClient.invalidateQueries({ queryKey: ['decisions', runId] });
      await queryClient.invalidateQueries({ queryKey: ['run', runId] });
      await queryClient.invalidateQueries({ queryKey: ['checklist', runId] });
    },
    onError: (err) => setError(apiError(err, '提交复核失败')),
  });
  const counts = useMemo(
    () =>
      (decisions.data ?? []).reduce(
        (acc, decision) => {
          acc[decision.status] = (acc[decision.status] ?? 0) + 1;
          return acc;
        },
        {} as Record<string, number>,
      ),
    [decisions.data],
  );

  if (run.isLoading) return <EmptyState loading title="正在加载分析结果" />;
  if (run.isError) return <Alert severity="error">分析记录不存在或暂时无法加载。<Button component={Link} to="/">返回项目列表</Button></Alert>;

  return (
    <Stack spacing={3}>
      <PageHeader title={['要求核对', '填写建议', '检查导出'][tab]} description={`${analysisLabel[run.data?.status ?? 'draft']} · 处理进度 ${run.data?.progress ?? 0}%`} actions={<Button variant="outlined" component={Link} to={`/projects/${run.data?.project_id}`}>返回项目资料</Button>} />
      {run.data && <WorkflowNav projectId={run.data.project_id} runId={runId} active={tab + 1} />}
      {tab === 0 && <Guidance step="第 2 步 · 核对要求" title="先选一条要求，对照原文和证据，再保存人工结论" action={<Button component={Link} to={`/projects/${run.data?.project_id}/evidence`} variant="outlined">管理证据资料</Button>}>左侧选择要求，右侧查看原文引用。待确认项需要补充证据或人工复核；“符合”与“已完成分析”是不同状态。</Guidance>}
      {error && <Alert severity="error">{error}</Alert>}
      {run.data?.status === 'failed' && <Alert severity="error">{run.data.error}</Alert>}
      {run.data?.status === 'stale' && <Alert severity="warning">项目资料已更新，当前显示历史分析结果。请回项目页重新分析后再核对结论。</Alert>}
      {run.data?.coverage_notes?.length ? (
        <Accordion variant="outlined" disableGutters>
          <AccordionSummary expandIcon={<ExpandMoreRounded />}><Typography variant="body2" color="warning.main">有 {run.data.coverage_notes.length} 项原文识别或定位需核验，点击查看原因</Typography></AccordionSummary>
          <AccordionDetails><Stack spacing={1}>{run.data.coverage_notes.map((note, index) => <Typography key={index} variant="body2">{index + 1}. {note}</Typography>)}<Button sx={{ alignSelf: 'flex-start' }} onClick={() => setSearchParams({ tab: 'checklist' })}>到检查清单处理</Button></Stack></AccordionDetails>
        </Accordion>
      ) : null}

      {tab === 0 && (
        <Stack spacing={2}>
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: { xs: 1, sm: 2 } }}>{Object.entries(decisionLabel).map(([status, label]) => <Paper key={status} variant="outlined" component="button" onClick={() => setFilter(filter === status ? 'all' : status)} aria-pressed={filter === status} sx={{ p: { xs: 1.5, sm: 2 }, textAlign: 'left', cursor: 'pointer', font: 'inherit', borderColor: filter === status ? 'primary.main' : 'divider' }}><Typography variant="caption" color="text.secondary">{label}</Typography><Typography variant="h4" sx={{ mt: 0.5 }}>{counts[status] ?? 0}<Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>条</Typography></Typography></Paper>)}</Box>
        <Box><Grid container spacing={2.5}>
          <Grid item xs={12} md={4}>
            <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
              <Box sx={{ p: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
                <Typography variant="h6" sx={{ mb: 1.5 }}>要求列表 · {filtered.length} 条</Typography>
                <TextField label="搜索要求" value={search} onChange={(event) => setSearch(event.target.value)} />
                <TextField select label="核验状态" value={filter} onChange={(event) => setFilter(event.target.value)} sx={{ mt: 1.5 }}><MenuItem value="all">全部状态</MenuItem>{Object.entries(decisionLabel).map(([key, label]) => <MenuItem key={key} value={key}>{label}</MenuItem>)}</TextField>
              </Box>
              <Box className="custom-scrollbar" sx={{ maxHeight: 'calc(100vh - 280px)', overflow: 'auto' }}>
                {!filtered.length && <EmptyState title={decisions.isLoading || run.data?.status === 'running' ? '正在整理要求' : '没有可显示的要求'} description={search || filter !== 'all' ? '请调整搜索词或切换到全部状态。' : '请查看本次分析状态，确认招标文件已经解析并完成分析。'} />}
                {filtered.map((decision) => (
                  <Box
                    key={decision.id}
                    component="button"
                    onClick={() => setSelectedId(decision.id)}
                    aria-pressed={selected?.id === decision.id}
                    sx={{
                      display: 'block', width: '100%', textAlign: 'left', font: 'inherit',
                      border: 0,
                      p: 2,
                      cursor: 'pointer',
                      borderBottom: '1px solid', borderColor: 'divider',
                      bgcolor:
                        selected?.id === decision.id ? 'rgba(183,67,43,.08)' : 'transparent',
                      '&:hover': { bgcolor: 'rgba(183,67,43,.04)' },
                    }}
                  >
                    <Stack direction="row" justifyContent="space-between" gap={1}>
                      <Typography fontWeight={600}>
                        {decision.requirement?.title ?? '未命名要求'}
                      </Typography>
                      <Chip
                        size="small"
                        color={decisionColor[decision.status]}
                        label={decisionLabel[decision.status]}
                      />
                    </Stack>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                      {categoryLabels[decision.requirement?.category ?? ''] ?? '其他要求'} · {stageLabels[decision.requirement?.evaluation_stage ?? ''] ?? decision.requirement?.evaluation_stage}
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 1 }}>
                      {decision.summary}
                    </Typography>
                  </Box>
                ))}
              </Box>
            </Paper>
          </Grid>
          <Grid item xs={12} md={8}>
            {selectedPage ? (
              <Stack spacing={2}>
                {selected && (
                  <RequirementPanel decision={selected} sourceName={documents.data?.find((doc) => doc.id === selected.requirement?.source_span?.document_id)?.filename} pageNumber={selectedPage.page_index + 1} evidence={evidence.data?.filter((item) => selected.evidence_ids.includes(item.id)) ?? []} onReview={() => { setReviewStatus(selected.status); setReviewReason(''); setReviewOpen(true); }} />
                )}
                <Box sx={{ maxHeight: 620, overflow: 'auto', borderRadius: 1 }}><PageViewer page={selectedPage} highlight={selected?.requirement?.source_span} /></Box>
              </Stack>
            ) : (
              <Paper variant="outlined" sx={{ p: 6, textAlign: 'center' }}>
                <Typography color="text.secondary">暂无可显示的标书页面。</Typography>
              </Paper>
            )}
          </Grid>
        </Grid></Box>
        </Stack>
      )}

      {tab === 1 && run.data && <FillPanel runId={runId} projectId={run.data.project_id} />}
      {tab === 2 && <ChecklistPanel runId={runId} />}
      {tab < 2 && <Stack direction="row" justifyContent="flex-end"><NextButton to={`/runs/${runId}?tab=${tab === 0 ? 'fill' : 'checklist'}`}>下一步：{tab === 0 ? '确认填写内容' : '检查并导出'}</NextButton></Stack>}

      <Drawer anchor="right" open={reviewOpen} onClose={() => setReviewOpen(false)}>
        <Box sx={{ width: { xs: '100vw', sm: 420 }, p: 3 }}>
          <Typography variant="h5" sx={{ mb: 2 }}>
            人工复核
          </Typography>
          <Stack spacing={2}>
            <Typography color="text.secondary">{selected?.requirement?.title}。请根据原文和证据选择结论，并填写复核理由。</Typography>
            <TextField
              select
              label="结论"
              value={reviewStatus}
              onChange={(event) => setReviewStatus(event.target.value)}
            >
              <MenuItem value="met">符合</MenuItem>
              <MenuItem value="not_met">不符合</MenuItem>
              <MenuItem value="needs_review">仍需确认</MenuItem>
              <MenuItem value="not_applicable">不适用</MenuItem>
            </TextField>
            <TextField
              label="复核理由"
              multiline
              minRows={5}
              value={reviewReason}
              onChange={(event) => setReviewReason(event.target.value)}
            />
            <Button
              variant="contained"
              disabled={!reviewReason.trim() || review.isPending}
              onClick={() => review.mutate()}
            >
              保存复核记录
            </Button>
          </Stack>
        </Box>
      </Drawer>
    </Stack>
  );
}

function RequirementPanel({
  decision,
  onReview,
  sourceName,
  pageNumber,
  evidence,
}: {
  decision: Decision;
  onReview: () => void;
  sourceName?: string;
  pageNumber: number;
  evidence: Evidence[];
}) {
  const requirement = decision.requirement;
  if (!requirement) return null;
  return (
    <Paper variant="outlined" sx={{ p: 2.5 }}>
      <Stack spacing={2}>
        <Stack direction="row" justifyContent="space-between" gap={2} alignItems="center">
          <Typography variant="h5">{requirement.title}</Typography>
          <Button variant="contained" onClick={onReview}>
            {decision.reviews.length ? '修改复核结论' : '人工复核'}
          </Button>
        </Stack>
        <Typography>{requirement.statement}</Typography>
        <Divider />
        <Typography variant="subtitle2">原文引用</Typography>
        <Typography variant="caption" color="text.secondary">
          {sourceName ?? '来源文件'} · 第 {pageNumber} 页
        </Typography>
        <Typography
          sx={{
            p: 2,
            bgcolor: '#F8F9FB',
            borderLeft: '3px solid #B7432B',
          }}
        >
          {requirement.source_span?.quote ?? '未找到原文'}
        </Typography>
        <Typography variant="subtitle2">判定说明</Typography>
        <Typography color="text.secondary">{decision.summary}</Typography>
        <Typography variant="subtitle2">匹配证据</Typography>
        <Typography variant="body2" color="text.secondary">{evidence.length ? evidence.map((item) => `${item.title}${item.holder ? `（${item.holder}）` : ''}`).join('；') : '尚未找到可直接支持该要求的证据，请到「证据资料」登记或人工核验。'}</Typography>
        {decision.condition_results?.length > 0 && (
          <Typography variant="caption" color="text.secondary">
            已记录 {decision.condition_results.length} 个条件检查结果
          </Typography>
        )}
      </Stack>
    </Paper>
  );
}

function apiError(error: unknown, fallback: string) {
  if (typeof error === 'object' && error && 'response' in error) {
    const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (detail) return detail;
  }
  return error instanceof Error ? error.message : fallback;
}
