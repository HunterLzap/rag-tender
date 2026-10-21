import { useState } from 'react';
import { Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Divider, FormControlLabel, Paper, Stack, Switch, TextField, Typography } from '@mui/material';
import AddRounded from '@mui/icons-material/AddRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ConfirmDialog, EmptyState, Guidance, PageHeader } from '../components/Workspace';
import { api, apiError } from '../lib/api';

interface ModelConfig {
  id: string; name: string; base_url: string; text_model: string;
  vision_model: string | null; api_key_masked: string; is_active: boolean;
}

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<ModelConfig | null>(null);
  const [deleting, setDeleting] = useState<ModelConfig | null>(null);
  const [name, setName] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [textModel, setTextModel] = useState('');
  const [visionModel, setVisionModel] = useState('');
  const [isActive, setIsActive] = useState(true);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const runtime = useQuery({ queryKey: ['runtime'], queryFn: async () => (await api.get<{ live_model_calls: boolean }>('/health')).data });
  const configs = useQuery({ queryKey: ['model-configs'], queryFn: async () => (await api.get<ModelConfig[]>('/model-configs')).data });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['model-configs'] });
  const save = useMutation({
    mutationFn: async () => {
      const payload = { name: name.trim(), base_url: baseUrl.trim(), text_model: textModel.trim(), vision_model: visionModel.trim() || null, is_active: isActive, ...(apiKey ? { api_key: apiKey } : {}) };
      return editing ? api.patch(`/model-configs/${editing.id}`, payload) : api.post('/model-configs', payload);
    },
    onSuccess: async () => { setOpen(false); setApiKey(''); setMessage('配置已加密保存，未自动调用模型'); await refresh(); },
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
  const test = useMutation({
    mutationFn: async (config: ModelConfig) => (await api.post<{ success: boolean; latency_ms: number; message: string }>('/model-configs/test', { config_id: config.id, model: config.text_model })).data,
    onSuccess: (result) => { if (result.success) setMessage(`连接成功，用时 ${result.latency_ms} ms`); else setError(result.message); },
    onError: (err) => setError(apiError(err, '测试连接失败')),
  });
  function edit(config: ModelConfig | null) {
    setEditing(config); setName(config?.name ?? '默认模型'); setBaseUrl(config?.base_url ?? '');
    setApiKey(''); setTextModel(config?.text_model ?? ''); setVisionModel(config?.vision_model ?? '');
    setIsActive(config?.is_active ?? true); setError(''); setMessage(''); setOpen(true);
  }
  return (
    <Stack spacing={3}>
      <PageHeader title="模型设置" description="管理文本和视觉模型的接入配置。保存配置后，回到项目进行资料准备。" actions={<Button variant="contained" startIcon={<AddRounded />} onClick={() => edit(null)}>新增配置</Button>} />
      <Guidance title={runtime.data?.live_model_calls ? '模型调用已启用' : '当前为离线模式'} step="运行状态">
        {runtime.data?.live_model_calls ? '分析与连接测试会调用你配置的模型。新增、编辑和保存配置不会自动测试。' : '可以新增、编辑和保存配置；真实分析与连接测试保持关闭。已有结果可继续查看和编辑。'}
      </Guidance>
      {message && <Alert severity="success" onClose={() => setMessage('')}>{message}</Alert>}
      {error && !open && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      <Paper variant="outlined">
        <Box sx={{ p: 2.5, borderBottom: '1px solid', borderColor: 'divider' }}><Typography variant="h6">接入配置</Typography><Typography variant="body2" color="text.secondary">设为默认的配置将用于新建的分析任务，已有任务保留原配置。</Typography></Box>
        {configs.isLoading ? <EmptyState loading title="正在加载配置" /> : configs.error ? <Alert severity="error" sx={{ m: 2 }}>配置加载失败，请重试。</Alert> : !configs.data?.length ? <EmptyState title="尚未添加模型配置" description="准备好服务地址、模型名称和 API Key 后，点击「新增配置」。" action={<Button variant="contained" onClick={() => edit(null)}>新增配置</Button>} /> : <Stack divider={<Divider />}>
          {configs.data.map((config) => <Box key={config.id} sx={{ p: 2.5 }}>
            <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={2}>
              <Box minWidth={0}><Stack direction="row" alignItems="center" gap={1}><Typography variant="subtitle1">{config.name}</Typography><Chip color={config.is_active ? 'success' : 'default'} label={config.is_active ? '默认配置' : '未启用'} /></Stack><Typography color="text.secondary" variant="body2" sx={{ mt: 0.75, overflowWrap: 'anywhere' }}>服务地址：{config.base_url}</Typography><Typography variant="body2" sx={{ mt: 1 }}>文本模型：{config.text_model}</Typography><Typography variant="body2" color="text.secondary">视觉模型：{config.vision_model || '未配置，扫描页需人工复核'}</Typography><Typography variant="caption" color="text.secondary">API Key：{config.api_key_masked} · 已加密保存</Typography></Box>
              <Stack direction="row" gap={0.5} alignItems="flex-start" flexWrap="wrap"><Button size="small" onClick={() => edit(config)}>编辑</Button><Button size="small" color="inherit" disabled={activate.isPending} onClick={() => activate.mutate(config)}>{config.is_active ? '停用' : '设为默认'}</Button><Button size="small" disabled={!runtime.data?.live_model_calls || test.isPending} onClick={() => test.mutate(config)} title={!runtime.data?.live_model_calls ? '离线模式下不调用真实模型' : '发送一次模型请求测试连接'}>测试连接</Button><Button size="small" color="error" onClick={() => setDeleting(config)}>删除</Button></Stack>
            </Stack>
          </Box>)}
        </Stack>}
      </Paper>
      <Paper variant="outlined" sx={{ p: 2.5 }}><Typography variant="subtitle2">配置说明</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>文本模型用于理解招标要求，视觉模型用于识别扫描页面。密钥只在本地保存加密结果，编辑时留空即可沿用；默认配置的切换不会启用当前关闭的真实模型调用。</Typography></Paper>
      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm"><DialogTitle>{editing ? '编辑模型配置' : '新增模型配置'}</DialogTitle><DialogContent><Stack spacing={2.5} sx={{ pt: 1 }}>{error && <Alert severity="error">{error}</Alert>}<TextField label="配置名称" required value={name} onChange={(event) => setName(event.target.value)} /><TextField label="服务地址（Base URL）" required value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://服务域名/v1" helperText="填写服务商提供的兼容 OpenAI 接口地址。" /><TextField label="API Key" type="password" required={!editing} value={apiKey} onChange={(event) => setApiKey(event.target.value)} autoComplete="new-password" helperText={editing ? '留空保留已保存的密钥；填写新值将替换原密钥。' : '只保存加密结果，列表和接口不会显示明文。'} /><TextField label="文本模型名称" required value={textModel} onChange={(event) => setTextModel(event.target.value)} helperText="与服务商提供的模型名称一致。" /><TextField label="视觉模型名称（选填）" value={visionModel} onChange={(event) => setVisionModel(event.target.value)} helperText="需要分析扫描件时配置支持图片输入的模型。" /><FormControlLabel control={<Switch checked={isActive} onChange={(_, checked) => setIsActive(checked)} />} label="设为默认配置" /></Stack></DialogContent><DialogActions><Button onClick={() => setOpen(false)}>取消</Button><Button variant="contained" disabled={!name.trim() || !baseUrl.trim() || !textModel.trim() || (!editing && !apiKey) || save.isPending} onClick={() => save.mutate()}>{save.isPending ? '保存中…' : '保存配置'}</Button></DialogActions></Dialog>
      <ConfirmDialog open={Boolean(deleting)} title="删除模型配置？" description={`将删除「${deleting?.name ?? ''}」及其已保存的密钥。历史分析结果仍然保留。`} pending={remove.isPending} onClose={() => setDeleting(null)} onConfirm={() => remove.mutate()} />
    </Stack>
  );
}
