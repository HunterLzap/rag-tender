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
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
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
  accepted: '已接受',
  edited: '已修改',
  missing_evidence: '缺少依据',
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
    selectedPlan?.targets.find((target) => target.suggestions.length > 0) ??
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
      setMessage('填写建议已保存');
      await queryClient.invalidateQueries({ queryKey: ['fill-plan', runId, templateId] });
    },
    onError: (err) => setError(apiError(err, '保存填写建议失败')),
  });

  const rebuild = useMutation({
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

  if (!templates.length) {
    return (
      <Alert severity="info">
        请先在项目页上传一个标记为「投标模板」的 PDF、DOCX 或 XLSX 文件，再生成填写建议。
      </Alert>
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
      {message && <Alert severity="success">{message}</Alert>}
      <Paper variant="outlined" sx={{ p: 2, bgcolor: 'rgba(255,253,247,.86)' }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" gap={2} flexWrap="wrap">
          <Box>
            <Typography variant="h6">原模板填写建议</Typography>
            <Typography variant="body2" color="text.secondary">
              {selectedPlan?.targets.length ?? 0} 个填写位置，{selectedPlan?.assets.length ?? 0} 张标注图
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
            重新识别模板
          </Button>
        </Stack>
      </Paper>

      <Grid container spacing={2}>
        <Grid item xs={12} lg={4}>
          <Paper variant="outlined" sx={{ bgcolor: 'rgba(255,253,247,.88)', overflow: 'hidden' }}>
            <Box sx={{ p: 2, borderBottom: '1px solid #ded5c5' }}>
              <Typography variant="h6">填写位置</Typography>
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
                        onClick={() => setSelectedTargetId(target.id)}
                        sx={{
                          p: 2,
                          cursor: 'pointer',
                          borderBottom: '1px solid #eee7db',
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

        <Grid item xs={12} lg={8}>
          <Stack spacing={2}>
            <Paper variant="outlined" sx={{ p: 2, bgcolor: 'rgba(255,253,247,.88)' }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
                <Box>
                  <Typography variant="h6">{selectedTarget?.label || '选择一个填写位置'}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {selectedSuggestion?.rationale || '标注图会直接叠加在原始模板页面上。'}
                  </Typography>
                </Box>
                {selectedAsset && (
                  <Button
                    size="small"
                    href={`/api/v2/annotation-assets/${selectedAsset.id}/image`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    查看原图
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

            {selectedSuggestion && (
              <Paper variant="outlined" sx={{ p: 2.5, bgcolor: 'rgba(255,253,247,.88)' }}>
                <Stack spacing={1.5}>
                  <Typography variant="subtitle1">填写内容与审阅</Typography>
                  <TextField
                    label="建议填写值"
                    multiline
                    minRows={2}
                    value={draftValues[selectedSuggestion.id] ?? selectedSuggestion.value ?? ''}
                    onChange={(event) =>
                      setDraftValues((current) => ({
                        ...current,
                        [selectedSuggestion.id]: event.target.value,
                      }))
                    }
                  />
                  <Stack direction="row" spacing={1}>
                    <Button
                      variant="contained"
                      disabled={save.isPending}
                      onClick={() =>
                        save.mutate({
                          suggestion: selectedSuggestion,
                          value: draftValues[selectedSuggestion.id] ?? '',
                          status: 'accepted',
                        })
                      }
                    >
                      接受建议
                    </Button>
                    <Button
                      variant="outlined"
                      disabled={save.isPending}
                      onClick={() =>
                        save.mutate({
                          suggestion: selectedSuggestion,
                          value: draftValues[selectedSuggestion.id] ?? '',
                          status: 'edited',
                        })
                      }
                    >
                      保存修改
                    </Button>
                    <Button
                      color="error"
                      disabled={save.isPending}
                      onClick={() =>
                        save.mutate({
                          suggestion: selectedSuggestion,
                          value: draftValues[selectedSuggestion.id] ?? '',
                          status: 'rejected',
                        })
                      }
                    >
                      拒绝
                    </Button>
                  </Stack>
                </Stack>
              </Paper>
            )}
          </Stack>
        </Grid>
      </Grid>
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
