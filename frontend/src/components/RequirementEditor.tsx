import { useState } from 'react';
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Stack, TextField, Typography } from '@mui/material';
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, apiError, type DocumentItem, type PageItem, type Requirement, type SourceSpan } from '../lib/api';
import { categoryLabels } from '../lib/labels';

export default function RequirementEditor({ runId, projectId, requirement, onClose, onSaved }: {
  runId: string; projectId: string; requirement: Requirement | null;
  onClose: () => void; onSaved: () => Promise<void>;
}) {
  const [title, setTitle] = useState(requirement?.title ?? '');
  const [statement, setStatement] = useState(requirement?.statement ?? '');
  const [category, setCategory] = useState(requirement?.category ?? 'other');
  const [documentId, setDocumentId] = useState('');
  const [pageId, setPageId] = useState('');
  const [spanId, setSpanId] = useState('');
  const version = requirement?.condition_json._version as { supersedes_ids?: string[]; relations?: { reason: string }[] } | undefined;
  const [replaces, setReplaces] = useState<string[]>(version?.supersedes_ids ?? (requirement?.supersedes_id ? [requirement.supersedes_id] : []));
  const [versionChanged, setVersionChanged] = useState(false);
  const requirements = useQuery({
    queryKey: ['requirements', runId], enabled: Boolean(requirement),
    queryFn: async () => (await api.get<Requirement[]>(`/analysis-runs/${runId}/requirements`)).data,
  });
  const documents = useQuery({
    queryKey: ['documents', projectId],
    queryFn: async () => (await api.get<DocumentItem[]>(`/projects/${projectId}/documents`)).data,
  });
  const sources = documents.data?.filter((doc) => ['tender', 'addendum', 'qa'].includes(doc.role) && doc.current_revision_id) ?? [];
  const selectedDocumentId = documentId || sources[0]?.id;
  const pages = useQuery({
    queryKey: ['document-pages', selectedDocumentId], enabled: Boolean(!requirement && selectedDocumentId),
    queryFn: async () => (await api.get<PageItem[]>(`/documents/${selectedDocumentId}/pages`)).data,
  });
  const selectedPageId = pageId || pages.data?.[0]?.id;
  const spans = useQuery({
    queryKey: ['source-spans', selectedPageId], enabled: Boolean(!requirement && selectedPageId),
    queryFn: async () => (await api.get<SourceSpan[]>(`/pages/${selectedPageId}/source-spans`)).data,
  });
  const selectedSpan = spans.data?.find((span) => span.id === spanId);
  const save = useMutation({
    mutationFn: async () => {
      const payload = { title: title.trim(), statement: statement.trim(), category,
        ...(versionChanged ? { supersedes_ids: replaces, version_confirmed: true } : {}) };
      return requirement
        ? api.patch(`/requirements/${requirement.id}`, payload)
        : api.post(`/analysis-runs/${runId}/requirements`, { ...payload, source_span_id: spanId });
    },
    onSuccess: async () => { await onSaved(); onClose(); },
  });
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{requirement ? '修改要求' : '手工补充要求'}</DialogTitle>
      <DialogContent>
        <Stack spacing={2.25} sx={{ pt: 1 }}>
          <Typography color="text.secondary">补充漏提内容或修正提取结果。保存后需重新核对结论；误提内容可在人工复核时设为「不适用」并记录原因。</Typography>
          {save.isError && <Alert severity="error">{apiError(save.error, '保存要求失败')}</Alert>}
          {!requirement && <>
            <TextField select label="来源文件" value={selectedDocumentId ?? ''} disabled={!sources.length} onChange={(event) => { setDocumentId(event.target.value); setPageId(''); setSpanId(''); }}>{sources.length ? sources.map((doc) => <MenuItem key={doc.id} value={doc.id}>{doc.filename}</MenuItem>) : <MenuItem value="" disabled>{documents.isLoading ? '正在加载文件…' : '暂无可用招标文件'}</MenuItem>}</TextField>
            <TextField select label="来源页码" value={selectedPageId ?? ''} disabled={!pages.data?.length} onChange={(event) => { setPageId(event.target.value); setSpanId(''); }}>{pages.data?.length ? pages.data.map((page) => <MenuItem key={page.id} value={page.id}>第 {page.page_index + 1} 页</MenuItem>) : <MenuItem value="" disabled>{pages.isLoading ? '正在加载页码…' : '暂无可用页面'}</MenuItem>}</TextField>
            <TextField select label="依据原文" value={spanId} onChange={(event) => {
              setSpanId(event.target.value);
              if (!statement) setStatement(spans.data?.find((span) => span.id === event.target.value)?.quote ?? '');
            }} helperText="本页无文字时，可回项目预览中人工校正文字。"><MenuItem value="">请选择原文片段</MenuItem>{spans.data?.map((span) => <MenuItem key={span.id} value={span.id} sx={{ whiteSpace: 'normal', maxWidth: 500 }}>{span.quote.slice(0, 150)}</MenuItem>)}</TextField>
          </>}
          {(requirement?.source_span || selectedSpan) && <Typography sx={{ p: 2, bgcolor: '#F9FAFB', whiteSpace: 'pre-wrap', maxHeight: 200, overflow: 'auto' }}>{(requirement?.source_span ?? selectedSpan)?.quote}</Typography>}
          <TextField label="要求标题" required value={title} onChange={(event) => setTitle(event.target.value)} />
          <TextField label="要求内容" required multiline minRows={4} value={statement} onChange={(event) => setStatement(event.target.value)} />
          <TextField select label="要求类别" value={category} onChange={(event) => setCategory(event.target.value)}>{Object.entries(categoryLabels).map(([key, label]) => <MenuItem key={key} value={key}>{label}</MenuItem>)}</TextField>
          {requirement && <>
            {version?.relations?.map((relation, index) => <Typography key={index} color="text.secondary">{relation.reason}</Typography>)}
            <TextField select label="本条替代的旧条款" value={replaces} SelectProps={{ multiple: true }}
              onChange={(event) => { setReplaces(typeof event.target.value === 'string' ? event.target.value.split(',') : event.target.value); setVersionChanged(true); }}
              helperText="可多选；确认作为独立要求时不选旧条款。保存后重新执行本次规则核对。">
              {requirements.data?.filter((item) => item.id !== requirement.id).map((item) => <MenuItem key={item.id} value={item.id}>{item.title} · {item.statement.slice(0, 60)}</MenuItem>)}
            </TextField>
            {version && <Button size="small" sx={{ alignSelf: 'flex-start' }} onClick={() => setVersionChanged(true)}>确认当前条款关系</Button>}
          </>}
        </Stack>
      </DialogContent>
      <DialogActions><Button onClick={onClose}>取消</Button><Button variant="contained" disabled={!title.trim() || !statement.trim() || (!requirement && !spanId) || save.isPending} onClick={() => save.mutate()}>保存要求</Button></DialogActions>
    </Dialog>
  );
}
