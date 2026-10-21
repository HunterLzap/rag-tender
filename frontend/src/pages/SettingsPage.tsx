import { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';

interface ModelConfig {
  id: string;
  name: string;
  base_url: string;
  text_model: string;
  vision_model: string | null;
  api_key_masked: string;
}

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState('默认模型');
  const [baseUrl, setBaseUrl] = useState('https://api.openai.com/v1');
  const [apiKey, setApiKey] = useState('');
  const [textModel, setTextModel] = useState('');
  const [visionModel, setVisionModel] = useState('');
  const [message, setMessage] = useState('');
  const [messageSeverity, setMessageSeverity] = useState<'info' | 'success' | 'error'>('info');
  const [testing, setTesting] = useState(false);
  const configs = useQuery({
    queryKey: ['model-configs'],
    queryFn: async () => (await api.get<ModelConfig[]>('/model-configs')).data,
  });
  const save = useMutation({
    mutationFn: async () =>
      (
        await api.post('/model-configs', {
          name,
          base_url: baseUrl,
          api_key: apiKey,
          text_model: textModel,
          vision_model: visionModel || null,
        })
      ).data,
    onSuccess: async () => {
      setMessage('模型配置已加密保存');
      setMessageSeverity('success');
      setApiKey('');
      await queryClient.invalidateQueries({ queryKey: ['model-configs'] });
    },
    onError: (error) => {
      setMessage(error instanceof Error ? error.message : '保存失败');
      setMessageSeverity('error');
    },
  });

  async function testConnection() {
    setTesting(true);
    setMessage('');
    try {
      const response = await api.post<{ success: boolean; latency_ms: number; message: string }>(
        '/model-configs/test',
        {
          base_url: baseUrl,
          api_key: apiKey || undefined,
          config_id: !apiKey ? configs.data?.[0]?.id : undefined,
          model: textModel || configs.data?.[0]?.text_model,
        },
      );
      setMessage(
        response.data.success
          ? `连接成功 · ${response.data.latency_ms}ms`
          : `连接失败 · ${response.data.message}`,
      );
      setMessageSeverity(response.data.success ? 'success' : 'error');
    } catch (error) {
      const detail = (
        error as { response?: { data?: { detail?: string } } }
      ).response?.data?.detail;
      setMessage(detail || (error instanceof Error ? error.message : '测试失败'));
      setMessageSeverity('error');
    } finally {
      setTesting(false);
    }
  }

  return (
    <Stack spacing={3} maxWidth={800}>
      <Box>
        <Typography variant="overline" color="secondary.main">
          MODEL GATEWAY
        </Typography>
        <Typography variant="h3">模型配置</Typography>
      </Box>
      {message && <Alert severity={messageSeverity}>{message}</Alert>}
      <Paper variant="outlined" sx={{ p: 3, bgcolor: 'rgba(255,253,247,.85)' }}>
        <Stack spacing={2}>
          <TextField label="配置名称" value={name} onChange={(event) => setName(event.target.value)} />
          <TextField
            label="OpenAI-compatible Base URL"
            value={baseUrl}
            onChange={(event) => setBaseUrl(event.target.value)}
          />
          <TextField
            label="API Key"
            type="password"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            helperText="只保存加密结果，接口不会返回明文"
          />
          <TextField
            label="文本模型"
            value={textModel}
            onChange={(event) => setTextModel(event.target.value)}
          />
          <TextField
            label="视觉模型（可选）"
            value={visionModel}
            onChange={(event) => setVisionModel(event.target.value)}
          />
          <Stack direction="row" spacing={1}>
            <Button
              variant="contained"
              disabled={!apiKey || !textModel || save.isPending}
              onClick={() => save.mutate()}
            >
              保存配置
            </Button>
            <Button
              variant="outlined"
              disabled={testing || !textModel}
              onClick={() => void testConnection()}
            >
              测试连接
            </Button>
          </Stack>
        </Stack>
      </Paper>
      <Stack spacing={1}>
        {configs.data?.map((config) => (
          <Paper key={config.id} variant="outlined" sx={{ p: 2 }}>
            <Typography fontWeight={600}>{config.name}</Typography>
            <Typography variant="body2" color="text.secondary">
              {config.text_model} · {config.api_key_masked}
            </Typography>
          </Paper>
        ))}
      </Stack>
    </Stack>
  );
}
