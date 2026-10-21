import { useState } from 'react';
import { Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Divider, Grid, MenuItem, Paper, Stack, TextField, Typography } from '@mui/material';
import AddRounded from '@mui/icons-material/AddRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { api, apiError, type DocumentItem, type Evidence, type PageItem, type SourceSpan } from '../lib/api';
import { categoryLabels } from '../lib/labels';
import { ConfirmDialog, EmptyState, Guidance, PageHeader, StatusChip } from '../components/Workspace';
import PageViewer from '../components/PageViewer';

const factFields: Record<string, Array<[string, string, string?]>> = {
  qualification: [['certificate_name', '资质 / 证书名称'], ['level', '资质等级'], ['scope', '适用范围']],
  personnel: [['certificate_name', '人员证书名称'], ['certificate_type', '证书类型']],
  performance: [['project_name', '业绩项目名称'], ['client_name', '业主单位'], ['contract_amount', '合同金额', 'number'], ['project_scope', '项目范围']],
  financial: [['registered_capital', '注册资本', 'number'], ['revenue', '营业收入', 'number']],
};

export default function EvidencePage() {
  const { projectId = '' } = useParams();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Evidence | null>(null);
  const [deleting, setDeleting] = useState<Evidence | null>(null);
  const [viewing, setViewing] = useState<Evidence | null>(null);
  const [kind, setKind] = useState('qualification');
  const [title, setTitle] = useState('');
  const [holder, setHolder] = useState('');
  const [identifier, setIdentifier] = useState('');
  const [validUntil, setValidUntil] = useState('');
  const [facts, setFacts] = useState<Record<string, string>>({});
  const [documentId, setDocumentId] = useState('');
  const [pageId, setPageId] = useState('');
  const [spanId, setSpanId] = useState('');
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const evidence = useQuery({ queryKey: ['evidence', projectId], queryFn: async () => (await api.get<Evidence[]>(`/projects/${projectId}/evidence`)).data });
  const documents = useQuery({ queryKey: ['documents', projectId], queryFn: async () => (await api.get<DocumentItem[]>(`/projects/${projectId}/documents`)).data });
  const sources = documents.data?.filter((doc) => doc.role === 'evidence' && doc.current_revision_id) ?? [];
  const selectedDocumentId = documentId || sources[0]?.id;
  const pages = useQuery({ queryKey: ['evidence-pages', selectedDocumentId], enabled: Boolean(open && !editing && selectedDocumentId), queryFn: async () => (await api.get<PageItem[]>(`/documents/${selectedDocumentId}/pages`)).data });
  const selectedPageId = pageId || pages.data?.[0]?.id;
  const spans = useQuery({ queryKey: ['source-spans', selectedPageId], enabled: Boolean(open && !editing && selectedPageId), queryFn: async () => (await api.get<SourceSpan[]>(`/pages/${selectedPageId}/source-spans`)).data });
  const selectedSpan = spans.data?.find((span) => span.id === spanId);
  const viewPage = useQuery({ queryKey: ['page', viewing?.source_span?.page_id], enabled: Boolean(viewing?.source_span?.page_id), queryFn: async () => (await api.get<PageItem>(`/pages/${viewing!.source_span!.page_id}`)).data });
  const refresh = async () => { await queryClient.invalidateQueries({ queryKey: ['evidence', projectId] }); await queryClient.invalidateQueries({ queryKey: ['runs', projectId] }); };
  const save = useMutation({
    mutationFn: async () => {
      const payload = Object.fromEntries(Object.entries(facts).filter(([, value]) => value.trim()));
      const body = { title: title.trim(), holder: holder.trim() || null, identifier: identifier.trim() || null, valid_until: validUntil || null, payload };
      return editing ? api.patch(`/evidence/${editing.id}`, body) : api.post(`/projects/${projectId}/evidence`, { ...body, kind, source_span_id: spanId });
    },
    onSuccess: async () => { setOpen(false); setMessage('证据资料已保存。已有分析需要重新核验时，会显示「资料已更新」。'); await refresh(); },
    onError: (err) => setError(apiError(err, '保存证据失败')),
  });
  const verify = useMutation({
    mutationFn: async (item: Evidence) => api.patch(`/evidence/${item.id}`, { review_status: item.review_status === 'verified' ? 'unreviewed' : 'verified' }),
    onSuccess: async () => { setMessage('核实状态已更新'); await refresh(); },
    onError: (err) => setError(apiError(err, '更新核实状态失败')),
  });
  const remove = useMutation({
    mutationFn: async () => api.delete(`/evidence/${deleting!.id}`),
    onSuccess: async () => { setDeleting(null); setMessage('证据已删除，相关分析需重新核验'); await refresh(); },
    onError: (err) => { setDeleting(null); setError(apiError(err, '删除证据失败')); },
  });
  function edit(item: Evidence | null) {
    setEditing(item); setKind(item?.kind ?? 'qualification'); setTitle(item?.title ?? ''); setHolder(item?.holder ?? ''); setIdentifier(item?.identifier ?? ''); setValidUntil(item?.valid_until ?? '');
    setFacts(Object.fromEntries(Object.entries(item?.payload ?? {}).map(([key, value]) => [key, String(value ?? '')])));
    setDocumentId(''); setPageId(''); setSpanId(''); setError(''); setOpen(true);
  }
  const rows = (evidence.data ?? []).filter((item) => (filter === 'all' || item.kind === filter) && `${item.title} ${item.holder ?? ''} ${item.identifier ?? ''}`.toLowerCase().includes(search.toLowerCase()));
  return (
    <Stack spacing={3}>
      <PageHeader title="证据资料" description="登记企业资质、人员、业绩和财务信息，并为每条证据绑定证明材料原文。" actions={<><Button component={Link} to={`/projects/${projectId}`} variant="outlined">返回项目</Button><Button variant="contained" startIcon={<AddRounded />} onClick={() => edit(null)}>登记证据</Button></>} />
      <Guidance title="先上传证明材料，再登记证据" action={<Button component={Link} to={`/projects/${projectId}?upload=evidence#files`} variant="outlined">上传证明材料</Button>}>
        登记时选择「文件 → 页码 → 原文片段」，录入关键字段，核对无误后标记为已核实。系统会用这些资料支持要求核验。
      </Guidance>
      {message && <Alert severity="success" onClose={() => setMessage('')}>{message}</Alert>}{error && !open && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" alignItems={{ sm: 'center' }} gap={2} sx={{ p: 2.5, borderBottom: '1px solid', borderColor: 'divider' }}><Box><Typography variant="h6">证据列表</Typography><Typography variant="caption" color="text.secondary">共 {rows.length} 条证据</Typography></Box><Stack direction="row" gap={1}><TextField label="搜索证据" placeholder="名称、主体或编号" value={search} onChange={(event) => setSearch(event.target.value)} /><TextField select label="证据类型" value={filter} onChange={(event) => setFilter(event.target.value)} sx={{ width: 140, flexShrink: 0 }}><MenuItem value="all">全部类型</MenuItem>{Object.keys(factFields).map((key) => <MenuItem key={key} value={key}>{categoryLabels[key]}</MenuItem>)}</TextField></Stack></Stack>
        {evidence.isLoading ? <EmptyState title="正在加载证据" loading /> : evidence.error ? <Alert severity="error" sx={{ m: 2 }}>证据加载失败，请重试。</Alert> : !rows.length ? <EmptyState title="暂无匹配的证据" description="上传证明材料后，点击「登记证据」填写关键字段。不会自动调用模型。" action={<Button variant="outlined" onClick={() => edit(null)}>登记第一条证据</Button>} /> : <Stack divider={<Divider />}>
          {rows.map((item) => <Box key={item.id} sx={{ p: 2.5 }}><Stack direction="row" justifyContent="space-between" gap={2}><Box><Typography variant="subtitle1">{item.title}</Typography><Typography variant="body2" color="text.secondary">{categoryLabels[item.kind]} · {item.holder || '主体未填写'}{item.identifier ? ` · ${item.identifier}` : ''}</Typography></Box><StatusChip status={item.review_status} /></Stack>
            {item.source_span && <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5, px: 1.5, py: 1, bgcolor: '#F9FAFB', borderLeft: '2px solid', borderColor: 'divider', overflowWrap: 'anywhere' }}>原文：{item.source_span.quote}</Typography>}
            <Stack direction="row" gap={1.5} sx={{ mt: 1 }}><Typography variant="caption" color="text.secondary">{item.facts.length} 个关键字段</Typography>{item.valid_until && <Typography variant="caption" color="text.secondary">有效期至 {item.valid_until}</Typography>}</Stack>
            <Stack direction="row" gap={0.5} flexWrap="wrap" sx={{ mt: 1 }}><Button size="small" disabled={!item.source_span} onClick={() => setViewing(item)}>查看来源</Button><Button size="small" onClick={() => edit(item)}>编辑</Button><Button size="small" color="inherit" disabled={verify.isPending} onClick={() => verify.mutate(item)}>{item.review_status === 'verified' ? '撤销核实' : '标记已核实'}</Button><Button size="small" color="error" onClick={() => setDeleting(item)}>删除</Button></Stack>
          </Box>)}
        </Stack>}
      </Paper>
      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="md"><DialogTitle>{editing ? '编辑证据资料' : '登记证据资料'}</DialogTitle><DialogContent><Stack spacing={2} sx={{ pt: 1 }}>{error && <Alert severity="error">{error}</Alert>}<Box><Grid container spacing={3}>
        <Grid item xs={12} sm={6}><Stack spacing={2.25}><Typography variant="subtitle1">1. 基本信息与关键字段</Typography><TextField select label="证据类型" value={kind} disabled={Boolean(editing)} onChange={(event) => { setKind(event.target.value); setFacts({}); }}>{Object.keys(factFields).map((key) => <MenuItem key={key} value={key}>{categoryLabels[key]}</MenuItem>)}</TextField><TextField required label="证据名称" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="例如：公司营业执照" /><TextField label="持有主体 / 人员" value={holder} onChange={(event) => setHolder(event.target.value)} /><TextField label="证书 / 合同编号" value={identifier} onChange={(event) => setIdentifier(event.target.value)} /><TextField label="有效期至（选填）" type="date" value={validUntil} onChange={(event) => setValidUntil(event.target.value)} InputLabelProps={{ shrink: true }} /><Divider />{factFields[kind].map(([key, label, type]) => <TextField key={key} label={label} type={type ?? 'text'} value={facts[key] ?? ''} onChange={(event) => setFacts((current) => ({ ...current, [key]: event.target.value }))} />)}{['performance', 'financial'].includes(kind) && <TextField select label="金额单位" value={facts.unit ?? ''} onChange={(event) => setFacts((current) => ({ ...current, unit: event.target.value }))}><MenuItem value="">请选择原文中的单位</MenuItem>{['元', '万元', '亿元'].map((unit) => <MenuItem key={unit} value={unit}>{unit}</MenuItem>)}</TextField>}</Stack></Grid>
        <Grid item xs={12} sm={6}><Stack spacing={2.25}><Typography variant="subtitle1">2. 绑定证明材料原文</Typography>{editing ? <><Typography color="text.secondary">来源绑定保留。请对照原文修改字段。</Typography><Typography sx={{ p: 2, bgcolor: '#F9FAFB', borderRadius: 1, whiteSpace: 'pre-wrap' }}>{editing.source_span?.quote ?? '来源片段不可用'}</Typography></> : !sources.length ? <EmptyState title="尚无可用的证明材料" description="请先上传用途为「证明材料」的文件，等待解析完成后再登记。" action={<Button component={Link} to={`/projects/${projectId}?upload=evidence#files`}>前往上传证明材料</Button>} /> : <><TextField select label="来源文件" value={selectedDocumentId ?? ''} onChange={(event) => { setDocumentId(event.target.value); setPageId(''); setSpanId(''); }}>{sources.map((doc) => <MenuItem key={doc.id} value={doc.id}>{doc.filename}</MenuItem>)}</TextField><TextField select label="来源页码" value={selectedPageId ?? ''} onChange={(event) => { setPageId(event.target.value); setSpanId(''); }} disabled={!pages.data?.length}>{pages.data?.map((page) => <MenuItem key={page.id} value={page.id}>第 {page.page_index + 1} 页</MenuItem>)}</TextField><TextField select label="原文片段" value={spanId} onChange={(event) => setSpanId(event.target.value)} disabled={!spans.data?.length} helperText="选择直接证明上述字段的原文，不需要填写内部编号。"><MenuItem value="">请选择证明信息所在段落</MenuItem>{spans.data?.map((span) => <MenuItem key={span.id} value={span.id} sx={{ whiteSpace: 'normal', maxWidth: 520 }}>{span.quote.slice(0, 110)}</MenuItem>)}</TextField>{selectedSpan && <Typography sx={{ p: 2, bgcolor: '#F9FAFB', borderRadius: 1, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{selectedSpan.quote}</Typography>}{spans.data?.length === 0 && <Alert severity="info">本页没有可用文字片段。请选择其他页，扫描页需先完成文字识别或人工复核。</Alert>}</>}</Stack></Grid>
      </Grid></Box></Stack></DialogContent><DialogActions><Button onClick={() => setOpen(false)}>取消</Button><Button variant="contained" disabled={!title.trim() || (!editing && !spanId) || save.isPending} onClick={() => save.mutate()}>{save.isPending ? '保存中…' : '保存证据'}</Button></DialogActions></Dialog>
      <Dialog open={Boolean(viewing)} onClose={() => setViewing(null)} fullWidth maxWidth="md"><DialogTitle>证据来源 · {viewing?.title}</DialogTitle><DialogContent>{viewPage.isLoading ? <EmptyState loading title="正在加载来源" /> : viewPage.data ? <PageViewer page={viewPage.data} highlight={viewing?.source_span} /> : <EmptyState title="来源页面暂不可用" />}</DialogContent><DialogActions><Button onClick={() => setViewing(null)}>关闭</Button></DialogActions></Dialog>
      <ConfirmDialog open={Boolean(deleting)} title="删除证据？" description={`将删除「${deleting?.title ?? ''}」及其关键字段，原证明文件仍保留；已有分析将标记为需重新核验。`} pending={remove.isPending} onClose={() => setDeleting(null)} onConfirm={() => remove.mutate()} />
    </Stack>
  );
}
