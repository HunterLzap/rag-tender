import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  Drawer,
  Grid,
  MenuItem,
  Paper,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import PageViewer from '../components/PageViewer';
import ChecklistPanel from './ChecklistPanel';
import FillPanel from './FillPanel';
import { api, type AnalysisRun, type Decision, type PageItem } from '../lib/api';

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

export default function WorkbenchPage() {
  const { runId = '' } = useParams();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState(0);
  const [selectedId, setSelectedId] = useState('');
  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewStatus, setReviewStatus] = useState('met');
  const [reviewReason, setReviewReason] = useState('');
  const [error, setError] = useState('');

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
  const pages = useQuery({
    queryKey: ['run-pages', runId],
    queryFn: async () => {
      if (!run.data) return [];
      const docs = (
        await api.get<Array<{ id: string; role: string }>>(
          `/projects/${run.data.project_id}/documents`,
        )
      ).data;
      const tender = docs.find((doc) => doc.role === 'tender');
      if (!tender) return [];
      return (await api.get<PageItem[]>(`/documents/${tender.id}/pages`)).data;
    },
    enabled: Boolean(run.data),
  });
  const selected = decisions.data?.find((item) => item.id === selectedId) ?? decisions.data?.[0];
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

  return (
    <Stack spacing={3}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'end',
          gap: 2,
          flexWrap: 'wrap',
        }}
      >
        <Box>
          <Typography variant="overline" color="secondary.main">
            RESPONSE WORKBENCH / {run.data?.prompt_version ?? 'V2'}
          </Typography>
          <Typography variant="h3">投标响应工作台</Typography>
          <Typography color="text.secondary" sx={{ mt: 1 }}>
            {run.data?.stage} · {run.data?.progress ?? 0}%
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} flexWrap="wrap">
          {Object.entries(counts).map(([status, count]) => (
            <Chip
              key={status}
              color={decisionColor[status as keyof typeof decisionColor] ?? 'default'}
              label={`${decisionLabel[status as keyof typeof decisionLabel] ?? status} ${count}`}
            />
          ))}
        </Stack>
      </Box>
      {error && <Alert severity="error">{error}</Alert>}
      {run.data?.status === 'failed' && <Alert severity="error">{run.data.error}</Alert>}
      {run.data?.coverage_notes?.length ? (
        <Alert severity="warning">
          有 {run.data.coverage_notes.length} 条提取或定位警告，需要人工检查。
        </Alert>
      ) : null}

      <Paper variant="outlined" sx={{ bgcolor: 'rgba(255,253,247,.88)' }}>
        <Tabs value={tab} onChange={(_, value) => setTab(value)} variant="scrollable">
          <Tab label="要求核对" />
          <Tab label="填写建议" />
          <Tab label="交付检查" />
        </Tabs>
      </Paper>

      {tab === 0 && (
        <Grid container spacing={3}>
          <Grid item xs={12} lg={4}>
            <Paper variant="outlined" sx={{ bgcolor: 'rgba(255,253,247,.88)', overflow: 'hidden' }}>
              <Box sx={{ p: 2, borderBottom: '1px solid #ded5c5' }}>
                <Typography variant="h6">要求与结论</Typography>
              </Box>
              <Box className="custom-scrollbar" sx={{ maxHeight: 'calc(100vh - 280px)', overflow: 'auto' }}>
                {decisions.data?.length === 0 && (
                  <Box sx={{ p: 3 }}>
                    <Typography color="text.secondary">
                      分析仍在进行，或当前文档没有提取到要求。
                    </Typography>
                  </Box>
                )}
                {decisions.data?.map((decision) => (
                  <Box
                    key={decision.id}
                    onClick={() => setSelectedId(decision.id)}
                    sx={{
                      p: 2,
                      cursor: 'pointer',
                      borderBottom: '1px solid #eee7db',
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
                      {decision.requirement?.category} · {decision.requirement?.evaluation_stage}
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 1 }}>
                      {decision.summary}
                    </Typography>
                  </Box>
                ))}
              </Box>
            </Paper>
          </Grid>
          <Grid item xs={12} lg={8}>
            {selectedPage ? (
              <Stack spacing={2}>
                <PageViewer page={selectedPage} highlight={selected?.requirement?.source_span} />
                {selected && (
                  <RequirementPanel decision={selected} onReview={() => setReviewOpen(true)} />
                )}
              </Stack>
            ) : (
              <Paper variant="outlined" sx={{ p: 6, textAlign: 'center' }}>
                <Typography color="text.secondary">暂无可显示的标书页面。</Typography>
              </Paper>
            )}
          </Grid>
        </Grid>
      )}

      {tab === 1 && run.data && <FillPanel runId={runId} projectId={run.data.project_id} />}
      {tab === 2 && <ChecklistPanel runId={runId} />}

      <Drawer anchor="right" open={reviewOpen} onClose={() => setReviewOpen(false)}>
        <Box sx={{ width: 380, p: 3 }}>
          <Typography variant="h5" sx={{ mb: 2 }}>
            人工复核
          </Typography>
          <Stack spacing={2}>
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
}: {
  decision: Decision;
  onReview: () => void;
}) {
  const requirement = decision.requirement;
  if (!requirement) return null;
  return (
    <Paper variant="outlined" sx={{ p: 3, bgcolor: 'rgba(255,253,247,.88)' }}>
      <Stack spacing={2}>
        <Stack direction="row" justifyContent="space-between" gap={2}>
          <Typography variant="h5">{requirement.title}</Typography>
          <Button variant="outlined" onClick={onReview}>
            人工复核
          </Button>
        </Stack>
        <Typography>{requirement.statement}</Typography>
        <Divider />
        <Typography variant="subtitle2">原文引用</Typography>
        <Typography variant="caption" color="text.secondary">
          {requirement.source_span?.document_filename ?? '来源文件'}
          {requirement.source_span?.page_index != null
            ? ` · 第 ${requirement.source_span.page_index + 1} 页`
            : ''}
        </Typography>
        <Typography
          sx={{
            p: 2,
            bgcolor: '#f0ece2',
            borderLeft: '3px solid #B7432B',
            fontFamily: '"Songti SC", serif',
          }}
        >
          {requirement.source_span?.quote ?? '未找到原文'}
        </Typography>
        <Typography variant="subtitle2">判定说明</Typography>
        <Typography color="text.secondary">{decision.summary}</Typography>
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
