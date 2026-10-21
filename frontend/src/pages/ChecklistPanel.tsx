import { useState } from 'react';
import { Alert, Box, Button, Checkbox, Chip, Divider, LinearProgress, Paper, Stack, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';
import DownloadOutlined from '@mui/icons-material/DownloadOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api, apiError, type AnalysisReport, type AnalysisRun, type ChecklistItem } from '../lib/api';
import { EmptyState } from '../components/Workspace';

const severityLabel: Record<string, string> = { blocker: '必须处理', warning: '需要核验', info: '提示' };

export default function ChecklistPanel({ runId }: { runId: string }) {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState('open');
  const [error, setError] = useState('');
  const [exporting, setExporting] = useState(false);
  const checklist = useQuery({ queryKey: ['checklist', runId], queryFn: async () => (await api.get<ChecklistItem[]>(`/analysis-runs/${runId}/checklist`)).data });
  const run = useQuery({ queryKey: ['run', runId], queryFn: async () => (await api.get<AnalysisRun>(`/analysis-runs/${runId}`)).data });
  const toggle = useMutation({
    mutationFn: async (item: ChecklistItem) => (await api.patch<ChecklistItem>(`/checklist/${item.id}`, { completed: !item.completed })).data,
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ['checklist', runId] }); await queryClient.invalidateQueries({ queryKey: ['run', runId] }); },
    onError: (err) => setError(apiError(err, '更新检查项失败')),
  });
  async function exportReport() {
    setExporting(true); setError('');
    try {
      const report = (await api.get<AnalysisReport>(`/analysis-runs/${runId}/report`)).data;
      const url = URL.createObjectURL(new Blob([report.markdown], { type: 'text/markdown;charset=utf-8' }));
      const link = document.createElement('a'); link.href = url; link.download = '投标准备检查报告.md';
      link.click(); URL.revokeObjectURL(url);
    } catch (err) { setError(apiError(err, '导出报告失败')); }
    finally { setExporting(false); }
  }
  async function exportBundle() {
    setExporting(true); setError('');
    try {
      const result = await api.get<Blob>(`/analysis-runs/${runId}/export`, { responseType: 'blob' });
      const url = URL.createObjectURL(result.data);
      const link = document.createElement('a'); link.href = url; link.download = '投标准备资料.zip';
      link.click(); URL.revokeObjectURL(url);
    } catch (err) { setError(apiError(err, '导出资料包失败，请确认填写建议和标注图已就绪')); }
    finally { setExporting(false); }
  }
  const total = checklist.data?.length ?? 0;
  const open = checklist.data?.filter((item) => !item.completed) ?? [];
  const rows = filter === 'open' ? open : checklist.data ?? [];
  const finished = total - open.length;
  return (
    <Stack spacing={2}>
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      {checklist.isError && <Alert severity="error">检查清单加载失败，请刷新页面重试。</Alert>}
      <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
        <Stack direction="row" alignItems="center" gap={1.5} flexWrap="wrap" sx={{ p: 2 }}>
          <ToggleButtonGroup exclusive size="small" value={filter} onChange={(_, value) => { if (value) setFilter(value); }} aria-label="筛选检查事项"><ToggleButton value="open">待处理 {open.length}</ToggleButton><ToggleButton value="all">全部 {total}</ToggleButton></ToggleButtonGroup>
          <Typography variant="body2" color="text.secondary" sx={{ flex: 1, whiteSpace: 'nowrap' }}>已处理 {finished} / {total}</Typography>
          <Button disabled={exporting || !run.data || ['running', 'draft'].includes(run.data.status) || checklist.isLoading} onClick={() => void exportReport()}>检查报告</Button>
          <Button variant="contained" startIcon={<DownloadOutlined />} disabled={exporting || !run.data || ['running', 'draft'].includes(run.data.status) || checklist.isLoading} onClick={() => void exportBundle()}>{exporting ? '导出中…' : '导出资料包'}</Button>
        </Stack>
        <LinearProgress variant="determinate" value={total ? finished / total * 100 : 0} sx={{ height: 2 }} />
        {checklist.isLoading ? <EmptyState title="正在加载检查清单" loading /> : !rows.length ? <EmptyState title={total ? '当前没有待处理事项' : '暂无检查事项'} /> : <Stack divider={<Divider />}>
          {rows.map((item) => <Stack key={item.id} direction="row" alignItems="flex-start" gap={1} sx={{ p: 2 }}>
            <Checkbox checked={item.completed} disabled={toggle.isPending} onChange={() => toggle.mutate(item)} inputProps={{ 'aria-label': `${item.completed ? '标记为待处理' : '标记为已处理'}：${item.title}` }} />
            <Box sx={{ flex: 1, pt: 0.75 }}><Stack direction="row" gap={1} flexWrap="wrap" alignItems="center"><Typography fontWeight={600} sx={{ textDecoration: item.completed ? 'line-through' : 'none', color: item.completed ? 'text.secondary' : 'text.primary' }}>{item.title}</Typography><Chip color={item.completed ? 'default' : item.severity === 'blocker' ? 'error' : item.severity === 'warning' ? 'warning' : 'info'} label={item.completed ? '已处理' : severityLabel[item.severity] ?? '待核验'} /></Stack>{item.detail && <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>{item.detail}</Typography>}<Button component={Link} size="small" sx={{ mt: 0.5, ml: -1 }} to={item.title.startsWith('确认填写：') ? `/runs/${runId}?tab=fill` : item.requirement_id ? `/runs/${runId}?tab=requirements&requirement=${item.requirement_id}` : `/projects/${run.data?.project_id}`}>{item.title.startsWith('确认填写：') ? '前往填写' : item.requirement_id ? '核对这条要求' : '查看原文资料'}</Button></Box>
          </Stack>)}
        </Stack>}
      </Paper>
    </Stack>
  );
}
