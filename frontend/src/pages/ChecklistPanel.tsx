import { useEffect, useState } from 'react';
import { Alert, Box, Button, Checkbox, Chip, Divider, LinearProgress, Paper, Stack, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';
import DownloadOutlined from '@mui/icons-material/DownloadOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api, apiError, type AnalysisReport, type AnalysisRun, type ChecklistItem, type Job } from '../lib/api';
import { EmptyState, Notice } from '../components/Workspace';

const severityLabel: Record<string, string> = { blocker: '必须处理', warning: '需要核验', info: '提示' };

export default function ChecklistPanel({ runId }: { runId: string }) {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState('open');
  const [error, setError] = useState('');
  const [exporting, setExporting] = useState<'report' | 'bundle' | null>(null);
  const [message, setMessage] = useState('');
  const checklist = useQuery({ queryKey: ['checklist', runId], queryFn: async () => (await api.get<ChecklistItem[]>(`/analysis-runs/${runId}/checklist`)).data });
  const run = useQuery({ queryKey: ['run', runId], queryFn: async () => (await api.get<AnalysisRun>(`/analysis-runs/${runId}`)).data });
  const jobs = useQuery({
    queryKey: ['checklist-jobs', runId], enabled: Boolean(run.data?.project_id),
    queryFn: async () => (await api.get<Job[]>(`/projects/${run.data!.project_id}/jobs`)).data,
    refetchInterval: 2500,
  });
  const busy = ['draft', 'running'].includes(run.data?.status ?? '') || Boolean(jobs.data?.some(
    (job) => job.payload.run_id === runId && ['queued', 'running'].includes(job.status),
  ));
  useEffect(() => {
    if (!busy) {
      void queryClient.invalidateQueries({ queryKey: ['checklist', runId] });
      void queryClient.invalidateQueries({ queryKey: ['run', runId] });
    }
  }, [busy, queryClient, runId]);
  const toggle = useMutation({
    mutationFn: async (item: ChecklistItem) => (await api.patch<ChecklistItem>(`/checklist/${item.id}`, { completed: !item.completed })).data,
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ['checklist', runId] }); await queryClient.invalidateQueries({ queryKey: ['run', runId] }); },
    onError: (err) => setError(apiError(err, '更新检查项失败')),
  });
  async function exportReport() {
    setExporting('report'); setError(''); setMessage('');
    try {
      const report = (await api.get<AnalysisReport>(`/analysis-runs/${runId}/report`)).data;
      const url = URL.createObjectURL(new Blob([report.markdown], { type: 'text/markdown;charset=utf-8' }));
      const link = document.createElement('a'); link.href = url; link.download = '投标准备检查报告.md';
      link.click(); URL.revokeObjectURL(url);
      setMessage('检查报告已生成，已开始下载');
    } catch (err) { setError(apiError(err, '导出报告失败')); }
    finally { setExporting(null); }
  }
  async function exportBundle() {
    setExporting('bundle'); setError(''); setMessage('');
    try {
      const result = await api.get<Blob>(`/analysis-runs/${runId}/export`, { responseType: 'blob' });
      const url = URL.createObjectURL(result.data);
      const link = document.createElement('a'); link.href = url; link.download = '投标准备资料.zip';
      link.click(); URL.revokeObjectURL(url);
      setMessage('资料包已生成，已开始下载');
    } catch (err) { setError(apiError(err, '导出资料包失败，请确认填写建议和标注图已就绪')); }
    finally { setExporting(null); }
  }
  const total = checklist.data?.length ?? 0;
  const open = checklist.data?.filter((item) => !item.completed) ?? [];
  const rows = filter === 'open' ? open : checklist.data ?? [];
  const finished = total - open.length;
  return (
    <Stack spacing={2}>
      <Notice message={message} onClose={() => setMessage('')} />
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      {jobs.isError && <Alert severity="error">任务状态加载失败，请刷新页面重试。</Alert>}
      {checklist.isError && <Alert severity="error">检查清单加载失败，请刷新页面重试。</Alert>}
      <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
        <Stack direction="row" alignItems="center" gap={1.5} flexWrap="wrap" sx={{ p: 2 }}>
          <ToggleButtonGroup exclusive size="small" value={filter} onChange={(_, value) => { if (value) setFilter(value); }} aria-label="筛选检查事项"><ToggleButton value="open">待处理 {open.length}</ToggleButton><ToggleButton value="all">全部 {total}</ToggleButton></ToggleButtonGroup>
          <Typography variant="body2" color="text.secondary" sx={{ flex: 1, whiteSpace: 'nowrap' }}>已处理 {finished} / {total}</Typography>
          <Button disabled={Boolean(exporting) || !run.data || busy || !jobs.data || checklist.isLoading} onClick={() => void exportReport()}>{exporting === 'report' ? '生成报告中…' : '下载检查报告'}</Button>
          <Button variant="contained" startIcon={<DownloadOutlined />} disabled={Boolean(exporting) || !run.data || busy || !jobs.data || checklist.isLoading} onClick={() => void exportBundle()}>{exporting === 'bundle' ? '导出中…' : '导出资料包'}</Button>
        </Stack>
        <LinearProgress variant="determinate" value={total ? finished / total * 100 : 0} sx={{ height: 2 }} />
        {checklist.isLoading ? <EmptyState title="正在加载检查清单" loading /> : !rows.length ? <EmptyState title={total ? '当前没有待处理事项' : '暂无检查事项'} /> : <Stack divider={<Divider />}>
          {rows.map((item) => <Stack key={item.id} direction="row" alignItems="flex-start" gap={1} sx={{ p: 2 }}>
            <Checkbox checked={item.completed} disabled={busy || toggle.isPending || Boolean(item.fill_target_id)} onChange={() => toggle.mutate(item)} inputProps={{ 'aria-label': item.fill_target_id ? `填写审阅状态自动同步：${item.title}` : `${item.completed ? '标记为待处理' : '标记为已处理'}：${item.title}` }} />
            <Box sx={{ flex: 1, pt: 0.75 }}><Stack direction="row" gap={1} flexWrap="wrap" alignItems="center"><Typography fontWeight={600} sx={{ textDecoration: item.completed ? 'line-through' : 'none', color: item.completed ? 'text.secondary' : 'text.primary' }}>{item.title}</Typography><Chip color={item.completed ? 'default' : item.severity === 'blocker' ? 'error' : item.severity === 'warning' ? 'warning' : 'info'} label={item.completed ? '已处理' : severityLabel[item.severity] ?? '待核验'} /></Stack>{item.detail && <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>{item.detail}</Typography>}<Button component={Link} size="small" sx={{ mt: 0.5, ml: -1 }} to={item.fill_target_id ? `/runs/${runId}?tab=fill&template=${item.template_document_id ?? ''}&target=${item.fill_target_id}` : item.title.startsWith('确认填写：') ? `/runs/${runId}?tab=fill` : item.requirement_id ? `/runs/${runId}?tab=requirements&requirement=${item.requirement_id}` : `/projects/${run.data?.project_id}`}>{item.title.startsWith('确认填写：') ? '前往填写' : item.requirement_id ? '核对这条要求' : '查看原文资料'}</Button></Box>
          </Stack>)}
        </Stack>}
      </Paper>
    </Stack>
  );
}
