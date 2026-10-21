import { useEffect, useRef, useState } from 'react';
import {
  Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Divider,
  Autocomplete, FormControlLabel, IconButton, LinearProgress, Menu, MenuItem, Paper, Stack, Switch, Tab, Tabs, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import UploadFileOutlined from '@mui/icons-material/UploadFileOutlined';
import AddRounded from '@mui/icons-material/AddRounded';
import MoreHorizRounded from '@mui/icons-material/MoreHorizRounded';
import EditOutlined from '@mui/icons-material/EditOutlined';
import DeleteOutlineRounded from '@mui/icons-material/DeleteOutlineRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { api, apiError, uploadDocument, type AnalysisRun, type Bid, type DocumentItem, type Job, type Organization, type PageItem, type Project, type ResponseValue } from '../lib/api';
import { formatBytes, formatDate, dateTimeInput } from '../lib/format';
import { documentStatus, roleLabels } from '../lib/labels';
import { ConfirmDialog, EmptyState, Notice, PageHeader, StatusChip } from '../components/Workspace';
import PageViewer from '../components/PageViewer';

const presets = ['投标人名称', '联系人', '联系电话', '设备名称', '规格型号', '数量', '交货期'];

export default function ProjectPage() {
  const { projectId = '' } = useParams();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const fileRef = useRef<HTMLInputElement>(null);
  const [role, setRole] = useState(new URLSearchParams(location.search).get('upload') === 'evidence' ? 'tender' : new URLSearchParams(location.search).get('upload') || 'tender');
  const [uploading, setUploading] = useState(false);
  const [fileMenu, setFileMenu] = useState<{ anchor: HTMLElement; document: DocumentItem } | null>(null);
  const [actionMenu, setActionMenu] = useState<HTMLElement | null>(null);
  const section = location.hash === '#history' ? 'history' : location.hash === '#values' ? 'values' : location.hash === '#library' ? 'library' : 'files';
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [infoOpen, setInfoOpen] = useState(false);
  const [projectName, setProjectName] = useState('');
  const [tenderNo, setTenderNo] = useState('');
  const [bidderName, setBidderName] = useState('');
  const [bidDeadline, setBidDeadline] = useState('');
  const [organizationId, setOrganizationId] = useState('');
  const [autoAnalyze, setAutoAnalyze] = useState(true);
  const [valueOpen, setValueOpen] = useState(false);
  const [editingValue, setEditingValue] = useState<ResponseValue | null>(null);
  const [valueLabel, setValueLabel] = useState('');
  const [valueText, setValueText] = useState('');
  const [editingDoc, setEditingDoc] = useState<DocumentItem | null>(null);
  const [docName, setDocName] = useState('');
  const [docRole, setDocRole] = useState('');
  const [preview, setPreview] = useState<DocumentItem | null>(null);
  const [previewPage, setPreviewPage] = useState('');
  const [textOpen, setTextOpen] = useState(false);
  const [pageText, setPageText] = useState('');
  const [deleting, setDeleting] = useState<{ path: string; title: string; description: string } | null>(null);
  const project = useQuery({ queryKey: ['project', projectId], queryFn: async () => (await api.get<Project>(`/projects/${projectId}`)).data });
  const runtime = useQuery({ queryKey: ['runtime'], queryFn: async () => (await api.get<{ live_model_calls: boolean }>('/health')).data });
  const documents = useQuery({ queryKey: ['documents', projectId], queryFn: async () => (await api.get<DocumentItem[]>(`/projects/${projectId}/documents`)).data, refetchInterval: 2500 });
  const organizations = useQuery({ queryKey: ['organizations'], queryFn: async () => (await api.get<Organization[]>('/organizations')).data });
  const libraryDocuments = useQuery({ queryKey: ['project-library', projectId], queryFn: async () => (await api.get<DocumentItem[]>(`/projects/${projectId}/library-documents`)).data, refetchInterval: 2500 });
  const runs = useQuery({ queryKey: ['runs', projectId], queryFn: async () => (await api.get<AnalysisRun[]>(`/projects/${projectId}/analysis-runs`)).data, refetchInterval: 2500 });
  const jobs = useQuery({ queryKey: ['jobs', projectId], queryFn: async () => (await api.get<Job[]>(`/projects/${projectId}/jobs`)).data, refetchInterval: 1500 });
  const bids = useQuery({ queryKey: ['bids', projectId], queryFn: async () => (await api.get<Bid[]>(`/projects/${projectId}/bids`)).data });
  const values = useQuery({ queryKey: ['response-values', projectId], queryFn: async () => (await api.get<ResponseValue[]>(`/projects/${projectId}/response-values`)).data });
  const previewPages = useQuery({ queryKey: ['document-pages', preview?.id], enabled: Boolean(preview?.id), queryFn: async () => (await api.get<PageItem[]>(`/documents/${preview!.id}/pages`)).data });
  const page = previewPages.data?.find((item) => item.id === previewPage) ?? previewPages.data?.[0];
  const refresh = async () => {
    await Promise.all(['project', 'projects', 'documents', 'runs', 'jobs', 'bids', 'response-values', 'fill-documents', 'fill-plan', 'project-library', 'evidence'].map((key) => queryClient.invalidateQueries({ queryKey: key === 'projects' || key === 'fill-plan' ? [key] : [key, projectId] })));
  };
  useEffect(() => {
    const uploadRole = new URLSearchParams(location.search).get('upload');
    if (uploadRole && uploadRole !== 'evidence') setRole(uploadRole);
  }, [location.search]);
  const analyze = useMutation({
    mutationFn: async (mode: 'model' | 'manual') => (await api.post<AnalysisRun>(`/projects/${projectId}/analysis-runs`, { mode })).data,
    onSuccess: async (run) => { await refresh(); navigate(`/runs/${run.id}`); },
    onError: (err) => setError(apiError(err, '创建分析任务失败')),
  });
  const reparse = useMutation({
    mutationFn: async (doc: DocumentItem) => api.post(`/documents/${doc.id}/reparse`),
    onSuccess: async () => { setMessage('已重新加入解析队列'); await refresh(); },
    onError: (err) => setError(apiError(err, '重新解析失败')),
  });
  const reprocess = useMutation({
    mutationFn: async (doc: DocumentItem) => api.post(`/documents/${doc.id}/process`),
    onSuccess: async () => { setMessage('已继续 AI 处理，完成后自动对标'); await refresh(); },
    onError: (err) => setError(apiError(err, '提交 AI 处理失败')),
  });
  const correctText = useMutation({
    mutationFn: async () => api.put(`/pages/${page!.id}/text`, { text: pageText }),
    onSuccess: async () => {
      setTextOpen(false); setMessage('本页文字已人工校正；已有结论已标记待重新核对');
      await queryClient.invalidateQueries({ queryKey: ['document-pages', preview?.id] });
      await queryClient.invalidateQueries({ queryKey: ['source-spans', page?.id] });
      await refresh();
    },
    onError: (err) => setError(apiError(err, '保存人工校正失败')),
  });
  const saveInfo = useMutation({
    mutationFn: async () => {
      const deadline = bidDeadline ? new Date(bidDeadline).toISOString() : null;
      const payload = { bidder_name: bidderName.trim() || '投标人', bid_deadline: deadline, as_of_date: bidDeadline ? bidDeadline.slice(0, 10) : null };
      if (bids.data?.[0]) await api.patch(`/bids/${bids.data[0].id}`, payload);
      else await api.post(`/projects/${projectId}/bids`, payload);
      await api.patch(`/projects/${projectId}`, { name: projectName.trim(), tender_no: tenderNo.trim() || null, bidder_name: bidderName.trim() || null, bid_deadline: deadline, organization_id: organizationId || null, auto_analyze: autoAnalyze });
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
  const share = useMutation({
    mutationFn: async (doc: DocumentItem) => api.post(`/documents/${doc.id}/share`, null, { params: { organization_id: project.data?.organization_id } }),
    onSuccess: async () => { setMessage('材料已归入企业资料库，可跨项目复用'); await refresh(); },
    onError: (err) => setError(apiError(err, '移入企业资料库失败')),
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
    setOrganizationId(project.data?.organization_id ?? '');
    setAutoAnalyze(project.data?.auto_analyze ?? true);
    setBidDeadline(dateTimeInput(bids.data?.[0]?.bid_deadline ?? project.data?.bid_deadline)); setInfoOpen(true);
  }
  function openValue(value: ResponseValue | null = null, label = '') {
    setError(''); setEditingValue(value); setValueLabel(value?.label ?? label); setValueText(value?.value_text ?? ''); setValueOpen(true);
  }
  async function handleUpload(file: File) {
    setError(''); setUploading(true);
    try { await uploadDocument(projectId, role, file); setMessage(runtime.data?.live_model_calls ? '文件已上传，处理完成后将自动对标' : '文件已上传，自动解析后等待启用 AI'); await refresh(); }
    catch (err) { setError(apiError(err, '上传失败')); }
    finally { setUploading(false); if (fileRef.current) fileRef.current.value = ''; }
  }
  const tenders = documents.data?.filter((doc) => ['tender', 'addendum', 'qa'].includes(doc.role)) ?? [];
  const parsedTenders = tenders.filter((doc) => doc.current_revision_id);
  const activeRun = runs.data?.[0];
  const organization = organizations.data?.find((item) => item.id === project.data?.organization_id);
  const allDocuments = [...(documents.data ?? []), ...(libraryDocuments.data ?? [])];
  const materialsReady = parsedTenders.length > 0 && !tenders.some((doc) => !doc.current_revision_id || ['queued', 'running', 'failed'].includes(doc.parse_status));
  const aiReady = allDocuments.every((doc) => ['ready', 'needs_review'].includes(doc.ai_status));
  const canAnalyze = materialsReady && aiReady && runtime.data?.live_model_calls && !['draft', 'running'].includes(activeRun?.status ?? '');
  if (project.isLoading) return <EmptyState title="正在加载项目信息" loading />;
  if (project.isError) return <Alert severity="error">项目不存在或暂时无法加载。<Button component={Link} to="/">返回项目列表</Button></Alert>;

  return (
    <Stack spacing={2}>
      <PageHeader title={project.data?.name ?? '项目资料'} actions={<>
        <Button color="inherit" onClick={openInfo}>项目信息</Button>
        {activeRun
          ? <Button variant="contained" component={Link} to={`/runs/${activeRun.id}?tab=requirements`}>进入工作台</Button>
          : <Button variant="contained" disabled={!canAnalyze || analyze.isPending} onClick={() => analyze.mutate('model')}>{runtime.data?.live_model_calls ? '立即对标' : 'AI 待启用'}</Button>}
        <IconButton aria-label="更多项目操作" onClick={(event) => setActionMenu(event.currentTarget)}><MoreHorizRounded /></IconButton>
      </>} />
      <Notice message={message} onClose={() => setMessage('')} />
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} gap={1} alignItems={{ xs: 'flex-start', sm: 'center' }} sx={{ px: 2, py: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
          <Button color="inherit" size="small" onClick={openInfo}>{organization?.name ?? '选择投标企业'}</Button>
          <Typography variant="caption" color="text.secondary" sx={{ flex: 1 }}>{!project.data?.organization_id ? '关联企业后复用资料库' : !runtime.data?.live_model_calls ? '开发阶段 · 解析后等待启用 AI' : !project.data?.auto_analyze ? '自动对标已暂停' : !materialsReady ? '上传招标文件后自动处理' : !aiReady ? '资料正在入库，完成后自动对标' : activeRun ? '资料更新后自动重新对标' : '资料已就绪，等待自动对标'}</Typography>
          {project.data?.organization_id && <Button size="small" component={Link} to={`/library?organization=${project.data.organization_id}`}>管理企业材料</Button>}
        </Stack>
        <Stack direction={{ xs: 'column', sm: 'row' }} alignItems={{ sm: 'center' }} justifyContent="space-between" gap={1} sx={{ px: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
          <Tabs value={section} onChange={(_, value) => navigate(`/projects/${projectId}#${value}`)} aria-label="项目资料分类" variant="scrollable" scrollButtons={false}>
            <Tab value="files" label={`文件 ${documents.data?.length ?? 0}`} />
            <Tab value="library" label={`企业材料 ${libraryDocuments.data?.length ?? 0}`} />
            <Tab value="values" label={`填写资料 ${values.data?.length ?? 0}`} />
            <Tab value="history" label={`分析记录 ${runs.data?.length ?? 0}`} />
          </Tabs>
          <Stack direction="row" gap={1} alignItems="center" sx={{ py: 1, flexShrink: 0 }}>
            {section === 'files' && <><TextField select label="文件用途" value={role} onChange={(event) => setRole(event.target.value)} sx={{ width: 130 }}>{Object.entries(roleLabels).filter(([key]) => key !== 'evidence').map(([key, label]) => <MenuItem key={key} value={key}>{label}</MenuItem>)}</TextField><Button variant="contained" disabled={uploading} startIcon={<UploadFileOutlined />} onClick={() => fileRef.current?.click()}>{uploading ? '上传中…' : '上传文件'}</Button></>}
            {section === 'values' && <Button startIcon={<AddRounded />} onClick={() => openValue()}>新增资料</Button>}
          </Stack>
        </Stack>
        <input ref={fileRef} hidden type="file" aria-label="选择项目文件" accept=".pdf,.doc,.docx,.xlsx,.csv" onChange={(event) => { const file = event.target.files?.[0]; if (file) void handleUpload(file); }} />
        {section === 'files' && <>
          {documents.isLoading ? <EmptyState title="正在加载文件" loading /> : !documents.data?.length ? <EmptyState title="上传第一份招标文件" action={<Button variant="outlined" onClick={() => { setRole('tender'); fileRef.current?.click(); }}>选择文件</Button>} /> : <TableContainer><Table aria-label="项目文件"><TableHead><TableRow><TableCell>文件</TableCell><TableCell sx={{ display: { xs: 'none', md: 'table-cell' } }}>用途</TableCell><TableCell>状态</TableCell><TableCell align="right" sx={{ width: 52 }} /></TableRow></TableHead><TableBody>{documents.data.map((doc) => <TableRow key={doc.id} hover>
            <TableCell sx={{ minWidth: 0, maxWidth: 480 }}><Button disabled={!doc.current_revision_id} color="inherit" onClick={() => { setPreview(doc); setPreviewPage(''); }} sx={{ p: 0, minHeight: 0, justifyContent: 'flex-start', whiteSpace: 'normal', overflowWrap: 'anywhere', textAlign: 'left', fontWeight: 600 }}>{doc.filename}</Button><Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>{doc.current_revision_id ? `${doc.page_count} 页 · ` : ''}{formatBytes(doc.file_size)}<Box component="span" sx={{ display: { md: 'none' } }}> · {roleLabels[doc.role]}</Box></Typography>{doc.parse_error && <Typography variant="caption" color="error.main" display="block" sx={{ mt: 0.5 }}>{doc.parse_error}</Typography>}</TableCell>
            <TableCell sx={{ display: { xs: 'none', md: 'table-cell' }, whiteSpace: 'nowrap' }}>{roleLabels[doc.role]}</TableCell>
            <TableCell sx={{ whiteSpace: 'nowrap' }}><StatusChip status={documentStatus(doc)} />{doc.ai_error && <Typography variant="caption" color="error" display="block" sx={{ maxWidth: 260, whiteSpace: 'normal' }}>{doc.ai_error}</Typography>}</TableCell>
            <TableCell align="right"><IconButton size="small" aria-label={`操作文件 ${doc.filename}`} onClick={(event) => setFileMenu({ anchor: event.currentTarget, document: doc })}><MoreHorizRounded /></IconButton></TableCell>
          </TableRow>)}</TableBody></Table></TableContainer>}
        </>}
        {section === 'library' && (libraryDocuments.isLoading ? <EmptyState loading title="正在加载企业材料" /> : libraryDocuments.error ? <Alert severity="error" sx={{ m: 2 }}>企业材料加载失败。</Alert> : !libraryDocuments.data?.length ? <EmptyState title={organization ? '企业资料库暂无材料' : '先关联投标企业'} action={organization ? <Button component={Link} to={`/library?organization=${organization.id}`}>上传企业材料</Button> : <Button onClick={openInfo}>选择企业</Button>} /> : <TableContainer><Table sx={{ minWidth: 500 }} aria-label="复用的企业材料"><TableHead><TableRow><TableCell>材料</TableCell><TableCell>状态</TableCell><TableCell>事实</TableCell><TableCell align="right">操作</TableCell></TableRow></TableHead><TableBody>{libraryDocuments.data.map((doc) => <TableRow key={doc.id} hover><TableCell>{doc.filename}<Typography variant="caption" display="block" color="text.secondary">{doc.page_count} 页 · 企业共享</Typography></TableCell><TableCell><StatusChip status={documentStatus(doc)} /></TableCell><TableCell>{doc.evidence_count}</TableCell><TableCell align="right"><Button size="small" disabled={!doc.current_revision_id} onClick={() => { setPreview(doc); setPreviewPage(''); }}>原文</Button></TableCell></TableRow>)}</TableBody></Table></TableContainer>)}
        {section === 'values' && <>
          {!values.data?.length ? <EmptyState title="添加准备填写的内容" action={<Button variant="outlined" onClick={() => openValue()}>新增资料</Button>} /> : <TableContainer><Table aria-label="填写资料"><TableHead><TableRow><TableCell>字段</TableCell><TableCell>内容</TableCell><TableCell align="right" sx={{ width: 90 }} /></TableRow></TableHead><TableBody>{values.data.map((value) => <TableRow key={value.id} hover><TableCell sx={{ width: '25%' }}>{value.label}</TableCell><TableCell sx={{ overflowWrap: 'anywhere' }}>{value.value_text ?? value.value_number ?? value.value_date ?? '未填写'}</TableCell><TableCell align="right" sx={{ whiteSpace: 'nowrap' }}><IconButton size="small" aria-label={`编辑 ${value.label}`} onClick={() => openValue(value)}><EditOutlined fontSize="small" /></IconButton><IconButton size="small" aria-label={`删除 ${value.label}`} onClick={() => setDeleting({ path: `/response-values/${value.id}`, title: '删除填写资料？', description: `将删除「${value.label}」，已保存的填写建议仍可单独编辑。` })}><DeleteOutlineRounded fontSize="small" /></IconButton></TableCell></TableRow>)}</TableBody></Table></TableContainer>}
        </>}
        {section === 'history' && <>
          {!runs.data?.length ? <EmptyState title="暂无分析记录" /> : <TableContainer><Table aria-label="分析记录"><TableHead><TableRow><TableCell>时间</TableCell><TableCell>要求</TableCell><TableCell>状态</TableCell><TableCell align="right">操作</TableCell></TableRow></TableHead><TableBody>{runs.data.map((run) => {
            const job = jobs.data?.find((item) => item.payload?.run_id === run.id && ['queued', 'running'].includes(item.status));
            return <TableRow key={run.id} hover><TableCell>{formatDate(run.created_at)}<Typography variant="caption" color="text.secondary" display="block">{run.model_snapshot.execution_mode === 'manual' ? '人工核对' : '模型分析'}</Typography></TableCell><TableCell>{run.requirement_count}</TableCell><TableCell><StatusChip status={run.status} /></TableCell><TableCell align="right" sx={{ whiteSpace: 'nowrap' }}><Button size="small" component={Link} to={`/runs/${run.id}`}>打开</Button>{job ? <Button size="small" disabled={cancel.isPending} onClick={() => cancel.mutate(job.id)}>取消</Button> : <IconButton size="small" aria-label="删除分析记录" onClick={() => setDeleting({ path: `/analysis-runs/${run.id}`, title: '删除本次分析？', description: '将删除本次要求、复核记录、填写建议和检查清单，原文件保留。' })}><DeleteOutlineRounded fontSize="small" /></IconButton>}</TableCell></TableRow>;
          })}</TableBody></Table></TableContainer>}
        </>}
        {jobs.data?.filter((job) => ['queued', 'running'].includes(job.status)).map((job) => <Box key={job.id} sx={{ px: 2, py: 1.5, borderTop: '1px solid', borderColor: 'divider' }}><Stack direction="row" justifyContent="space-between"><Typography variant="caption">{job.stage}</Typography><Typography variant="caption">{job.progress}%</Typography></Stack><LinearProgress variant="determinate" value={job.progress} sx={{ mt: 0.75 }} /></Box>)}
      </Paper>
      <Menu anchorEl={actionMenu} open={Boolean(actionMenu)} onClose={() => setActionMenu(null)}>
        <MenuItem disabled={!materialsReady || analyze.isPending} onClick={() => { setActionMenu(null); analyze.mutate('manual'); }}>新建人工工作台</MenuItem>
        <MenuItem disabled={!canAnalyze || analyze.isPending} onClick={() => { setActionMenu(null); analyze.mutate('model'); }}>重新自动对标{!runtime.data?.live_model_calls ? '（AI 暂停）' : ''}</MenuItem>
        <MenuItem component={Link} to={`/projects/${projectId}/evidence`}>证据资料</MenuItem>
      </Menu>
      <Menu anchorEl={fileMenu?.anchor} open={Boolean(fileMenu)} onClose={() => setFileMenu(null)}>
        <MenuItem disabled={!fileMenu?.document.current_revision_id} onClick={() => { setPreview(fileMenu!.document); setPreviewPage(''); setFileMenu(null); }}>预览原文</MenuItem>
        <MenuItem component="a" href={`/api/v2/documents/${fileMenu?.document.id}/file`} onClick={() => setFileMenu(null)}>下载原文件</MenuItem>
        <MenuItem onClick={() => { const doc = fileMenu!.document; setEditingDoc(doc); setDocName(doc.filename); setDocRole(doc.role); setError(''); setFileMenu(null); }}>编辑文件信息</MenuItem>
        <MenuItem disabled={reparse.isPending || ['queued', 'running'].includes(fileMenu?.document.parse_status ?? '')} onClick={() => { reparse.mutate(fileMenu!.document); setFileMenu(null); }}>重新解析</MenuItem>
        <MenuItem disabled={!runtime.data?.live_model_calls || !fileMenu?.document.current_revision_id || ['queued', 'running'].includes(fileMenu?.document.ai_status ?? '') || reprocess.isPending} onClick={() => { reprocess.mutate(fileMenu!.document); setFileMenu(null); }}>继续 AI 处理</MenuItem>
        {fileMenu?.document.role === 'evidence' && <MenuItem disabled={!project.data?.organization_id || share.isPending} onClick={() => { share.mutate(fileMenu!.document); setFileMenu(null); }}>移入企业资料库</MenuItem>}
        <Divider />
        <MenuItem sx={{ color: 'error.main' }} onClick={() => { const doc = fileMenu!.document; setDeleting({ path: `/documents/${doc.id}`, title: '移除文件？', description: `将移除「${doc.filename}」。被引用的文件需先处理关联记录。` }); setFileMenu(null); }}>删除</MenuItem>
      </Menu>
      <Dialog open={infoOpen} onClose={() => setInfoOpen(false)} fullWidth maxWidth="sm"><DialogTitle>编辑项目信息</DialogTitle><DialogContent><Stack spacing={2.5} sx={{ pt: 1 }}>{error && <Alert severity="error">{error}</Alert>}<TextField required label="项目名称" value={projectName} onChange={(event) => setProjectName(event.target.value)} /><TextField label="招标编号（选填）" value={tenderNo} onChange={(event) => setTenderNo(event.target.value)} /><TextField select label="投标企业" value={organizationId} onChange={(event) => { setOrganizationId(event.target.value); const item = organizations.data?.find((entry) => entry.id === event.target.value); if (item && !bidderName) setBidderName(item.name); }} helperText="自动复用该企业的全部已入库材料。"><MenuItem value="">暂不关联</MenuItem>{organizations.data?.map((item) => <MenuItem key={item.id} value={item.id}>{item.name}</MenuItem>)}</TextField><TextField label="投标人名称" value={bidderName} onChange={(event) => setBidderName(event.target.value)} /><FormControlLabel control={<Switch checked={autoAnalyze} onChange={(_, checked) => setAutoAnalyze(checked)} />} label="资料齐备后自动对标并生成填写建议" /><TextField label="投标截止时间" type="datetime-local" value={bidDeadline} onChange={(event) => setBidDeadline(event.target.value)} InputLabelProps={{ shrink: true }} helperText="用于核验投标时的证书有效期；请填写招标文件规定的截止时间。" /></Stack></DialogContent><DialogActions><Button onClick={() => setInfoOpen(false)}>取消</Button><Button variant="contained" disabled={!projectName.trim() || saveInfo.isPending} onClick={() => saveInfo.mutate()}>保存修改</Button></DialogActions></Dialog>
      <Dialog open={valueOpen} onClose={() => setValueOpen(false)} fullWidth maxWidth="sm"><DialogTitle>{editingValue ? '编辑填写资料' : '新增填写资料'}</DialogTitle><DialogContent><Stack spacing={2.5} sx={{ pt: 1 }}>{error && <Alert severity="error">{error}</Alert>}<Autocomplete freeSolo options={presets} inputValue={valueLabel} onInputChange={(_, value) => setValueLabel(value)} renderInput={(params) => <TextField {...params} required label="字段名称" />} /><TextField required label="准备填写的内容" multiline minRows={3} value={valueText} onChange={(event) => setValueText(event.target.value)} /></Stack></DialogContent><DialogActions><Button onClick={() => setValueOpen(false)}>取消</Button><Button variant="contained" disabled={!valueLabel.trim() || !valueText.trim() || saveValue.isPending} onClick={() => saveValue.mutate()}>保存资料</Button></DialogActions></Dialog>
      <Dialog open={Boolean(editingDoc)} onClose={() => setEditingDoc(null)} fullWidth maxWidth="sm"><DialogTitle>编辑文件信息</DialogTitle><DialogContent><Stack spacing={2.5} sx={{ pt: 1 }}>{error && <Alert severity="error">{error}</Alert>}<TextField label="文件名称" required value={docName} onChange={(event) => setDocName(event.target.value)} /><TextField label="文件用途" select value={docRole} onChange={(event) => setDocRole(event.target.value)} helperText="修改用途后，已有分析可能需要重新核验。">{Object.entries(roleLabels).map(([key, label]) => <MenuItem key={key} value={key}>{label}</MenuItem>)}</TextField></Stack></DialogContent><DialogActions><Button onClick={() => setEditingDoc(null)}>取消</Button><Button variant="contained" disabled={!docName.trim() || saveDoc.isPending} onClick={() => saveDoc.mutate()}>保存修改</Button></DialogActions></Dialog>
      <Dialog open={Boolean(preview)} onClose={() => setPreview(null)} fullWidth maxWidth="md"><DialogTitle>{preview?.filename}</DialogTitle><DialogContent><Stack spacing={2} sx={{ pt: 1 }}>{previewPages.isLoading ? <EmptyState title="正在加载原文" loading /> : page ? <><TextField select label="页码" value={page.id} onChange={(event) => setPreviewPage(event.target.value)}>{previewPages.data?.map((item) => <MenuItem key={item.id} value={item.id}>第 {item.page_index + 1} 页{item.printed_label ? ` · ${item.printed_label}` : ''}</MenuItem>)}</TextField><PageViewer page={page} showLabel={false} /></> : <EmptyState title="原文尚未就绪" description="请等待解析完成后重新查看。" />}</Stack></DialogContent><DialogActions>{page && !page.quality_flags.some((flag) => ['no_page_coordinates', 'spreadsheet_coordinates'].includes(flag)) && <Button onClick={() => { setPageText(page.text); setError(''); setTextOpen(true); }}>人工校正本页文字</Button>}<Button href={`/api/v2/documents/${preview?.id}/file`}>下载原文件</Button><Button onClick={() => setPreview(null)}>关闭</Button></DialogActions></Dialog>
      <Dialog open={textOpen} onClose={() => setTextOpen(false)} fullWidth maxWidth="md"><DialogTitle>人工校正 · 第 {(page?.page_index ?? 0) + 1} 页</DialogTitle><DialogContent><Stack spacing={2} sx={{ pt: 1 }}><Alert severity="info">请对照原页输入完整、真实的文字。保存后可用作要求或证据的来源；文字只定位到整页，精确填写位置请在模板中手工框选。</Alert>{error && <Alert severity="error">{error}</Alert>}<TextField label="已核实的本页文字" multiline minRows={12} value={pageText} onChange={(event) => setPageText(event.target.value)} /></Stack></DialogContent><DialogActions><Button onClick={() => setTextOpen(false)}>取消</Button><Button variant="contained" disabled={!pageText.trim() || correctText.isPending} onClick={() => correctText.mutate()}>保存人工校正</Button></DialogActions></Dialog>
      <ConfirmDialog open={Boolean(deleting)} title={deleting?.title ?? ''} description={deleting?.description ?? ''} pending={remove.isPending} onClose={() => setDeleting(null)} onConfirm={() => remove.mutate()} />
    </Stack>
  );
}
