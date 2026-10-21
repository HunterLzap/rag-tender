import { useState } from 'react';
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Checkbox, Chip,
  Dialog, DialogActions, DialogContent, DialogTitle, Divider, FormControlLabel,
  Paper, Stack, Switch, TextField, Typography,
} from '@mui/material';
import AddRounded from '@mui/icons-material/AddRounded';
import ExpandMoreRounded from '@mui/icons-material/ExpandMoreRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ConfirmDialog, EmptyState, Notice, PageHeader } from '../components/Workspace';
import { api, apiError, type ModelConfig } from '../lib/api';

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<ModelConfig | null>(null);
  const [deleting, setDeleting] = useState<ModelConfig | null>(null);
  const [form, setForm] = useState({
    name: '', base_url: '', api_key: '', text_model: '', vision_model: '',
    embedding_model: '', embedding_base_url: '', embedding_api_key: '', embedding_dimensions: '',
  });
  const [inheritKey, setInheritKey] = useState(true);
  const [isActive, setIsActive] = useState(true);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const runtime = useQuery({ queryKey: ['runtime'], queryFn: async () => (await api.get<{ live_model_calls: boolean }>('/health')).data });
  const configs = useQuery({ queryKey: ['model-configs'], queryFn: async () => (await api.get<ModelConfig[]>('/model-configs')).data });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['model-configs'] });
  const set = (key: keyof typeof form, value: string) => setForm((current) => ({ ...current, [key]: value }));
  const save = useMutation({
    mutationFn: async () => {
      const payload = {
        name: form.name.trim(), base_url: form.base_url.trim(),
        text_model: form.text_model.trim(), vision_model: form.vision_model.trim() || null,
        embedding_model: form.embedding_model.trim(),
        embedding_base_url: form.embedding_base_url.trim() || null,
        embedding_dimensions: form.embedding_dimensions ? Number(form.embedding_dimensions) : null,
        is_active: isActive,
        ...(form.api_key ? { api_key: form.api_key } : {}),
        ...(inheritKey ? { embedding_api_key: null } : form.embedding_api_key ? { embedding_api_key: form.embedding_api_key } : {}),
      };
      return editing ? api.patch(`/model-configs/${editing.id}`, payload) : api.post('/model-configs', payload);
    },
    onSuccess: async () => {
      setOpen(false); set('api_key', ''); set('embedding_api_key', '');
      setMessage('配置已加密保存，未执行连接测试'); await refresh();
    },
    onError: (err) => setError(apiError(err, '保存配置失败')),
  });
  const activate = useMutation({
    mutationFn: async (config: ModelConfig) => api.patch(`/model-configs/${config.id}`, { is_active: !config.is_active }),
    onSuccess: async () => { setMessage('默认模型配置已更新'); await refresh(); },
    onError: (err) => setError(apiError(err, '更新配置失败')),
  });
  const remove = useMutation({
    mutationFn: async () => api.delete(`/model-configs/${deleting!.id}`),
    onSuccess: async () => { setDeleting(null); setMessage('配置已删除'); await refresh(); },
    onError: (err) => { setDeleting(null); setError(apiError(err, '删除配置失败')); },
  });
  function edit(config: ModelConfig | null) {
    setEditing(config);
    setForm({
      name: config?.name ?? '默认模型', base_url: config?.base_url ?? '', api_key: '',
      text_model: config?.text_model ?? '', vision_model: config?.vision_model ?? '',
      embedding_model: config?.embedding_model ?? '',
      embedding_base_url: config?.embedding_base_url ?? '', embedding_api_key: '',
      embedding_dimensions: config?.embedding_dimensions?.toString() ?? '',
    });
    setInheritKey(!config || config.embedding_api_key_masked !== '****');
    setIsActive(config?.is_active ?? true); setError(''); setOpen(true);
  }
  const embeddingKeyReady = inheritKey || form.embedding_api_key || (editing?.embedding_api_key_masked === '****');
  return (
    <Stack spacing={2}>
      <PageHeader title="模型设置" actions={<Button variant="contained" startIcon={<AddRounded />} onClick={() => edit(null)}>新增配置</Button>} />
      <Notice message={message} onClose={() => setMessage('')} />
      {error && !open && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      {!runtime.data?.live_model_calls && <Alert severity="info">开发阶段暂停真实调用。可以保存配置，AI 入库与分析将在启用模型后执行。</Alert>}
      <Paper variant="outlined">
        {configs.isLoading ? <EmptyState loading title="正在加载配置" /> : configs.error ? <Alert severity="error" sx={{ m: 2 }}>配置加载失败，请重试。</Alert> : !configs.data?.length ? <EmptyState title="配置主模型和 Embedding 模型" description="主模型需要支持图片输入；两种模型可以使用不同服务商。" action={<Button variant="contained" onClick={() => edit(null)}>新增配置</Button>} /> : <Stack divider={<Divider />}>
          {configs.data.map((config) => <Box key={config.id} sx={{ p: 2.5 }}>
            <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={2}>
              <Stack spacing={1} minWidth={0}>
                <Stack direction="row" gap={1} alignItems="center"><Typography variant="subtitle1">{config.name}</Typography><Chip color={config.is_active ? 'success' : 'default'} label={config.is_active ? '默认配置' : '未启用'} /></Stack>
                <Typography variant="body2">多模态主模型：{config.text_model}</Typography>
                <Typography variant="body2" color={config.embedding_model ? 'text.primary' : 'warning.main'}>Embedding：{config.embedding_model || '待补充'}</Typography>
                {config.vision_model && <Typography variant="body2">视觉覆盖：{config.vision_model}</Typography>}
                <Typography variant="caption" color="text.secondary" sx={{ overflowWrap: 'anywhere' }}>{config.base_url} · 密钥已加密</Typography>
                {config.embedding_base_url && <Typography variant="caption" color="text.secondary" sx={{ overflowWrap: 'anywhere' }}>Embedding 地址：{config.embedding_base_url}</Typography>}
              </Stack>
              <Stack direction="row" gap={0.5} alignItems="flex-start" flexWrap="wrap">
                <Button size="small" onClick={() => edit(config)}>编辑</Button>
                <Button size="small" color="inherit" disabled={activate.isPending} onClick={() => activate.mutate(config)}>{config.is_active ? '停用' : '设为默认'}</Button>
                <Button size="small" color="error" onClick={() => setDeleting(config)}>删除</Button>
              </Stack>
            </Stack>
          </Box>)}
        </Stack>}
      </Paper>
      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>{editing ? '编辑模型配置' : '新增模型配置'}</DialogTitle>
        <DialogContent><Stack spacing={2.5} sx={{ pt: 1 }}>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField label="配置名称" required value={form.name} onChange={(e) => set('name', e.target.value)} />
          <Typography variant="subtitle2">多模态主模型</Typography>
          <TextField label="主模型名称" required value={form.text_model} onChange={(e) => set('text_model', e.target.value)} helperText="需支持文本和图片输入，用于文档理解、对标和填写建议。" />
          <TextField label="主模型服务地址" required value={form.base_url} onChange={(e) => set('base_url', e.target.value)} placeholder="https://服务域名/v1" />
          <TextField label="主模型 API Key" type="password" required={!editing} autoComplete="new-password" value={form.api_key} onChange={(e) => set('api_key', e.target.value)} helperText={editing ? '留空保留原密钥。' : '只保存本地加密结果。'} />
          <Divider /><Typography variant="subtitle2">Embedding 模型</Typography>
          <TextField label="Embedding 模型名称" required value={form.embedding_model} onChange={(e) => set('embedding_model', e.target.value)} helperText="用于企业材料的语义索引和检索召回。" />
          <TextField label="Embedding 服务地址（选填）" value={form.embedding_base_url} onChange={(e) => set('embedding_base_url', e.target.value)} helperText="留空沿用主模型地址；可接不同服务商。" />
          <FormControlLabel control={<Checkbox checked={inheritKey} onChange={(_, checked) => setInheritKey(checked)} />} label="Embedding 沿用主模型密钥" />
          {!inheritKey && <TextField label="Embedding API Key" type="password" autoComplete="new-password" value={form.embedding_api_key} onChange={(e) => set('embedding_api_key', e.target.value)} helperText={editing?.embedding_api_key_masked === '****' ? '留空保留已保存的独立密钥。' : '填写 Embedding 服务商的密钥。'} />}
          <TextField label="向量维度（选填）" type="number" inputProps={{ min: 1, step: 1 }} value={form.embedding_dimensions} onChange={(e) => set('embedding_dimensions', e.target.value)} helperText="留空使用模型默认维度。" />
          <Accordion disableGutters elevation={0} sx={{ border: '1px solid', borderColor: 'divider' }}><AccordionSummary expandIcon={<ExpandMoreRounded />}><Typography variant="body2">独立视觉模型（选填）</Typography></AccordionSummary><AccordionDetails><TextField fullWidth label="视觉模型名称" value={form.vision_model} onChange={(e) => set('vision_model', e.target.value)} helperText="留空使用主模型读图；覆盖模型使用主模型的地址和密钥。" /></AccordionDetails></Accordion>
          <FormControlLabel control={<Switch checked={isActive} onChange={(_, checked) => setIsActive(checked)} />} label="设为默认配置" />
        </Stack></DialogContent>
        <DialogActions><Button onClick={() => setOpen(false)}>取消</Button><Button variant="contained" disabled={!form.name.trim() || !form.base_url.trim() || !form.text_model.trim() || !form.embedding_model.trim() || (!editing && !form.api_key) || !embeddingKeyReady || (Boolean(form.embedding_dimensions) && (!Number.isInteger(Number(form.embedding_dimensions)) || Number(form.embedding_dimensions) < 1)) || save.isPending} onClick={() => save.mutate()}>{save.isPending ? '保存中…' : '保存配置'}</Button></DialogActions>
      </Dialog>
      <ConfirmDialog open={Boolean(deleting)} title="删除模型配置？" description={`将删除「${deleting?.name ?? ''}」及主模型、Embedding 的密钥，历史结果保留。`} pending={remove.isPending} onClose={() => setDeleting(null)} onConfirm={() => remove.mutate()} />
    </Stack>
  );
}
