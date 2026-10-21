import { useEffect, useMemo, useState } from 'react';
import { isAxiosError } from 'axios';
import {
  Alert,
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  MenuItem,
  Paper,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  LinearProgress,
} from '@mui/material';
import ExpandMoreRounded from '@mui/icons-material/ExpandMoreRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ConfirmDialog, EmptyState, Notice } from '../components/Workspace';
import FillTargetEditor from '../components/FillTargetEditor';
import PageViewer from '../components/PageViewer';
import {
  api,
  apiError,
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
  const [editingTarget, setEditingTarget] = useState<FillTarget | null | undefined>(undefined);
  const [deletingTarget, setDeletingTarget] = useState<FillTarget | null>(null);
  const [previewMode, setPreviewMode] = useState('annotation');
  const [viewingSource, setViewingSource] = useState<FillSuggestion['source_refs'][number] | null>(null);
  const runtime = useQuery({ queryKey: ['runtime'], queryFn: async () => (await api.get<{ live_model_calls: boolean }>('/health')).data });
  const sourcePage = useQuery({
    queryKey: ['page', viewingSource?.page_id], enabled: Boolean(viewingSource?.page_id),
    queryFn: async () => (await api.get<PageItem>(`/pages/${viewingSource!.page_id}`)).data,
  });

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
    refetchInterval: (query) => ['queued', 'drafting'].includes(query.state.data?.status ?? '') ? 2000 : false,
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
  const selectedPage = templatePages.data?.find((page) => page.id === selectedTarget?.page_id) ?? templatePages.data?.[0];
  const selectedAsset = selectedPlan?.assets.find((asset) => asset.page_id === selectedPage?.id);

  useEffect(() => {
    if (!selectedTarget || !selectedSuggestion) return;
    setDraftValues((current) => ({
      ...current,
      [selectedSuggestion.id]: selectedSuggestion.value ?? '',
    }));
  }, [selectedSuggestion?.id, selectedSuggestion?.value]);

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
  const draft = useMutation({
    mutationFn: async () => api.post(`/fill-plans/${selectedPlan!.id}/draft`),
    onSuccess: async () => {
      setMessage('正在自动起草，已确认的内容会保留');
      await queryClient.invalidateQueries({ queryKey: ['fill-plan', runId, templateId] });
    },
    onError: (err) => setError(apiError(err, '提交起草任务失败')),
  });
  const removeTarget = useMutation({
    mutationFn: async () => (await api.delete<FillPlan>(`/fill-targets/${deletingTarget!.id}`)).data,
    onSuccess: async (result) => {
      setDeletingTarget(null); setSelectedTargetId(''); setMessage('填写位置已移除，更新建议时不会重新添加');
      queryClient.setQueryData(['fill-plan', runId, templateId], result);
      await queryClient.invalidateQueries({ queryKey: ['checklist', runId] });
      await queryClient.invalidateQueries({ queryKey: ['run', runId] });
    },
    onError: (err) => { setDeletingTarget(null); setError(apiError(err, '移除填写位置失败')); },
  });
  const renderedPages = templatePages.data?.filter((page) => !page.quality_flags.some((flag) => ['no_page_coordinates', 'spreadsheet_coordinates'].includes(flag))) ?? [];

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
      <Paper variant="outlined"><EmptyState title="上传需要填写的投标模板" description="支持 PDF、Word 和 Excel。" action={<Button component={Link} to={`/projects/${projectId}?upload=template#files`} variant="contained">上传模板</Button>} /></Paper>
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
      {error && <Alert severity="error">{error}</Alert>}
      {plan.error && <Alert severity="error">{apiError(plan.error, '加载填写计划失败')}</Alert>}
      {selectedPlan?.status === 'failed' && <Alert severity="error">AI 起草未完成，已保存的内容仍可查看。请检查模型设置后重新生成。</Alert>}
      <Notice message={message} onClose={() => setMessage('')} />
      <Paper variant="outlined" sx={{ px: 2, pt: 1.5, pb: 1 }}>
        <Stack direction="row" alignItems="center" gap={1.5} flexWrap="wrap">
          <TextField
            select
            size="small"
            label="投标模板"
            value={templateId ?? ''}
            onChange={(event) => {
              setTemplateChoiceId(event.target.value);
              setSelectedTargetId('');
            }}
            sx={{ width: { xs: '100%', sm: 240 } }}
          >
            {templates.map((document) => (
              <MenuItem key={document.id} value={document.id}>{document.filename}</MenuItem>
            ))}
          </TextField>
          <Typography variant="body2" color="text.secondary" sx={{ flex: 1, whiteSpace: 'nowrap' }}>已处理 {reviewed} / {total}</Typography>
          <Button disabled={rebuild.isPending || ['queued', 'drafting'].includes(selectedPlan?.status ?? '')} onClick={() => rebuild.mutate()}>
            {rebuild.isPending ? '正在更新…' : '重新定位'}
          </Button>
          <Button disabled={!runtime.data?.live_model_calls || !selectedPlan || draft.isPending || ['queued', 'drafting'].includes(selectedPlan.status)} onClick={() => draft.mutate()}>{['queued', 'drafting'].includes(selectedPlan?.status ?? '') ? '正在起草…' : 'AI 生成建议'}</Button>
          <Button variant="outlined" disabled={!selectedPlan || !renderedPages.length} onClick={() => setEditingTarget(null)}>添加填写位置</Button>
        </Stack>
        <LinearProgress variant="determinate" value={total ? reviewed / total * 100 : 0} sx={{ mt: 1.5, height: 2 }} />
      </Paper>

      <Box><Grid container spacing={2}>
        <Grid item xs={12} md={4}>
          <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
            <Box className="custom-scrollbar" sx={{ maxHeight: { xs: 240, md: 620 }, overflow: 'auto' }}>
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
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 1, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                          {suggestion?.value || '尚无可填写值'}
                        </Typography>
                      </Box>
                    );
                  })}
                </Box>
              ))}
              {selectedPlan?.targets.length === 0 && (
                <EmptyState title="暂无填写位置" action={<Button disabled={!renderedPages.length} onClick={() => setEditingTarget(null)}>手工框选位置</Button>} />
              )}
            </Box>
          </Paper>
        </Grid>

        <Grid item xs={12} md={8} sx={{ minWidth: 0 }}>
          <Stack spacing={2}>
            {selectedSuggestion && (
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Stack spacing={2}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center" gap={1}><Typography variant="h6">{selectedTarget?.label}</Typography><Chip label={statusLabel[selectedSuggestion.status] ?? '待补充'} size="small" /></Stack>
                  {selectedSuggestion.rationale && <Typography variant="caption" color="text.secondary">{selectedSuggestion.rationale.replace(/项目响应值/g, '填写资料')}</Typography>}
                  {Boolean(selectedSuggestion.source_refs?.length) && <Accordion disableGutters elevation={0} sx={{ border: '1px solid', borderColor: 'divider' }}><AccordionSummary expandIcon={<ExpandMoreRounded />}><Typography variant="body2">填写依据 · {selectedSuggestion.source_refs.length} 处来源</Typography></AccordionSummary><AccordionDetails><Stack spacing={1.5}>{selectedSuggestion.source_refs.map((source, index) => <Box key={source.source_span_id ?? source.response_value_id ?? index}>{source.page_id ? <Button size="small" sx={{ p: 0 }} onClick={() => setViewingSource(source)}>{source.filename ?? '查看原文'}{source.page_index !== undefined ? ` · 第 ${source.page_index + 1} 页` : ''}</Button> : <Typography variant="caption" fontWeight={600}>{source.label ?? '项目填写资料'}</Typography>}<Typography variant="caption" color="text.secondary" display="block" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{source.quote ?? source.value}</Typography></Box>)}</Stack></AccordionDetails></Accordion>}
                  <TextField
                    label="准备填写的内容" multiline minRows={3}
                    disabled={['queued', 'drafting'].includes(selectedPlan?.status ?? '')}
                    value={draftValues[selectedSuggestion.id] ?? selectedSuggestion.value ?? ''}
                    onChange={(event) => setDraftValues((current) => ({ ...current, [selectedSuggestion.id]: event.target.value }))}
                  />
                  <Stack direction="row" gap={1} flexWrap="wrap">
                    <Button variant="contained" disabled={save.isPending || !(draftValues[selectedSuggestion.id] ?? selectedSuggestion.value ?? '').trim()} onClick={() => {
                      const value = draftValues[selectedSuggestion.id] ?? selectedSuggestion.value ?? '';
                      save.mutate({ suggestion: selectedSuggestion, value, status: value === selectedSuggestion.value ? 'accepted' : 'edited' });
                    }}>{save.isPending ? '保存中…' : nextPending ? '确认并处理下一项' : '保存并确认'}</Button>
                    <Button color="inherit" disabled={save.isPending} onClick={() => save.mutate({ suggestion: selectedSuggestion, value: draftValues[selectedSuggestion.id] ?? '', status: 'rejected' })}>暂不采用此项</Button>
                    {nextPending && <Button disabled={save.isPending} onClick={() => setSelectedTargetId(nextPending.id)}>下一处待处理</Button>}
                  </Stack>
                  {selectedTarget && <Stack direction="row" gap={1}><Button size="small" disabled={!renderedPages.some((page) => page.id === selectedTarget.page_id)} onClick={() => setEditingTarget(selectedTarget)}>编辑字段与位置</Button><Button size="small" color="error" onClick={() => setDeletingTarget(selectedTarget)}>移除此位置</Button></Stack>}
                </Stack>
              </Paper>
            )}
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
                <ToggleButtonGroup exclusive size="small" value={previewMode} onChange={(_, value) => { if (value) setPreviewMode(value); }} aria-label="预览方式"><ToggleButton value="annotation">填写标注</ToggleButton><ToggleButton value="original">原页</ToggleButton></ToggleButtonGroup>
                {selectedAsset && (
                  <Button
                    size="small"
                    href={previewMode === 'original' && selectedPage ? `/api/v2/pages/${selectedPage.id}/image` : `/api/v2/annotation-assets/${selectedAsset.id}/image`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    放大查看
                  </Button>
                )}
              </Stack>
              {previewMode === 'original' && selectedPage ? <PageViewer page={selectedPage} /> : selectedAsset ? (
                <AnnotatedImage asset={selectedAsset} />
              ) : (
                <Box sx={{ p: 5, bgcolor: '#f0ece2', textAlign: 'center' }}>
                  <Typography color="text.secondary">
                    暂无原页标注图，请先添加填写位置。
                  </Typography>
                </Box>
              )}
            </Paper>

          </Stack>
        </Grid>
      </Grid></Box>
      {editingTarget !== undefined && selectedPlan && <FillTargetEditor key={editingTarget?.id ?? 'new'} plan={selectedPlan} pages={renderedPages} target={editingTarget} onClose={() => setEditingTarget(undefined)} onSaved={async (result, label) => {
        queryClient.setQueryData(['fill-plan', runId, templateId], result);
        setSelectedTargetId(result.targets.find((target) => target.label === label)?.id ?? '');
        setMessage('填写位置已保存，可继续输入填写内容');
        await queryClient.invalidateQueries({ queryKey: ['checklist', runId] });
        await queryClient.invalidateQueries({ queryKey: ['run', runId] });
      }} />}
      <ConfirmDialog open={Boolean(deletingTarget)} title="移除此填写位置？" description={`将移除「${deletingTarget?.label ?? ''}」及其建议内容和标注。原模板保持原样，更新建议时不会重新添加此位置。`} pending={removeTarget.isPending} onClose={() => setDeletingTarget(null)} onConfirm={() => removeTarget.mutate()} />
      <Dialog open={Boolean(viewingSource)} onClose={() => setViewingSource(null)} fullWidth maxWidth="md"><DialogTitle>{viewingSource?.filename ?? '填写依据'}</DialogTitle><DialogContent>{sourcePage.isLoading ? <EmptyState loading title="正在加载原文" /> : sourcePage.data ? <PageViewer page={sourcePage.data} highlight={viewingSource?.page_id && viewingSource.bbox_json ? { page_id: viewingSource.page_id, bbox_json: viewingSource.bbox_json, quote: viewingSource.quote ?? '' } : undefined} /> : <EmptyState title="来源页暂不可用" />}</DialogContent><DialogActions><Button onClick={() => setViewingSource(null)}>关闭</Button></DialogActions></Dialog>
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
