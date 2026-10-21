import { useEffect, useMemo, useState } from 'react';
import { isAxiosError } from 'axios';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Grid,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
  LinearProgress,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { EmptyState, Guidance } from '../components/Workspace';
import {
  api,
  type AnnotationAsset,
  type FillPlan,
  type FillSuggestion,
  type FillTarget,
  type PageItem,
} from '../lib/api';

interface Props {
  runId: string;
  projectId: string;
}

const statusLabel: Record<string, string> = {
  proposed: '待确认',
  accepted: '已确认',
  edited: '已修改',
  missing_evidence: '待补充',
  rejected: '已拒绝',
};

export default function FillPanel({ runId, projectId }: Props) {
  const queryClient = useQueryClient();
  const [selectedTargetId, setSelectedTargetId] = useState('');
  const [templateChoiceId, setTemplateChoiceId] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [draftValues, setDraftValues] = useState<Record<string, string>>({});

  const documents = useQuery({
    queryKey: ['fill-documents', projectId],
    queryFn: async () =>
      (
        await api.get<Array<{ id: string; role: string; filename: string; current_revision_id: string | null }>>(
          `/projects/${projectId}/documents`,
        )
      ).data,
  });
  const templates = documents.data?.filter(
    (document) => document.role === 'template' && document.current_revision_id,
  ) ?? [];
  const templateId =
    templates.find((document) => document.id === templateChoiceId)?.id ?? templates[0]?.id;
  const templatePages = useQuery({
    queryKey: ['template-pages', templateId],
    enabled: Boolean(templateId),
    queryFn: async () => (await api.get<PageItem[]>(`/documents/${templateId}/pages`)).data,
  });
  const plan = useQuery({
    queryKey: ['fill-plan', runId, templateId],
    enabled: Boolean(templateId),
    queryFn: async () => {
      try {
        return (
          await api.get<FillPlan>(`/analysis-runs/${runId}/fill-plan`, {
            params: { template_document_id: templateId },
          })
        ).data;
      } catch (err) {
        if (!isAxiosError(err) || err.response?.status !== 404) throw err;
      }
      const response = await api.post<FillPlan>(`/analysis-runs/${runId}/fill-plan`, {
        template_document_id: templateId,
      });
      return response.data;
    },
  });

  const selectedPlan = plan.data;
  const selectedTarget =
    selectedPlan?.targets.find((target) => target.id === selectedTargetId) ??
    selectedPlan?.targets.find((target) => !['accepted', 'edited', 'rejected'].includes(target.suggestions[0]?.status)) ??
    selectedPlan?.targets[0];
  const selectedSuggestion = selectedTarget?.suggestions[0];
  const selectedAsset = selectedPlan?.assets.find(
    (asset) => asset.page_id === selectedTarget?.page_id,
  );

  useEffect(() => {
    if (!selectedTarget || !selectedSuggestion) return;
    setDraftValues((current) => ({
      ...current,
      [selectedSuggestion.id]: current[selectedSuggestion.id] ?? selectedSuggestion.value ?? '',
    }));
  }, [selectedTarget, selectedSuggestion]);

  const save = useMutation({
    onMutate: () => { setError(''); setMessage(''); },
    mutationFn: async ({
      suggestion,
      value,
      status,
    }: {
      suggestion: FillSuggestion;
      value: string;
      status: string;
    }) =>
      (
        await api.patch<FillSuggestion>(`/fill-suggestions/${suggestion.id}`, {
          value,
          status,
          reviewed_by: '人工复核',
        })
      ).data,
    onSuccess: async () => {
      setMessage('本项已保存，标注图已同步更新');
      await queryClient.invalidateQueries({ queryKey: ['fill-plan', runId, templateId] });
      await queryClient.invalidateQueries({ queryKey: ['checklist', runId] });
      await queryClient.invalidateQueries({ queryKey: ['run', runId] });
      const next = selectedPlan?.targets.find((target) => target.id !== selectedTarget?.id && !['accepted', 'edited', 'rejected'].includes(target.suggestions[0]?.status));
      if (next) setSelectedTargetId(next.id);
    },
    onError: (err) => setError(apiError(err, '保存填写建议失败')),
  });

  const rebuild = useMutation({
    onMutate: () => { setError(''); setMessage(''); },
    mutationFn: async () =>
      (
        await api.post<FillPlan>(`/analysis-runs/${runId}/fill-plan`, {
          template_document_id: templateId,
        })
      ).data,
    onSuccess: (result) => {
      setMessage('填写计划已重建，已审阅的内容会保留');
      queryClient.setQueryData(['fill-plan', runId, templateId], result);
      setSelectedTargetId('');
    },
    onError: (err) => setError(apiError(err, '重建填写计划失败')),
  });

  const groupedTargets = useMemo(() => {
    const groups = new Map<string, FillTarget[]>();
    for (const target of selectedPlan?.targets ?? []) {
      groups.set(target.page_id, [...(groups.get(target.page_id) ?? []), target]);
    }
    return groups;
  }, [selectedPlan?.targets]);
  const reviewed = selectedPlan?.targets.filter((target) => ['accepted', 'edited', 'rejected'].includes(target.suggestions[0]?.status)).length ?? 0;
  const total = selectedPlan?.targets.length ?? 0;
  const nextPending = selectedPlan?.targets.find((target) => target.id !== selectedTarget?.id && !['accepted', 'edited', 'rejected'].includes(target.suggestions[0]?.status));

  if (documents.isLoading) return <EmptyState title="正在加载投标模板" loading />;
  if (documents.isError) return <Alert severity="error">模板文件加载失败，请刷新页面重试。</Alert>;
  if (!templates.length) {
    return (
      <Paper variant="outlined"><EmptyState title="先上传需要填写的投标模板" description="回到项目资料，将文件用途设为「投标模板」后上传。需要原页标注图时，优先上传 PDF。" action={<Button component={Link} to={`/projects/${projectId}?upload=template#files`} variant="contained">前往上传投标模板</Button>} /></Paper>
    );
  }

  if (plan.isLoading) {
    return (
      <Paper variant="outlined" sx={{ p: 6, textAlign: 'center' }}>
        <CircularProgress size={28} />
        <Typography color="text.secondary" sx={{ mt: 2 }}>
          正在识别模板中的填写位置和标注图...
        </Typography>
      </Paper>
    );
  }

  return (
    <Stack spacing={2}>
      <Guidance step="第 3 步" title="逐项确认填写内容">
        左侧选位置 → 右侧填内容 → 保存后查看标注图，并继续下一项。原文件不会被自动改写。
      </Guidance>
      {error && <Alert severity="error">{error}</Alert>}
      {plan.error && <Alert severity="error">{apiError(plan.error, '加载填写计划失败')}</Alert>}
      {message && <Alert severity="success">{message}</Alert>}
      <Paper variant="outlined" sx={{ p: 2.5 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" gap={2} flexWrap="wrap">
          <Box>
            <Typography variant="h6">模板填写进度</Typography>
            <Typography variant="body2" color="text.secondary">
              已处理 {reviewed} / {total} 项 · {selectedPlan?.assets.length ?? 0} 张原页标注图
            </Typography>
          </Box>
          <TextField
            select
            size="small"
            label="投标模板"
            value={templateId ?? ''}
            onChange={(event) => {
              setTemplateChoiceId(event.target.value);
              setSelectedTargetId('');
            }}
            sx={{ minWidth: 200, maxWidth: 340 }}
          >
            {templates.map((document) => (
              <MenuItem key={document.id} value={document.id}>{document.filename}</MenuItem>
            ))}
          </TextField>
          <Button variant="outlined" disabled={rebuild.isPending} onClick={() => rebuild.mutate()}>
            {rebuild.isPending ? '正在更新…' : '更新填写建议'}
          </Button>
        </Stack>
        <LinearProgress variant="determinate" value={total ? reviewed / total * 100 : 0} sx={{ mt: 2, height: 5, borderRadius: 1 }} />
      </Paper>

      <Box><Grid container spacing={2}>
        <Grid item xs={12} md={4}>
          <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
            <Box sx={{ p: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
              <Typography variant="h6">填写位置 · {Math.max(total - reviewed, 0)} 项待处理</Typography>
              <Typography variant="caption" color="text.secondary">点击一项，查看建议与原文位置</Typography>
            </Box>
            <Box className="custom-scrollbar" sx={{ maxHeight: 620, overflow: 'auto' }}>
              {[...groupedTargets.entries()].map(([pageId, targets]) => (
                <Box key={pageId}>
                  <Typography variant="overline" sx={{ px: 2, pt: 2, display: 'block' }}>
                    第 {(templatePages.data?.find((page) => page.id === pageId)?.page_index ?? 0) + 1} 页
                  </Typography>
                  {targets.map((target) => {
                    const suggestion = target.suggestions[0];
                    return (
                      <Box
                        key={target.id}
                        component="button"
                        onClick={() => setSelectedTargetId(target.id)}
                        aria-pressed={selectedTarget?.id === target.id}
                        sx={{
                          width: '100%', display: 'block', textAlign: 'left', font: 'inherit',
                          border: 0,
                          p: 2,
                          cursor: 'pointer',
                          borderBottom: '1px solid', borderColor: 'divider',
                          bgcolor:
                            selectedTarget?.id === target.id
                              ? 'rgba(183,67,43,.08)'
                              : 'transparent',
                        }}
                      >
                        <Stack direction="row" justifyContent="space-between" gap={1}>
                          <Typography fontWeight={600}>{target.label}</Typography>
                          <Chip
                            size="small"
                            color={['accepted', 'edited'].includes(suggestion?.status) ? 'success' : suggestion?.status === 'rejected' ? 'default' : 'warning'}
                            label={statusLabel[suggestion?.status ?? ''] ?? '待填写'}
                          />
                        </Stack>
                        <Typography variant="body2" sx={{ mt: 1 }}>
                          {suggestion?.value || '尚无可填写值'}
                        </Typography>
                      </Box>
                    );
                  })}
                </Box>
              ))}
              {selectedPlan?.targets.length === 0 && (
                <Typography color="text.secondary" sx={{ p: 3 }}>
                  未识别到可填写位置。请确认模板包含可解析的表格或下划线字段。
                </Typography>
              )}
            </Box>
          </Paper>
        </Grid>

        <Grid item xs={12} md={8}>
          <Stack spacing={2}>
            {selectedSuggestion && (
              <Paper variant="outlined" sx={{ p: 2.5 }}>
                <Stack spacing={2}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center" gap={1}><Typography variant="h6">{selectedTarget?.label} · 填写内容</Typography><Chip label={statusLabel[selectedSuggestion.status] ?? '待补充'} size="small" /></Stack>
                  <Typography variant="body2" color="text.secondary">{selectedSuggestion.rationale.replace(/项目响应值/g, '填写资料')}</Typography>
                  <TextField
                    label="准备填写的内容" multiline minRows={3}
                    value={draftValues[selectedSuggestion.id] ?? selectedSuggestion.value ?? ''}
                    onChange={(event) => setDraftValues((current) => ({ ...current, [selectedSuggestion.id]: event.target.value }))}
                    helperText="没有建议内容时，可直接输入已核实的真实内容。保存后会显示在下方标注图中。"
                  />
                  <Stack direction="row" gap={1} flexWrap="wrap">
                    <Button variant="contained" disabled={save.isPending || !(draftValues[selectedSuggestion.id] ?? selectedSuggestion.value ?? '').trim()} onClick={() => {
                      const value = draftValues[selectedSuggestion.id] ?? selectedSuggestion.value ?? '';
                      save.mutate({ suggestion: selectedSuggestion, value, status: value === selectedSuggestion.value ? 'accepted' : 'edited' });
                    }}>{save.isPending ? '保存中…' : nextPending ? '确认并处理下一项' : '保存并确认'}</Button>
                    <Button color="inherit" disabled={save.isPending} onClick={() => save.mutate({ suggestion: selectedSuggestion, value: draftValues[selectedSuggestion.id] ?? '', status: 'rejected' })}>暂不采用此项</Button>
                    {nextPending && <Button disabled={save.isPending} onClick={() => setSelectedTargetId(nextPending.id)}>下一处待处理</Button>}
                  </Stack>
                </Stack>
              </Paper>
            )}
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
                <Box>
                  <Typography variant="h6">原页标注预览</Typography>
                  <Typography variant="body2" color="text.secondary">
                    建议内容直接显示在原模板中，保存后同步更新。
                  </Typography>
                </Box>
                {selectedAsset && (
                  <Button
                    size="small"
                    href={`/api/v2/annotation-assets/${selectedAsset.id}/image`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    放大标注图
                  </Button>
                )}
              </Stack>
              {selectedAsset ? (
                <AnnotatedImage asset={selectedAsset} />
              ) : (
                <Box sx={{ p: 5, bgcolor: '#f0ece2', textAlign: 'center' }}>
                  <Typography color="text.secondary">
                    该模板没有固定页面图，仍可在下方填写和复核；需要原页面标注图时请上传 PDF。
                  </Typography>
                </Box>
              )}
            </Paper>

          </Stack>
        </Grid>
      </Grid></Box>
    </Stack>
  );
}

function AnnotatedImage({ asset }: { asset: AnnotationAsset }) {
  return (
    <Box className="page-canvas paper-frame" sx={{ overflow: 'auto', maxHeight: 660 }}>
      <img
        src={`/api/v2/annotation-assets/${asset.id}/image?v=${encodeURIComponent(asset.updated_at)}`}
        alt="模板标注图"
        style={{ minWidth: 520 }}
      />
    </Box>
  );
}

function apiError(error: unknown, fallback: string) {
  if (typeof error === 'object' && error && 'response' in error) {
    const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (detail) return detail;
  }
  return error instanceof Error ? error.message : fallback;
}
