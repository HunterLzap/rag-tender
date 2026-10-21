import { useRef, useState } from 'react';
import {
  Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Divider,
  IconButton, LinearProgress, Menu, MenuItem, Paper, Stack, Tab, Tabs, Table,
  TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import AddRounded from '@mui/icons-material/AddRounded';
import MoreHorizRounded from '@mui/icons-material/MoreHorizRounded';
import UploadFileOutlined from '@mui/icons-material/UploadFileOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import { ConfirmDialog, EmptyState, Notice, PageHeader, StatusChip } from '../components/Workspace';
import PageViewer from '../components/PageViewer';
import {
  api, apiError, type DocumentItem, type Evidence, type EvidenceFact, type Job,
  type Organization, type PageItem, type SourceSpan,
} from '../lib/api';
import { formatBytes } from '../lib/format';
import { categoryLabels, documentStatus, factLabels } from '../lib/labels';

const companyFields = [
  ['address', '企业地址'], ['contact', '联系人'], ['phone', '联系电话'],
  ['bank_name', '开户银行'], ['bank_account', '银行账号'],
];

export default function LibraryPage() {
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const fileRef = useRef<HTMLInputElement>(null);
  const [search, setSearch] = useState('');
  const [uploading, setUploading] = useState(false);
  const [companyOpen, setCompanyOpen] = useState(false);
  const [editingCompany, setEditingCompany] = useState<Organization | null>(null);
  const [companyName, setCompanyName] = useState('');
  const [companyCode, setCompanyCode] = useState('');
  const [companyData, setCompanyData] = useState<Record<string, string>>({});
  const [docMenu, setDocMenu] = useState<{ anchor: HTMLElement; item: DocumentItem } | null>(null);
  const [renaming, setRenaming] = useState<DocumentItem | null>(null);
  const [filename, setFilename] = useState('');
  const [detailsId, setDetailsId] = useState('');
  const [editingFact, setEditingFact] = useState<EvidenceFact | null>(null);
  const [evidenceEdit, setEvidenceEdit] = useState<{ id: string; title: string; holder: string; identifier: string } | null>(null);
  const [factValue, setFactValue] = useState('');
  const [factUnit, setFactUnit] = useState('');
  const [preview, setPreview] = useState<{ documentId: string; title: string; span?: SourceSpan } | null>(null);
  const [previewPageId, setPreviewPageId] = useState('');
  const [deleting, setDeleting] = useState<{ path: string; title: string; detail: string } | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const organizations = useQuery({
    queryKey: ['organizations'],
    queryFn: async () => (await api.get<Organization[]>('/organizations')).data,
  });
  const organization = organizations.data?.find((item) => item.id === params.get('organization')) ?? organizations.data?.[0];
  const organizationId = organization?.id;
  const tab = params.get('tab') === 'facts' ? 'facts' : 'documents';
  const runtime = useQuery({ queryKey: ['runtime'], queryFn: async () => (await api.get<{ live_model_calls: boolean }>('/health')).data });
  const documents = useQuery({
    queryKey: ['library-documents', organizationId], enabled: Boolean(organizationId),
    queryFn: async () => (await api.get<DocumentItem[]>(`/organizations/${organizationId}/documents`)).data,
    refetchInterval: 2500,
  });
  const evidence = useQuery({
    queryKey: ['library-evidence', organizationId], enabled: Boolean(organizationId),
    queryFn: async () => (await api.get<Evidence[]>(`/organizations/${organizationId}/evidence`)).data,
    refetchInterval: 4000,
  });
  const jobs = useQuery({
    queryKey: ['library-jobs', organizationId], enabled: Boolean(organizationId),
    queryFn: async () => (await api.get<Job[]>(`/organizations/${organizationId}/jobs`)).data,
    refetchInterval: 2500,
  });
  const previewPages = useQuery({
    queryKey: ['document-pages', preview?.documentId], enabled: Boolean(preview),
    queryFn: async () => (await api.get<PageItem[]>(`/documents/${preview!.documentId}/pages`)).data,
  });
  const previewPage = previewPages.data?.find((item) => item.id === (previewPageId || preview?.span?.page_id)) ?? previewPages.data?.[0];
  const details = evidence.data?.find((item) => item.id === detailsId);
  const refresh = async () => {
    await Promise.all(['organizations', 'library-documents', 'library-evidence', 'library-jobs', 'evidence', 'runs', 'project-library'].map((key) => queryClient.invalidateQueries({ queryKey: [key] })));
  };
  function choose(id: string, nextTab = tab) {
    setParams({ organization: id, tab: nextTab }); setSearch(''); setDetailsId('');
  }
  function editCompany(item: Organization | null) {
    setEditingCompany(item); setCompanyName(item?.name ?? ''); setCompanyCode(item?.unified_code ?? '');
    setCompanyData(item?.metadata_json ?? {}); setError(''); setCompanyOpen(true);
  }
  const saveCompany = useMutation({
    mutationFn: async () => {
      const payload = { name: companyName.trim(), unified_code: companyCode.trim() || null, metadata_json: companyData };
      return (editingCompany ? await api.patch<Organization>(`/organizations/${editingCompany.id}`, payload) : await api.post<Organization>('/organizations', payload)).data;
    },
    onSuccess: async (item) => { setCompanyOpen(false); choose(item.id); setMessage('企业信息已保存'); await refresh(); },
    onError: (err) => setError(apiError(err, '保存企业失败')),
  });
  const rename = useMutation({
    mutationFn: async () => api.patch(`/documents/${renaming!.id}`, { filename: filename.trim() }),
    onSuccess: async () => { setRenaming(null); setMessage('文件名称已更新'); await refresh(); },
    onError: (err) => setError(apiError(err)),
  });
  const documentAction = useMutation({
    mutationFn: async ({ item, action }: { item: DocumentItem; action: string }) => api.post(`/documents/${item.id}/${action}`),
    onSuccess: async () => { setMessage('已加入处理队列'); await refresh(); },
    onError: (err) => setError(apiError(err, '提交任务失败')),
  });
  const verify = useMutation({
    mutationFn: async (item: Evidence) => api.patch(`/evidence/${item.id}`, { review_status: item.review_status === 'verified' ? 'unreviewed' : 'verified' }),
    onSuccess: async () => { setMessage('核实状态已更新，关联项目将重新对标'); await refresh(); },
    onError: (err) => setError(apiError(err)),
  });
  const saveFact = useMutation({
    mutationFn: async () => api.patch(`/evidence-facts/${editingFact!.id}`, {
      value_text: editingFact!.value_number === null && !editingFact!.value_date ? factValue.trim() || null : null,
      value_number: editingFact!.value_number !== null ? factValue || null : null,
      value_date: editingFact!.value_date ? factValue || null : null,
      unit: factUnit.trim() || null, review_status: 'verified',
    }),
    onSuccess: async () => { setEditingFact(null); setMessage('字段已校正，关联项目将重新对标'); await refresh(); },
    onError: (err) => setError(apiError(err, '校正字段失败')),
  });
  const saveEvidence = useMutation({
    mutationFn: async () => api.patch(`/evidence/${evidenceEdit!.id}`, {
      title: evidenceEdit!.title.trim(), holder: evidenceEdit!.holder.trim() || null,
      identifier: evidenceEdit!.identifier.trim() || null,
    }),
    onSuccess: async () => { setEvidenceEdit(null); setMessage('事实信息已校正，原文来源保留'); await refresh(); },
    onError: (err) => setError(apiError(err, '校正事实信息失败')),
  });
  const remove = useMutation({
    mutationFn: async () => api.delete(deleting!.path),
    onSuccess: async () => { setDeleting(null); setDetailsId(''); setMessage('已删除'); await refresh(); },
    onError: (err) => { setDeleting(null); setError(apiError(err, '删除失败')); },
  });
  async function upload(files: FileList) {
    if (!organizationId) return;
    setError(''); setUploading(true);
    const targetId = organizationId;
    let count = 0;
    try {
      for (const file of Array.from(files)) {
        const form = new FormData(); form.append('file', file);
        await api.post(`/organizations/${targetId}/documents`, form); count += 1;
      }
      setMessage(`${count} 份材料已上传，系统将自动处理`);
    } catch (err) { setError(`${count ? `已上传 ${count} 份。` : ''}${apiError(err, '上传失败')}`); }
    finally { setUploading(false); if (fileRef.current) fileRef.current.value = ''; await refresh(); }
  }
  function view(documentId: string, title: string, span?: SourceSpan) {
    setPreview({ documentId, title, span }); setPreviewPageId('');
  }
  function editFact(fact: EvidenceFact) {
    setEditingFact(fact); setFactValue(fact.value_date ?? fact.value_number ?? fact.value_text ?? '');
    setFactUnit(fact.unit ?? ''); setError('');
  }
  const docRows = (documents.data ?? []).filter((item) => item.filename.toLowerCase().includes(search.toLowerCase()));
  const factRows = (evidence.data ?? []).filter((item) => `${item.title} ${item.holder ?? ''} ${item.identifier ?? ''}`.toLowerCase().includes(search.toLowerCase()));
  return (
    <Stack spacing={2}>
      <PageHeader title="企业资料库" actions={<><Button startIcon={<AddRounded />} onClick={() => editCompany(null)}>新增企业</Button>{organization && <Button variant="contained" startIcon={<UploadFileOutlined />} disabled={uploading} onClick={() => fileRef.current?.click()}>{uploading ? '上传中…' : '上传材料'}</Button>}</>} />
      <Notice message={message} onClose={() => setMessage('')} />
      {error && !companyOpen && !renaming && !editingFact && !evidenceEdit && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      <input ref={fileRef} hidden type="file" multiple accept=".pdf,.doc,.docx,.xlsx,.csv,.png,.jpg,.jpeg" aria-label="选择企业材料" onChange={(e) => { if (e.target.files?.length) void upload(e.target.files); }} />
      {organizations.isLoading ? <EmptyState loading title="正在加载企业" /> : organizations.error ? <Alert severity="error">企业资料加载失败，请刷新重试。</Alert> : !organization ? <Paper variant="outlined"><EmptyState title="先建立企业资料库" description="企业材料统一上传一次，项目选择企业后即可复用。" action={<Button variant="contained" onClick={() => editCompany(null)}>新增企业</Button>} /></Paper> : <>
        <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
          <Stack direction={{ xs: 'column', sm: 'row' }} gap={1.5} sx={{ p: 2 }} alignItems={{ sm: 'center' }}>
            <TextField select label="当前企业" value={organization.id} onChange={(e) => choose(e.target.value)} sx={{ minWidth: 200, flex: 1 }}>{organizations.data?.map((item) => <MenuItem key={item.id} value={item.id}>{item.name}</MenuItem>)}</TextField>
            <TextField label={tab === 'documents' ? '搜索文件' : '搜索事实'} value={search} onChange={(e) => setSearch(e.target.value)} sx={{ width: { xs: '100%', sm: 220 } }} />
            <Button color="inherit" onClick={() => editCompany(organization)}>企业信息</Button>
          </Stack>
          <Tabs value={tab} onChange={(_, value) => choose(organization.id, value)} sx={{ px: 2, borderBottom: '1px solid', borderColor: 'divider' }}><Tab value="documents" label={`材料 ${documents.data?.length ?? 0}`} /><Tab value="facts" label={`提取事实 ${evidence.data?.length ?? 0}`} /></Tabs>
          {tab === 'documents' ? documents.isLoading ? <EmptyState loading title="正在加载材料" /> : documents.error ? <Alert severity="error" sx={{ m: 2 }}>材料加载失败。</Alert> : !docRows.length ? <EmptyState title={search ? '没有匹配的材料' : '上传企业证明材料'} description={search ? undefined : '支持资质、人员、业绩、财务和产品资料，以及证书图片。'} action={<Button variant="outlined" onClick={() => fileRef.current?.click()}>选择材料</Button>} /> : <TableContainer><Table sx={{ minWidth: 540 }} aria-label="企业材料"><TableHead><TableRow><TableCell>文件</TableCell><TableCell>处理状态</TableCell><TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>事实</TableCell><TableCell align="right" sx={{ width: 52 }} /></TableRow></TableHead><TableBody>{docRows.map((item) => <TableRow key={item.id} hover>
            <TableCell sx={{ maxWidth: 440 }}><Button color="inherit" disabled={!item.current_revision_id} sx={{ p: 0, minHeight: 0, justifyContent: 'flex-start', textAlign: 'left', fontWeight: 600, overflowWrap: 'anywhere' }} onClick={() => view(item.id, item.filename)}>{item.filename}</Button><Typography variant="caption" color="text.secondary" display="block">{item.page_count ? `${item.page_count} 页 · ` : ''}{formatBytes(item.file_size)}</Typography>{(item.parse_error || item.ai_error) && <Typography variant="caption" color="error" display="block">{item.parse_error || item.ai_error}</Typography>}</TableCell>
            <TableCell sx={{ whiteSpace: 'nowrap' }}><StatusChip status={documentStatus(item)} /><Typography variant="caption" color="text.secondary" display="block">{item.current_revision_id ? '原文已保存' : '正在解析原文'}</Typography></TableCell>
            <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>{item.evidence_count}</TableCell>
            <TableCell align="right"><IconButton aria-label={`操作材料 ${item.filename}`} onClick={(e) => setDocMenu({ anchor: e.currentTarget, item })}><MoreHorizRounded /></IconButton></TableCell>
          </TableRow>)}</TableBody></Table></TableContainer> : evidence.isLoading ? <EmptyState loading title="正在加载事实" /> : evidence.error ? <Alert severity="error" sx={{ m: 2 }}>事实加载失败。</Alert> : !factRows.length ? <EmptyState title="暂无提取事实" description={runtime.data?.live_model_calls ? '上传材料后自动提取，可在材料页查看处理进度。' : '开发阶段暂停 AI 提取；原文件与页面仍会保存，启用模型后自动入库。'} action={!runtime.data?.live_model_calls ? <Button component={Link} to="/settings">模型设置</Button> : undefined} /> : <TableContainer><Table sx={{ minWidth: 520 }} aria-label="企业事实"><TableHead><TableRow><TableCell>事实 / 主体</TableCell><TableCell>类型</TableCell><TableCell>字段</TableCell><TableCell>状态</TableCell></TableRow></TableHead><TableBody>{factRows.map((item) => <TableRow key={item.id} hover>
            <TableCell><Button color="inherit" sx={{ p: 0, minHeight: 0, textAlign: 'left', fontWeight: 600 }} onClick={() => setDetailsId(item.id)}>{item.title}</Button><Typography variant="caption" color="text.secondary" display="block">{item.holder || '主体待核实'}{item.identifier ? ` · ${item.identifier}` : ''}</Typography></TableCell>
            <TableCell>{categoryLabels[item.kind] ?? item.kind}</TableCell><TableCell>{item.facts.length}</TableCell><TableCell><StatusChip status={item.review_status} /></TableCell>
          </TableRow>)}</TableBody></Table></TableContainer>}
          {jobs.data?.filter((job) => ['queued', 'running'].includes(job.status)).map((job) => <Box key={job.id} sx={{ px: 2, py: 1.5, borderTop: '1px solid', borderColor: 'divider' }}><Stack direction="row" justifyContent="space-between"><Typography variant="caption">{job.stage}</Typography><Typography variant="caption">{job.progress}%</Typography></Stack><LinearProgress variant="determinate" value={job.progress} sx={{ mt: 0.75 }} /></Box>)}
        </Paper>
      </>}
      <Menu anchorEl={docMenu?.anchor} open={Boolean(docMenu)} onClose={() => setDocMenu(null)}>
        <MenuItem disabled={!docMenu?.item.current_revision_id} onClick={() => { view(docMenu!.item.id, docMenu!.item.filename); setDocMenu(null); }}>查看原文</MenuItem>
        <MenuItem component="a" href={`/api/v2/documents/${docMenu?.item.id}/file`} onClick={() => setDocMenu(null)}>下载原文件</MenuItem>
        <MenuItem onClick={() => { setRenaming(docMenu!.item); setFilename(docMenu!.item.filename); setError(''); setDocMenu(null); }}>重命名</MenuItem>
        <MenuItem disabled={documentAction.isPending || ['queued', 'running'].includes(docMenu?.item.parse_status ?? '')} onClick={() => { documentAction.mutate({ item: docMenu!.item, action: 'reparse' }); setDocMenu(null); }}>重新解析</MenuItem>
        <MenuItem disabled={!runtime.data?.live_model_calls || !docMenu?.item.current_revision_id || ['queued', 'running'].includes(docMenu?.item.ai_status ?? '') || documentAction.isPending} onClick={() => { documentAction.mutate({ item: docMenu!.item, action: 'process' }); setDocMenu(null); }}>重新 AI 入库</MenuItem>
        <Divider /><MenuItem sx={{ color: 'error.main' }} onClick={() => { const item = docMenu!.item; setDeleting({ path: `/documents/${item.id}`, title: '删除企业材料？', detail: `将删除「${item.filename}」及提取事实，所有关联项目会标记待重新对标。` }); setDocMenu(null); }}>删除材料</MenuItem>
      </Menu>
      <Dialog open={companyOpen} onClose={() => setCompanyOpen(false)} fullWidth maxWidth="sm"><DialogTitle>{editingCompany ? '企业信息' : '新增企业'}</DialogTitle><DialogContent><Stack spacing={2.5} sx={{ pt: 1 }}>{error && <Alert severity="error">{error}</Alert>}<TextField required label="企业名称" value={companyName} onChange={(e) => setCompanyName(e.target.value)} /><TextField label="统一社会信用代码（选填）" value={companyCode} onChange={(e) => setCompanyCode(e.target.value)} />{companyFields.map(([key, label]) => <TextField key={key} label={label} value={companyData[key] ?? ''} onChange={(e) => setCompanyData((current) => ({ ...current, [key]: e.target.value }))} />)}</Stack></DialogContent><DialogActions>{editingCompany && <Button color="error" onClick={() => { setCompanyOpen(false); setDeleting({ path: `/organizations/${editingCompany.id}`, title: '删除企业？', detail: '需先删除企业材料并解除项目关联，才能删除企业。' }); }}>删除企业</Button>}<Box flex={1} /><Button onClick={() => setCompanyOpen(false)}>取消</Button><Button variant="contained" disabled={!companyName.trim() || saveCompany.isPending} onClick={() => saveCompany.mutate()}>保存</Button></DialogActions></Dialog>
      <Dialog open={Boolean(renaming)} onClose={() => setRenaming(null)} fullWidth maxWidth="sm"><DialogTitle>重命名材料</DialogTitle><DialogContent sx={{ pt: '16px !important' }}>{error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}<TextField fullWidth label="文件名称" value={filename} onChange={(e) => setFilename(e.target.value)} /></DialogContent><DialogActions><Button onClick={() => setRenaming(null)}>取消</Button><Button variant="contained" disabled={!filename.trim() || rename.isPending} onClick={() => rename.mutate()}>保存</Button></DialogActions></Dialog>
      <Dialog open={Boolean(details)} onClose={() => setDetailsId('')} fullWidth maxWidth="md"><DialogTitle>{details?.title}</DialogTitle><DialogContent>
        <TableContainer><Table sx={{ minWidth: 500 }} aria-label="事实字段"><TableHead><TableRow><TableCell>字段</TableCell><TableCell>提取内容</TableCell><TableCell>状态</TableCell><TableCell align="right">操作</TableCell></TableRow></TableHead><TableBody>{details?.facts.map((fact) => <TableRow key={fact.id}><TableCell>{factLabels[fact.fact_key] ?? fact.fact_key}</TableCell><TableCell sx={{ maxWidth: 300, overflowWrap: 'anywhere' }}>{fact.value_date ?? fact.value_number ?? fact.value_text ?? '未填写'}{fact.unit ? ` ${fact.unit}` : ''}</TableCell><TableCell><StatusChip status={fact.review_status} /></TableCell><TableCell align="right" sx={{ whiteSpace: 'nowrap' }}><Button size="small" onClick={() => editFact(fact)}>校正</Button><Button size="small" disabled={!fact.source_span && !details?.source_span} onClick={() => { const span = fact.source_span ?? details!.source_span!; view(span.document_id, details!.title, span); }}>原文</Button></TableCell></TableRow>)}</TableBody></Table></TableContainer>
      </DialogContent><DialogActions><Button color="error" onClick={() => setDeleting({ path: `/evidence/${details!.id}`, title: '删除此事实？', detail: '删除事实及字段，原文件保留。关联项目会重新对标。' })}>删除事实</Button><Box flex={1} /><Button onClick={() => { setError(''); setEvidenceEdit({ id: details!.id, title: details!.title, holder: details!.holder ?? '', identifier: details!.identifier ?? '' }); }}>编辑信息</Button><Button disabled={verify.isPending} onClick={() => verify.mutate(details!)}>{details?.review_status === 'verified' ? '撤销核实' : '标记已核实'}</Button><Button onClick={() => setDetailsId('')}>关闭</Button></DialogActions></Dialog>
      <Dialog open={Boolean(editingFact)} onClose={() => setEditingFact(null)} fullWidth maxWidth="sm"><DialogTitle>校正 · {editingFact && (factLabels[editingFact.fact_key] ?? editingFact.fact_key)}</DialogTitle><DialogContent><Stack spacing={2} sx={{ pt: 1 }}>{error && <Alert severity="error">{error}</Alert>}<TextField label="已核实内容" type={editingFact?.value_date ? 'date' : editingFact?.value_number !== null ? 'number' : 'text'} InputLabelProps={{ shrink: true }} value={factValue} onChange={(e) => setFactValue(e.target.value)} /><TextField label="单位（选填）" value={factUnit} onChange={(e) => setFactUnit(e.target.value)} />{editingFact?.source_span && <Typography variant="body2" sx={{ p: 2, bgcolor: 'background.default', whiteSpace: 'pre-wrap' }}>{editingFact.source_span.quote}</Typography>}</Stack></DialogContent><DialogActions><Button onClick={() => setEditingFact(null)}>取消</Button><Button variant="contained" disabled={!factValue.trim() || saveFact.isPending} onClick={() => saveFact.mutate()}>保存并核实</Button></DialogActions></Dialog>
      <Dialog open={Boolean(evidenceEdit)} onClose={() => setEvidenceEdit(null)} fullWidth maxWidth="sm"><DialogTitle>校正事实信息</DialogTitle><DialogContent><Stack spacing={2} sx={{ pt: 1 }}>{error && <Alert severity="error">{error}</Alert>}<TextField required label="事实名称" value={evidenceEdit?.title ?? ''} onChange={(e) => setEvidenceEdit((current) => current && ({ ...current, title: e.target.value }))} /><TextField label="持有主体 / 人员" value={evidenceEdit?.holder ?? ''} onChange={(e) => setEvidenceEdit((current) => current && ({ ...current, holder: e.target.value }))} /><TextField label="证书 / 合同编号" value={evidenceEdit?.identifier ?? ''} onChange={(e) => setEvidenceEdit((current) => current && ({ ...current, identifier: e.target.value }))} /></Stack></DialogContent><DialogActions><Button onClick={() => setEvidenceEdit(null)}>取消</Button><Button variant="contained" disabled={!evidenceEdit?.title.trim() || saveEvidence.isPending} onClick={() => saveEvidence.mutate()}>保存</Button></DialogActions></Dialog>
      <Dialog open={Boolean(preview)} onClose={() => setPreview(null)} fullWidth maxWidth="md"><DialogTitle>{preview?.title}</DialogTitle><DialogContent><Stack spacing={2} sx={{ pt: 1 }}>{previewPages.isLoading ? <EmptyState loading title="正在加载原文" /> : previewPage ? <><TextField select label="页码" value={previewPage.id} onChange={(e) => setPreviewPageId(e.target.value)}>{previewPages.data?.map((page) => <MenuItem key={page.id} value={page.id}>第 {page.page_index + 1} 页</MenuItem>)}</TextField><PageViewer page={previewPage} highlight={preview?.span?.page_id === previewPage.id ? preview.span : undefined} /></> : <EmptyState title="原文尚未就绪" />}</Stack></DialogContent><DialogActions><Button href={`/api/v2/documents/${preview?.documentId}/file`}>下载原文件</Button><Button onClick={() => setPreview(null)}>关闭</Button></DialogActions></Dialog>
      <ConfirmDialog open={Boolean(deleting)} title={deleting?.title ?? ''} description={deleting?.detail ?? ''} pending={remove.isPending} onClose={() => setDeleting(null)} onConfirm={() => remove.mutate()} />
    </Stack>
  );
}
