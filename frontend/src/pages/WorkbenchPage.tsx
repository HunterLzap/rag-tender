import { useMemo, useState } from 'react';
import {
  Alert,
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Button,
  Chip,
  Checkbox,
  Divider,
  Drawer,
  Grid,
  FormControlLabel,
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
import RequirementEditor from '../components/RequirementEditor';
import ChecklistPanel from './ChecklistPanel';
import FillPanel from './FillPanel';
import { api, apiError, type AnalysisRun, type Decision, type DocumentItem, type Evidence, type PageItem, type Requirement } from '../lib/api';
import { formatDate } from '../lib/format';
import { categoryLabels, stageLabels } from '../lib/labels';
import { EmptyState, Notice, PageHeader } from '../components/Workspace';

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
  const selectedId = searchParams.get('requirement') ?? '';
  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewStatus, setReviewStatus] = useState('met');
  const [reviewReason, setReviewReason] = useState('');
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [editingRequirement, setEditingRequirement] = useState<Requirement | null | undefined>(undefined);
  const [reviewEvidenceIds, setReviewEvidenceIds] = useState<string[]>([]);
  const [message, setMessage] = useState('');

  const run = useQuery({
    queryKey: ['run', runId],
    queryFn: async () => (await api.get<AnalysisRun>(`/analysis-runs/${runId}`)).data,
    refetchInterval: (query) => ['draft', 'running'].includes(query.state.data?.status ?? '') ? 2500 : false,
  });
  const decisions = useQuery({
    queryKey: ['decisions', runId],
    queryFn: async () => (await api.get<Decision[]>(`/analysis-runs/${runId}/decisions`)).data,
    refetchInterval: ['draft', 'running'].includes(run.data?.status ?? '') ? 3000 : false,
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
  const selected = filtered.find((item) => item.id === selectedId || item.requirement_id === selectedId) ?? filtered[0];
  const selectedPage =
    pages.data?.find((page) => page.id === selected?.requirement?.source_span?.page_id) ??
    pages.data?.[0];
  const review = useMutation({
    mutationFn: async () =>
      (
        await api.post(`/decisions/${selected?.id}/reviews`, {
          new_status: reviewStatus,
          reason: reviewReason,
          evidence_ids: reviewEvidenceIds,
        })
      ).data,
    onSuccess: async () => {
      setReviewOpen(false);
      setReviewReason('');
      setMessage('复核结论与所选证据已保存');
      await queryClient.invalidateQueries({ queryKey: ['decisions', runId] });
      await queryClient.invalidateQueries({ queryKey: ['run', runId] });
      await queryClient.invalidateQueries({ queryKey: ['checklist', runId] });
    },
    onError: (err) => setError(apiError(err, '提交复核失败')),
  });
  const refreshResults = async () => {
    await Promise.all(['decisions', 'run', 'checklist'].map((key) => queryClient.invalidateQueries({ queryKey: [key, runId] })));
    await queryClient.invalidateQueries({ queryKey: ['runs', run.data?.project_id] });
  };
  const recheck = useMutation({
    mutationFn: async () => api.post(`/analysis-runs/${runId}/recheck`),
    onSuccess: async () => { setMessage('已用当前资料重新执行规则核对，请继续人工复核；本次未调用模型'); await refreshResults(); },
    onError: (err) => setError(apiError(err, '规则核对失败')),
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
    <Stack spacing={2}>
      <PageHeader title={['要求核对', '填写建议', '检查导出'][tab]} actions={<>
        <Button color="inherit" component={Link} to={`/projects/${run.data?.project_id}`}>项目资料</Button>
        {tab === 0 && <><Button color="inherit" component={Link} to={`/projects/${run.data?.project_id}/evidence`}>证据资料</Button><Button variant="contained" disabled={['draft', 'running'].includes(run.data?.status ?? '')} onClick={() => setEditingRequirement(null)}>补充要求</Button></>}
      </>} />
      <Notice message={message} onClose={() => setMessage('')} />
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      {['draft', 'running'].includes(run.data?.status ?? '') && <Alert severity="info">{analysisLabel[run.data?.status ?? 'draft']} · {run.data?.progress ?? 0}%</Alert>}
      {run.data?.status === 'failed' && <Alert severity="error">{run.data.error}</Alert>}
      {run.data?.status === 'stale' && <Alert severity="warning" action={<Button color="inherit" disabled={recheck.isPending} onClick={() => recheck.mutate()}>重新核对</Button>}>资料已更新，请重新核对；招标原文有变动时需新建工作台。</Alert>}
      {tab === 0 && run.data?.coverage_notes?.length ? (
        <Accordion variant="outlined" disableGutters>
          <AccordionSummary expandIcon={<ExpandMoreRounded />}><Typography variant="body2" color="warning.main">{run.data.coverage_notes.length} 项范围待核验</Typography></AccordionSummary>
          <AccordionDetails><Stack spacing={1}>{run.data.coverage_notes.map((note, index) => <Typography key={index} variant="body2">{index + 1}. {note}</Typography>)}<Button sx={{ alignSelf: 'flex-start' }} onClick={() => setSearchParams({ tab: 'checklist' })}>到检查清单处理</Button></Stack></AccordionDetails>
        </Accordion>
      ) : null}

      {tab === 0 && (
        <Stack spacing={2}>
        <Box><Grid container spacing={2.5}>
          <Grid item xs={12} md={4}>
            <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
              <Box sx={{ p: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
                <TextField label="搜索要求" value={search} onChange={(event) => setSearch(event.target.value)} />
                <TextField select label="核验状态" value={filter} onChange={(event) => setFilter(event.target.value)} sx={{ mt: 1.5 }}><MenuItem value="all">全部 {decisions.data?.length ?? 0}</MenuItem>{Object.entries(decisionLabel).map(([key, label]) => <MenuItem key={key} value={key}>{label} {counts[key] ?? 0}</MenuItem>)}</TextField>
              </Box>
              <Box className="custom-scrollbar" sx={{ maxHeight: { xs: 240, md: 'calc(100vh - 280px)' }, overflow: 'auto' }}>
                {decisions.isError ? <Alert severity="error">要求加载失败，请刷新页面重试。</Alert> : !filtered.length && <EmptyState title={decisions.isLoading || run.data?.status === 'running' ? '正在整理要求' : '没有可显示的要求'} description={search || filter !== 'all' ? '请调整搜索词或切换到全部状态。' : '可手工补充有原文依据的要求。'} action={run.data?.status !== 'running' && <Button onClick={() => setEditingRequirement(null)}>补充第一条要求</Button>} />}
                {filtered.map((decision) => (
                  <Box
                    key={decision.id}
                    component="button"
                    onClick={() => setSearchParams({ tab: 'requirements', requirement: decision.id })}
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
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                      {decision.summary}
                    </Typography>
                  </Box>
                ))}
              </Box>
            </Paper>
          </Grid>
          <Grid item xs={12} md={8} sx={{ minWidth: 0 }}>
            {selectedPage ? (
              <Stack spacing={2}>
                {selected && (
                  <RequirementPanel decision={selected} sourceName={documents.data?.find((doc) => doc.id === selected.requirement?.source_span?.document_id)?.filename} pageNumber={selectedPage.page_index + 1} evidence={evidence.data?.filter((item) => selected.evidence_ids.includes(item.id)) ?? []} onEdit={() => setEditingRequirement(selected.requirement)} onReview={() => { setReviewStatus(selected.status); setReviewReason(''); setReviewEvidenceIds(selected.evidence_ids); setReviewOpen(true); }} />
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
      <Drawer anchor="right" open={reviewOpen} onClose={() => setReviewOpen(false)}>
        <Box sx={{ width: { xs: '100vw', sm: 420 }, p: 3 }}>
          <Typography variant="h5" sx={{ mb: 2 }}>
            人工复核
          </Typography>
          <Stack spacing={2}>
            {error && <Alert severity="error">{error}</Alert>}
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
            <Typography variant="subtitle2">本次复核依据的证据</Typography>
            <Box sx={{ maxHeight: 190, overflow: 'auto', border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 1 }}>
              {evidence.data?.length ? evidence.data.map((item) => <FormControlLabel key={item.id} sx={{ display: 'flex', m: 0 }} label={`${item.title}${item.review_status === 'verified' ? ' · 已核实' : ' · 待核实'}`} control={<Checkbox checked={reviewEvidenceIds.includes(item.id)} onChange={(_, checked) => setReviewEvidenceIds((current) => checked ? [...current, item.id] : current.filter((id) => id !== item.id))} />} />) : <Typography variant="body2" color="text.secondary">暂无已登记证据，可先到证据资料页补充。</Typography>}
            </Box>
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
      {editingRequirement !== undefined && run.data && <RequirementEditor key={editingRequirement?.id ?? 'new'} runId={runId} projectId={run.data.project_id} requirement={editingRequirement} onClose={() => setEditingRequirement(undefined)} onSaved={async () => { setMessage('要求已保存，请重新核对结论'); await refreshResults(); }} />}
    </Stack>
  );
}

function RequirementPanel({
  decision,
  onReview,
  onEdit,
  sourceName,
  pageNumber,
  evidence,
}: {
  decision: Decision;
  onReview: () => void;
  onEdit: () => void;
  sourceName?: string;
  pageNumber: number;
  evidence: Evidence[];
}) {
  const requirement = decision.requirement;
  if (!requirement) return null;
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack spacing={2}>
        <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={2} alignItems={{ xs: 'flex-start', sm: 'center' }}>
          <Typography variant="h6">{requirement.title}</Typography>
          <Stack direction="row" gap={1} flexShrink={0}><Button variant="outlined" onClick={onEdit}>修改要求</Button><Button variant="contained" onClick={onReview}>
            {decision.reviews.length ? '修改复核结论' : '人工复核'}
          </Button></Stack>
        </Stack>
        <Typography>{requirement.statement}</Typography>
        <Box sx={{ p: 1.5, bgcolor: '#F8F9FB', borderLeft: '2px solid #B7432B' }}>
          <Typography variant="caption" color="text.secondary">{sourceName ?? '来源文件'} · 第 {pageNumber} 页</Typography>
          <Typography variant="body2" sx={{ mt: 0.5 }}>{requirement.source_span?.quote ?? '未找到原文'}</Typography>
        </Box>
        <Typography variant="body2" color="text.secondary">{decision.summary}</Typography>
        {decision.stale && <Alert severity="warning">该结论需按最新资料重新核对。</Alert>}
        <Typography variant="caption" color="text.secondary">证据：{evidence.length ? evidence.map((item) => `${item.title}${item.holder ? `（${item.holder}）` : ''}`).join('；') : '待补充'}</Typography>
        {(decision.rule_trace.length > 0 || decision.reviews.length > 0) && <Accordion disableGutters elevation={0} sx={{ '&:before': { display: 'none' } }}>
          <AccordionSummary expandIcon={<ExpandMoreRounded />} sx={{ px: 0, minHeight: 36 }}><Typography variant="body2" color="text.secondary">核对依据与复核记录</Typography></AccordionSummary>
          <AccordionDetails sx={{ px: 0, pb: 0 }}><Stack spacing={1.5}>
            {decision.rule_trace.map((trace, index) => <Box key={index}><Typography variant="body2">{String(trace.reason ?? '')}</Typography>{trace.expected != null && <Typography variant="caption" color="text.secondary">要求：{String(trace.expected)}；实际：{trace.actual == null ? '缺少可比较字段' : String(trace.actual)}</Typography>}</Box>)}
            {decision.rule_trace.length > 0 && decision.reviews.length > 0 && <Divider />}
            {[...decision.reviews].sort((a, b) => b.created_at.localeCompare(a.created_at)).map((record) => <Box key={record.id}><Typography variant="caption" color="text.secondary">{formatDate(record.created_at)} · {decisionLabel[record.new_status as keyof typeof decisionLabel]}{record.reviewer ? ` · ${record.reviewer}` : ''}</Typography><Typography variant="body2">{record.reason}</Typography></Box>)}
          </Stack></AccordionDetails>
        </Accordion>}
      </Stack>
    </Paper>
  );
}
