import { useEffect, useRef, useState } from 'react';
import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Divider,
  Grid, LinearProgress, MenuItem, Paper, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import UploadFileOutlined from '@mui/icons-material/UploadFileOutlined';
import AddRounded from '@mui/icons-material/AddRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { api, apiError, uploadDocument, type AnalysisRun, type Bid, type DocumentItem, type Job, type PageItem, type Project, type ResponseValue } from '../lib/api';
import { formatBytes, formatDate, dateTimeInput } from '../lib/format';
import { roleLabels } from '../lib/labels';
import { ConfirmDialog, EmptyState, Guidance, NextButton, PageHeader, ReadyItem, StatusChip, WorkflowNav } from '../components/Workspace';
import PageViewer from '../components/PageViewer';

const presets = ['投标人名称', '联系人', '联系电话', '设备名称', '规格型号', '数量', '交货期'];

export default function ProjectPage() {
  const { projectId = '' } = useParams();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const fileRef = useRef<HTMLInputElement>(null);
  const [role, setRole] = useState(new URLSearchParams(location.search).get('upload') || 'tender');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [infoOpen, setInfoOpen] = useState(false);
  const [projectName, setProjectName] = useState('');
  const [tenderNo, setTenderNo] = useState('');
  const [bidderName, setBidderName] = useState('');
  const [bidDeadline, setBidDeadline] = useState('');
  const [valueOpen, setValueOpen] = useState(false);
  const [editingValue, setEditingValue] = useState<ResponseValue | null>(null);
  const [valueLabel, setValueLabel] = useState('');
  const [valueText, setValueText] = useState('');
  const [editingDoc, setEditingDoc] = useState<DocumentItem | null>(null);
  const [docName, setDocName] = useState('');
  const [docRole, setDocRole] = useState('');
  const [preview, setPreview] = useState<DocumentItem | null>(null);
  const [previewPage, setPreviewPage] = useState('');
  const [deleting, setDeleting] = useState<{ path: string; title: string; description: string } | null>(null);
  const project = useQuery({ queryKey: ['project', projectId], queryFn: async () => (await api.get<Project>(`/projects/${projectId}`)).data });
  const runtime = useQuery({ queryKey: ['runtime'], queryFn: async () => (await api.get<{ live_model_calls: boolean }>('/health')).data });
  const documents = useQuery({ queryKey: ['documents', projectId], queryFn: async () => (await api.get<DocumentItem[]>(`/projects/${projectId}/documents`)).data, refetchInterval: 2500 });
  const runs = useQuery({ queryKey: ['runs', projectId], queryFn: async () => (await api.get<AnalysisRun[]>(`/projects/${projectId}/analysis-runs`)).data, refetchInterval: 2500 });
  const jobs = useQuery({ queryKey: ['jobs', projectId], queryFn: async () => (await api.get<Job[]>(`/projects/${projectId}/jobs`)).data, refetchInterval: 1500 });
  const bids = useQuery({ queryKey: ['bids', projectId], queryFn: async () => (await api.get<Bid[]>(`/projects/${projectId}/bids`)).data });
  const values = useQuery({ queryKey: ['response-values', projectId], queryFn: async () => (await api.get<ResponseValue[]>(`/projects/${projectId}/response-values`)).data });
  const previewPages = useQuery({ queryKey: ['document-pages', preview?.id], enabled: Boolean(preview?.id), queryFn: async () => (await api.get<PageItem[]>(`/documents/${preview!.id}/pages`)).data });
  const page = previewPages.data?.find((item) => item.id === previewPage) ?? previewPages.data?.[0];
  const refresh = async () => {
    await Promise.all(['project', 'projects', 'documents', 'runs', 'jobs', 'bids', 'response-values', 'fill-documents', 'fill-plan'].map((key) => queryClient.invalidateQueries({ queryKey: key === 'projects' || key === 'fill-plan' ? [key] : [key, projectId] })));
  };
  useEffect(() => {
    if (location.hash) document.getElementById(location.hash.slice(1))?.scrollIntoView({ behavior: 'auto', block: 'start' });
  }, [location.hash, project.data?.id]);
  const analyze = useMutation({
    mutationFn: async () => (await api.post<AnalysisRun>(`/projects/${projectId}/analysis-runs`, {})).data,
    onSuccess: async (run) => { await refresh(); navigate(`/runs/${run.id}`); },
    onError: (err) => setError(apiError(err, '创建分析任务失败')),
  });
  const saveInfo = useMutation({
    mutationFn: async () => {
      const deadline = bidDeadline ? new Date(bidDeadline).toISOString() : null;
      await api.patch(`/projects/${projectId}`, { name: projectName.trim(), tender_no: tenderNo.trim() || null, bidder_name: bidderName.trim() || null, bid_deadline: deadline });
      const payload = { bidder_name: bidderName.trim() || '投标人', bid_deadline: deadline, as_of_date: bidDeadline ? bidDeadline.slice(0, 10) : null };
      if (bids.data?.[0]) await api.patch(`/bids/${bids.data[0].id}`, payload);
      else await api.post(`/projects/${projectId}/bids`, payload);
    },
    onSuccess: async () => { setInfoOpen(false); setMessage('项目信息已保存'); await refresh(); },
    onError: (err) => setError(apiError(err, '保存项目信息失败')),
  });
  const saveValue = useMutation({
    mutationFn: async () => {
      const payload = { label: valueLabel.trim(), value_text: valueText.trim(), review_status: 'verified' };
      if (editingValue) await api.patch(`/response-values/${editingValue.id}`, payload);
      else await api.post(`/projects/${projectId}/response-values`, { ...payload, key: `field_${crypto.randomUUID()}`, source: 'manual' });
    },
    onSuccess: async () => { setValueOpen(false); setMessage('填写资料已保存，可在填写建议中更新建议'); await refresh(); },
    onError: (err) => setError(apiError(err, '保存填写资料失败')),
  });
  const saveDoc = useMutation({
    mutationFn: async () => api.patch(`/documents/${editingDoc!.id}`, { filename: docName.trim(), role: docRole }),
    onSuccess: async () => { setEditingDoc(null); setMessage('文件信息已更新'); await refresh(); },
    onError: (err) => setError(apiError(err, '更新文件失败')),
  });
  const remove = useMutation({
    mutationFn: async () => api.delete(deleting!.path),
    onSuccess: async () => { setDeleting(null); setMessage('记录已删除'); await refresh(); },
    onError: (err) => { setDeleting(null); setError(apiError(err, '删除失败')); },
  });
  const cancel = useMutation({ mutationFn: async (jobId: string) => api.post(`/jobs/${jobId}/cancel`), onSuccess: refresh, onError: (err) => setError(apiError(err, '取消任务失败')) });
  function openInfo() {
    setError(''); setProjectName(project.data?.name ?? ''); setTenderNo(project.data?.tender_no ?? '');
    setBidderName(bids.data?.[0]?.bidder_name ?? project.data?.bidder_name ?? '');
    setBidDeadline(dateTimeInput(bids.data?.[0]?.bid_deadline ?? project.data?.bid_deadline)); setInfoOpen(true);
  }
  function openValue(value: ResponseValue | null = null, label = '') {
    setError(''); setEditingValue(value); setValueLabel(value?.label ?? label); setValueText(value?.value_text ?? ''); setValueOpen(true);
  }
  async function handleUpload(file: File) {
    setError(''); setUploading(true);
    try { await uploadDocument(projectId, role, file); setMessage('文件已上传，正在自动解析。解析完成后可查看原文。'); await refresh(); }
    catch (err) { setError(apiError(err, '上传失败')); }
    finally { setUploading(false); if (fileRef.current) fileRef.current.value = ''; }
  }
  const tenders = documents.data?.filter((doc) => ['tender', 'addendum', 'qa'].includes(doc.role)) ?? [];
  const parsedTenders = tenders.filter((doc) => doc.current_revision_id);
  const templates = documents.data?.filter((doc) => doc.role === 'template') ?? [];
  const activeRun = runs.data?.[0];
  const canAnalyze = parsedTenders.length > 0 && !tenders.some((doc) => !doc.current_revision_id) && runtime.data?.live_model_calls && !['draft', 'running'].includes(activeRun?.status ?? '');
  if (project.isLoading) return <EmptyState title="正在加载项目信息" loading />;
  if (project.isError) return <Alert severity="error">项目不存在或暂时无法加载。<Button component={Link} to="/">返回项目列表</Button></Alert>;

  return (
    <Stack spacing={3}>
      <PageHeader title={project.data?.name ?? '项目资料'} description={project.data?.tender_no ? `招标编号：${project.data.tender_no}` : '先上传招标文件，再补充投标信息和需要填写的内容。'} actions={<><Button variant="outlined" onClick={openInfo}>编辑项目信息</Button><Button component={Link} to={`/projects/${projectId}/evidence`} variant="outlined">证据资料</Button></>} />
      <WorkflowNav projectId={projectId} runId={activeRun?.id} active={0} />
      <Guidance step="当前建议" title={activeRun ? '已有分析结果，继续核对和填写' : !tenders.length ? '第一步：上传采购方发布的招标文件' : !parsedTenders.length ? '文件正在解析，请稍候' : '招标文件已就绪，补充信息后开始分析'} action={activeRun ? <NextButton to={`/runs/${activeRun.id}?tab=requirements`}>继续核对要求</NextButton> : !tenders.length ? <Button variant="contained" startIcon={<UploadFileOutlined />} disabled={uploading} onClick={() => { setRole('tender'); fileRef.current?.click(); }}>上传招标文件</Button> : <Button variant="outlined" onClick={openInfo}>补充投标信息</Button>}>
        {activeRun ? '先核对待确认要求，再到「填写建议」确认表格内容。已有结果可以直接打开。' : '招标文件用于提取要求；投标模板用于定位填写位置；证明材料用于支持核验结论。'}
      </Guidance>
      {message && <Alert severity="success" onClose={() => setMessage('')}>{message}</Alert>}
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      <Box><Grid container spacing={2.5}>
        <Grid item xs={12} md={8}>
          <Paper variant="outlined" id="files" className="section-anchor" sx={{ overflow: 'hidden' }}>
            <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={2} sx={{ p: 2.5, borderBottom: '1px solid', borderColor: 'divider' }}>
              <Box><Typography variant="h6">项目文件</Typography><Typography variant="caption" color="text.secondary">先选择用途，再上传文件。原页标注优先使用 PDF。</Typography></Box>
              <Stack direction="row" gap={1} alignItems="center"><TextField select label="文件用途" value={role} onChange={(event) => setRole(event.target.value)} sx={{ width: 130, flexShrink: 0 }}>{Object.entries(roleLabels).map(([key, label]) => <MenuItem key={key} value={key}>{label}</MenuItem>)}</TextField><Button variant="contained" disabled={uploading} startIcon={<UploadFileOutlined />} onClick={() => fileRef.current?.click()}>{uploading ? '上传中…' : '上传文件'}</Button></Stack>
              <input ref={fileRef} hidden type="file" aria-label="选择项目文件" accept=".pdf,.doc,.docx,.xlsx,.csv" onChange={(event) => { const file = event.target.files?.[0]; if (file) void handleUpload(file); }} />
            </Stack>
            <Stack divider={<Divider flexItem />}>
              {!documents.data?.length && <EmptyState title="还没有项目文件" description="请选择「招标文件」并上传采购文件，系统会自动解析页码、原文和表格。" />}
              {documents.data?.map((doc) => <Box key={doc.id} sx={{ px: 2.5, py: 2 }}>
                <Stack direction="row" justifyContent="space-between" gap={1}><Typography fontWeight={600} sx={{ overflowWrap: 'anywhere' }}>{doc.filename}</Typography><StatusChip status={doc.parse_status} label={doc.parse_status === 'completed' ? '解析完成' : doc.parse_status === 'needs_review' ? '含待复核页' : '解析中'} /></Stack>
                <Typography variant="caption" color="text.secondary">{roleLabels[doc.role]} · {doc.current_revision_id ? `${doc.page_count} 页` : '等待解析'} · {formatBytes(doc.file_size)}</Typography>
                <Stack direction="row" gap={0.5} sx={{ mt: 1 }}><Button size="small" disabled={!doc.current_revision_id} onClick={() => { setPreview(doc); setPreviewPage(''); }}>查看原文</Button><Button size="small" href={`/api/v2/documents/${doc.id}/file`}>下载</Button><Button size="small" color="inherit" onClick={() => { setEditingDoc(doc); setDocName(doc.filename); setDocRole(doc.role); setError(''); }}>编辑</Button><Button size="small" color="error" onClick={() => setDeleting({ path: `/documents/${doc.id}`, title: '从项目中移除文件？', description: `将移除「${doc.filename}」。被分析或证据引用的文件，需要先删除相关记录。` })}>删除</Button></Stack>
              </Box>)}
            </Stack>
          </Paper>
        </Grid>
        <Grid item xs={12} md={4}>
          <Stack spacing={2.5}>
            <Paper variant="outlined" sx={{ p: 2.5 }}><Typography variant="h6" sx={{ mb: 2 }}>准备进度</Typography><Stack spacing={1.3}><ReadyItem label={`招标文件：${parsedTenders.length ? `已解析 ${parsedTenders.reduce((sum, doc) => sum + doc.page_count, 0)} 页` : '待上传 / 解析'}`} ready={Boolean(parsedTenders.length)} /><ReadyItem label={`投标模板：${templates.length ? `${templates.length} 份` : '需要填写建议时上传'}`} ready={Boolean(templates.length)} /><ReadyItem label={`投标信息：${bids.data?.[0]?.bid_deadline || project.data?.bid_deadline ? '已设置截止日' : '待补充截止日'}`} ready={Boolean(bids.data?.[0]?.bid_deadline || project.data?.bid_deadline)} /><ReadyItem label={`填写资料：${values.data?.length ?? 0} 项`} ready={Boolean(values.data?.length)} /></Stack>
              <Divider sx={{ my: 2 }} />
              {runtime.data && !runtime.data.live_model_calls && <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>当前为离线模式，可准备资料和查看已有结果，真实模型分析保持关闭。</Typography>}
              <Button fullWidth variant={activeRun ? 'outlined' : 'contained'} disabled={!canAnalyze || analyze.isPending} onClick={() => analyze.mutate()}>{analyze.isPending ? '正在创建分析…' : activeRun ? '重新分析招标文件' : '开始分析招标文件'}</Button>
              {!parsedTenders.length && <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>上传并解析招标文件后，即可开始分析。</Typography>}
            </Paper>
            <Paper variant="outlined" sx={{ p: 2.5 }}><Stack direction="row" justifyContent="space-between" alignItems="center"><Typography variant="h6">投标信息</Typography><Button size="small" onClick={openInfo}>编辑</Button></Stack><Typography sx={{ mt: 1.5 }}>{bids.data?.[0]?.bidder_name || project.data?.bidder_name || '投标人待补充'}</Typography><Typography variant="body2" color="text.secondary">截止：{formatDate(bids.data?.[0]?.bid_deadline ?? project.data?.bid_deadline)}</Typography><Typography variant="caption" color="text.secondary">用于核验资质和证书是否在投标时有效。</Typography></Paper>
          </Stack>
        </Grid>
      </Grid></Box>
      <Paper variant="outlined" id="values" className="section-anchor" sx={{ p: 2.5 }}>
        <Stack direction="row" justifyContent="space-between" gap={2} alignItems="center"><Box><Typography variant="h6">填写资料</Typography><Typography variant="body2" color="text.secondary">预先录入已确定的内容，系统会按模板中的字段名称生成建议。已确认的手工结果会保留。</Typography></Box><Button variant="outlined" startIcon={<AddRounded />} onClick={() => openValue()}>新增资料</Button></Stack>
        <Stack direction="row" gap={0.75} flexWrap="wrap" sx={{ my: 2 }}><Typography variant="caption" color="text.secondary" sx={{ alignSelf: 'center', mr: 0.5 }}>快速添加</Typography>{presets.map((label) => <Chip key={label} label={`+ ${label}`} variant="outlined" onClick={() => openValue(null, label)} />)}</Stack>
        {!values.data?.length ? <Typography color="text.secondary" sx={{ p: 2, bgcolor: '#F9FAFB', borderRadius: 1 }}>还没有填写资料。点击上方常用字段，或自行新增模板中的字段。</Typography> : <Stack divider={<Divider flexItem />}>{values.data.map((value) => <Stack key={value.id} direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={1} sx={{ py: 1.5 }}><Box><Typography fontWeight={600}>{value.label}</Typography><Typography color="text.secondary" sx={{ overflowWrap: 'anywhere' }}>{value.value_text || value.value_number || value.value_date || '尚未填写'}</Typography></Box><Stack direction="row" alignItems="center"><Button size="small" onClick={() => openValue(value)}>编辑</Button><Button size="small" color="error" onClick={() => setDeleting({ path: `/response-values/${value.id}`, title: '删除填写资料？', description: `将删除「${value.label}」这条基础资料，已保存的填写建议仍可单独编辑。` })}>删除</Button></Stack></Stack>)}</Stack>}
      </Paper>
      <Paper variant="outlined" id="history" className="section-anchor" sx={{ overflow: 'hidden' }}>
        <Box sx={{ p: 2.5 }}><Typography variant="h6">分析记录</Typography><Typography variant="body2" color="text.secondary">查看历史结果，或取消尚未完成的分析任务。</Typography></Box>
        {!runs.data?.length ? <EmptyState title="尚未开始分析" description="完成资料准备并开始分析后，结果会显示在这里。" /> : <TableContainer><Table size="small" aria-label="分析记录" sx={{ minWidth: 600 }}><TableHead><TableRow><TableCell>开始时间</TableCell><TableCell>提取要求</TableCell><TableCell>状态</TableCell><TableCell align="right">操作</TableCell></TableRow></TableHead><TableBody>{runs.data.map((run) => {
          const job = jobs.data?.find((item) => item.payload?.run_id === run.id && ['queued', 'running'].includes(item.status));
          return <TableRow key={run.id}><TableCell>{formatDate(run.created_at)}</TableCell><TableCell>{run.requirement_count} 条</TableCell><TableCell><StatusChip status={run.status} /></TableCell><TableCell align="right"><Button size="small" component={Link} to={`/runs/${run.id}`}>查看结果</Button>{job ? <Button size="small" color="error" disabled={cancel.isPending} onClick={() => cancel.mutate(job.id)}>取消任务</Button> : <Button size="small" color="error" onClick={() => setDeleting({ path: `/analysis-runs/${run.id}`, title: '删除本次分析？', description: '将删除本次要求核对、复核记录、填写建议和检查清单，项目原文件仍然保留。' })}>删除</Button>}</TableCell></TableRow>;
        })}</TableBody></Table></TableContainer>}
        {jobs.data?.some((job) => ['queued', 'running'].includes(job.status)) && <Box sx={{ p: 2.5 }}>{jobs.data.filter((job) => ['queued', 'running'].includes(job.status)).map((job) => <Box key={job.id} sx={{ mb: 1.5 }}><Stack direction="row" justifyContent="space-between"><Typography variant="caption">{job.kind === 'parse_document' ? '文件解析' : '要求分析'} · {job.stage}</Typography><Typography variant="caption">{job.progress}%</Typography></Stack><LinearProgress variant="determinate" value={job.progress} sx={{ mt: 1, height: 5, borderRadius: 1 }} /></Box>)}</Box>}
      </Paper>
      {activeRun && <Stack direction="row" justifyContent="flex-end"><NextButton to={`/runs/${activeRun.id}?tab=requirements`}>下一步：核对要求</NextButton></Stack>}
      <Dialog open={infoOpen} onClose={() => setInfoOpen(false)} fullWidth maxWidth="sm"><DialogTitle>编辑项目信息</DialogTitle><DialogContent><Stack spacing={2.5} sx={{ pt: 1 }}>{error && <Alert severity="error">{error}</Alert>}<TextField required label="项目名称" value={projectName} onChange={(event) => setProjectName(event.target.value)} /><TextField label="招标编号（选填）" value={tenderNo} onChange={(event) => setTenderNo(event.target.value)} /><TextField label="投标人名称" value={bidderName} onChange={(event) => setBidderName(event.target.value)} /><TextField label="投标截止时间" type="datetime-local" value={bidDeadline} onChange={(event) => setBidDeadline(event.target.value)} InputLabelProps={{ shrink: true }} helperText="用于核验投标时的证书有效期；请填写招标文件规定的截止时间。" /></Stack></DialogContent><DialogActions><Button onClick={() => setInfoOpen(false)}>取消</Button><Button variant="contained" disabled={!projectName.trim() || saveInfo.isPending} onClick={() => saveInfo.mutate()}>保存修改</Button></DialogActions></Dialog>
      <Dialog open={valueOpen} onClose={() => setValueOpen(false)} fullWidth maxWidth="sm"><DialogTitle>{editingValue ? '编辑填写资料' : '新增填写资料'}</DialogTitle><DialogContent><Stack spacing={2.5} sx={{ pt: 1 }}><Typography color="text.secondary">填写已确定的真实内容，供模板填写建议使用。</Typography>{error && <Alert severity="error">{error}</Alert>}<TextField required label="模板字段名称" placeholder="例如：投标人名称、设备名称、交货期" value={valueLabel} onChange={(event) => setValueLabel(event.target.value)} helperText="与模板中的字段名称保持一致，便于自动匹配。" /><TextField required label="准备填写的内容" multiline minRows={3} value={valueText} onChange={(event) => setValueText(event.target.value)} /></Stack></DialogContent><DialogActions><Button onClick={() => setValueOpen(false)}>取消</Button><Button variant="contained" disabled={!valueLabel.trim() || !valueText.trim() || saveValue.isPending} onClick={() => saveValue.mutate()}>保存资料</Button></DialogActions></Dialog>
      <Dialog open={Boolean(editingDoc)} onClose={() => setEditingDoc(null)} fullWidth maxWidth="sm"><DialogTitle>编辑文件信息</DialogTitle><DialogContent><Stack spacing={2.5} sx={{ pt: 1 }}>{error && <Alert severity="error">{error}</Alert>}<TextField label="文件名称" required value={docName} onChange={(event) => setDocName(event.target.value)} /><TextField label="文件用途" select value={docRole} onChange={(event) => setDocRole(event.target.value)} helperText="修改用途后，已有分析可能需要重新核验。">{Object.entries(roleLabels).map(([key, label]) => <MenuItem key={key} value={key}>{label}</MenuItem>)}</TextField></Stack></DialogContent><DialogActions><Button onClick={() => setEditingDoc(null)}>取消</Button><Button variant="contained" disabled={!docName.trim() || saveDoc.isPending} onClick={() => saveDoc.mutate()}>保存修改</Button></DialogActions></Dialog>
      <Dialog open={Boolean(preview)} onClose={() => setPreview(null)} fullWidth maxWidth="md"><DialogTitle>{preview?.filename}</DialogTitle><DialogContent><Stack spacing={2}>{previewPages.isLoading ? <EmptyState title="正在加载原文" loading /> : page ? <><TextField select label="页码" value={page.id} onChange={(event) => setPreviewPage(event.target.value)}>{previewPages.data?.map((item) => <MenuItem key={item.id} value={item.id}>第 {item.page_index + 1} 页{item.printed_label ? ` · ${item.printed_label}` : ''}</MenuItem>)}</TextField><PageViewer page={page} /></> : <EmptyState title="原文尚未就绪" description="请等待解析完成后重新查看。" />}</Stack></DialogContent><DialogActions><Button href={`/api/v2/documents/${preview?.id}/file`}>下载原文件</Button><Button onClick={() => setPreview(null)}>关闭</Button></DialogActions></Dialog>
      <ConfirmDialog open={Boolean(deleting)} title={deleting?.title ?? ''} description={deleting?.description ?? ''} pending={remove.isPending} onClose={() => setDeleting(null)} onConfirm={() => remove.mutate()} />
    </Stack>
  );
}
