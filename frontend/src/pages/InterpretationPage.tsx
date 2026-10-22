import { useState } from 'react';
import { Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Chip, Divider, Drawer, IconButton, Paper, Stack, Tab, Tabs, TextField, Typography } from '@mui/material';
import CloseRounded from '@mui/icons-material/CloseRounded';
import ExpandMoreRounded from '@mui/icons-material/ExpandMoreRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import PageViewer from '../components/PageViewer';
import { EmptyState, Notice, PageHeader } from '../components/Workspace';
import { api, apiError, type PageItem, type SourceSpan } from '../lib/api';
import { statusLabels } from '../lib/labels';

interface ReadingItem {
  id: string; title: string; content: string; filename: string; page_index: number;
  role: string; source_span: SourceSpan; requirement_id: string | null;
  state: 'active' | 'superseded' | 'rejected' | 'conflict';
  decision_status: string | null; decision_stale: boolean;
}
interface TenderReading {
  project_id: string; run_id: string | null; document_count: number;
  pending_documents: { filename: string; status: string }[]; amendments_pending: boolean;
  coverage_notes: string[];
  sections: { key: string; title: string; items: ReadingItem[] }[];
}
const states = { superseded: '已替代', rejected: '已否决', conflict: '待确认', active: '' };

export default function InterpretationPage() {
  const { projectId = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [source, setSource] = useState<ReadingItem | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [exporting, setExporting] = useState(false);
  const reading = useQuery({
    queryKey: ['interpretation', projectId],
    queryFn: async () => (await api.get<TenderReading>(`/projects/${projectId}/interpretation`)).data,
    refetchInterval: 3000,
  });
  const runtime = useQuery({ queryKey: ['runtime'], queryFn: async () => (await api.get<{ live_model_calls: boolean }>('/health')).data });
  const pages = useQuery({
    queryKey: ['document-pages', source?.source_span.document_id], enabled: Boolean(source),
    queryFn: async () => (await api.get<PageItem[]>(`/documents/${source!.source_span.document_id}/pages`)).data,
  });
  const interpret = useMutation({
    mutationFn: async () => api.post(`/projects/${projectId}/interpretation`),
    onSuccess: async () => {
      setMessage('已开始整理标书');
      await queryClient.invalidateQueries({ queryKey: ['interpretation', projectId] });
      await queryClient.invalidateQueries({ queryKey: ['runs', projectId] });
    },
    onError: (err) => setError(apiError(err, '提交解读失败')),
  });
  async function download() {
    setError(''); setExporting(true);
    try {
      const result = await api.get<Blob>(`/projects/${projectId}/interpretation/export`, { responseType: 'blob' });
      const url = URL.createObjectURL(result.data);
      const link = document.createElement('a'); link.href = url; link.download = '标书解读.md';
      link.click(); URL.revokeObjectURL(url); setMessage('解读文件已生成，已开始下载');
    } catch (err) { setError(apiError(err, '导出解读失败')); }
    finally { setExporting(false); }
  }
  const section = reading.data?.sections.find((item) => item.key === params.get('section')) ?? reading.data?.sections[0];
  const items = section?.items.filter((item) => `${item.title} ${item.content} ${item.filename}`.toLowerCase().includes(search.toLowerCase())) ?? [];
  const busy = reading.data?.pending_documents.some((item) => ['queued', 'running'].includes(item.status));
  const page = pages.data?.find((item) => item.id === source?.source_span.page_id);
  return <Stack spacing={2}>
    <PageHeader title="标书解读" actions={<>
      <Button component={Link} to={`/projects/${projectId}`}>项目资料</Button>
      <Button disabled={!reading.data || exporting || busy || !reading.data.document_count} onClick={() => void download()}>导出解读</Button>
      <Button variant="contained" disabled={!runtime.data?.live_model_calls || interpret.isPending || busy || !reading.data?.document_count} onClick={() => interpret.mutate()}>{busy ? '正在整理…' : '解读标书'}</Button>
    </>} />
    <Notice message={message} onClose={() => setMessage('')} />
    {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
    {reading.isError ? <Alert severity="error">标书解读加载失败，请刷新重试。</Alert> : reading.isLoading ? <EmptyState loading title="正在加载标书解读" /> : !reading.data?.document_count ? <EmptyState title="先上传项目标书" description="支持招标文件、补遗和答疑；整理关键条款并保留原文出处。" action={<Button component={Link} to={`/projects/${projectId}`}>上传标书</Button>} /> : <>
      {reading.data.amendments_pending && <Alert severity="warning">补遗与原条款的适用关系尚待核对，请结合原文确认。</Alert>}
      {!!reading.data.coverage_notes.length && <Accordion variant="outlined" disableGutters><AccordionSummary expandIcon={<ExpandMoreRounded />}><Typography variant="body2" color="warning.main">{reading.data.coverage_notes.length} 项解读待核对</Typography></AccordionSummary><AccordionDetails><Stack spacing={1}>{reading.data.coverage_notes.map((note) => <Typography variant="body2" key={note}>{note}</Typography>)}</Stack></AccordionDetails></Accordion>}
      {!!reading.data.pending_documents.length && <Typography variant="body2" color="text.secondary">{reading.data.pending_documents.map((item) => `${item.filename} · ${statusLabels[item.status] ?? '待处理'}`).join('；')}</Typography>}
      <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
        <Tabs value={section?.key ?? 'overview'} variant="scrollable" scrollButtons="auto" onChange={(_, value) => setParams({ section: value })} aria-label="标书解读分类" sx={{ px: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
          {reading.data.sections.map((item) => <Tab key={item.key} value={item.key} label={`${item.title} ${item.items.length}`} />)}
        </Tabs>
        <Box sx={{ p: 2 }}><TextField label="搜索解读内容" value={search} onChange={(event) => setSearch(event.target.value)} /></Box>
        {!items.length ? <EmptyState title={search ? '没有匹配的条目' : '暂无已核实的条目'} description={search ? '换个关键词试试。' : '可解读标书，并对照原文核对本类信息。'} /> : <Stack divider={<Divider />}>
          {items.map((item) => <Box key={`${item.id}-${item.filename}`} sx={{ px: 2, py: 2, opacity: ['superseded', 'rejected'].includes(item.state) ? 0.65 : 1 }}>
            <Stack direction="row" gap={1} alignItems="center" flexWrap="wrap"><Typography fontWeight={600}>{item.title}</Typography>{states[item.state] && <Chip size="small" color={item.state === 'conflict' ? 'warning' : 'default'} label={states[item.state]} />}{item.decision_status && <Chip size="small" label={item.decision_stale ? '结论待重核' : statusLabels[item.decision_status]} />}</Stack>
            <Typography variant="body2" sx={{ mt: 1, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{item.content}</Typography>
            <Stack direction="row" gap={1} alignItems="center" flexWrap="wrap" sx={{ mt: 1 }}><Button size="small" color="inherit" onClick={() => setSource(item)}>{item.filename} · 第 {item.page_index + 1} 页</Button>{reading.data.run_id && item.requirement_id && <Button size="small" component={Link} to={`/runs/${reading.data.run_id}?tab=requirements&requirement=${item.requirement_id}`}>核对条款</Button>}</Stack>
          </Box>)}
        </Stack>}
      </Paper>
    </>}
    <Drawer anchor="right" open={Boolean(source)} onClose={() => setSource(null)} PaperProps={{ sx: { width: { xs: '100%', md: 760 } } }}>
      <Stack spacing={2} sx={{ p: 2 }}><Stack direction="row" justifyContent="space-between" alignItems="center"><Typography fontWeight={600}>{source?.filename} · 第 {(source?.page_index ?? 0) + 1} 页</Typography><IconButton aria-label="关闭原文" onClick={() => setSource(null)}><CloseRounded /></IconButton></Stack>{page ? <PageViewer page={page} highlight={source?.source_span} /> : pages.isError ? <Alert severity="error">原文加载失败，请重新打开。</Alert> : <EmptyState loading title="正在加载原文" />}</Stack>
    </Drawer>
  </Stack>;
}
