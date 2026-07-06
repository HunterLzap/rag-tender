import React, { useState, useEffect, useCallback } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  TextField,
  IconButton,
  Typography,
  Alert,
  CircularProgress,
  Divider,
  Chip,
} from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined';
import { getConfigs, saveConfig, testConnection } from '../api/config';
import type { ApiConfig, ConfigType, TestConnectionResult } from '../types';

interface ApiConfigDialogProps {
  open: boolean;
  onClose: () => void;
  editConfig?: ApiConfig | null;
}

interface ModelSectionState {
  base_url: string;
  api_key: string;
  show_key: boolean;
  masked_key: string;
  model: string;
}

const EMPTY_SECTION: ModelSectionState = {
  base_url: '',
  api_key: '',
  show_key: false,
  masked_key: '',
  model: '',
};

/** 三段式的元信息(纯文字,不用 emoji) */
const SECTION_META: Record<
  ConfigType,
  { title: string; color: string; bg: string; placeholder_model: string; placeholder_url: string }
> = {
  llm: {
    title: '对话模型 (LLM)',
    color: '#1565C0',
    bg: '#E3F2FD',
    placeholder_model: 'deepseek-chat',
    placeholder_url: 'https://api.deepseek.com/v1',
  },
  embedding: {
    title: '向量模型 (Embedding)',
    color: '#6A1B9A',
    bg: '#F3E5F5',
    placeholder_model: 'text-embedding-v3',
    placeholder_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  },
  vision: {
    title: '视觉模型 (Vision)',
    color: '#E65100',
    bg: '#FFF3E0',
    placeholder_model: 'qwen-vl-max',
    placeholder_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  },
};

const TYPE_ORDER: ConfigType[] = ['llm', 'embedding', 'vision'];

const ApiConfigDialog: React.FC<ApiConfigDialogProps> = ({ open, onClose, editConfig }) => {
  const [sections, setSections] = useState<Record<ConfigType, ModelSectionState>>({
    llm: { ...EMPTY_SECTION },
    embedding: { ...EMPTY_SECTION },
    vision: { ...EMPTY_SECTION },
  });
  const [testResults, setTestResults] = useState<Record<ConfigType, TestConnectionResult | null>>({
    llm: null,
    embedding: null,
    vision: null,
  });
  const [testing, setTesting] = useState<Record<ConfigType, boolean>>({
    llm: false,
    embedding: false,
    vision: false,
  });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let mounted = true;

    const init = async () => {
      setLoading(true);
      setError(null);
      setTestResults({ llm: null, embedding: null, vision: null });
      try {
        const allConfigs = await getConfigs();
        if (!mounted) return;

        const nextSections = { ...sections };
        for (const t of TYPE_ORDER) {
          const cfg =
            allConfigs.find((c) => c.config_type === t && c.is_active) ||
            allConfigs.find((c) => c.config_type === t);
          nextSections[t] = {
            base_url: cfg?.base_url || '',
            api_key: '',
            show_key: false,
            masked_key: cfg?.api_key || '',
            model: cfg?.model_name || '',
          };
        }
        setSections(nextSections);
      } catch (err) {
        if (mounted) setError(err instanceof Error ? err.message : '加载失败');
      } finally {
        if (mounted) setLoading(false);
      }
    };

    init();
    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const handleFieldChange = useCallback(
    (type: ConfigType, field: keyof ModelSectionState, value: string | boolean) => {
      setSections((prev) => ({
        ...prev,
        [type]: { ...prev[type], [field]: value },
      }));
    },
    []
  );

  const handleTest = useCallback(
    async (type: ConfigType) => {
      const s = sections[type];
      if (!s.base_url) {
        setError(`请先填写 ${SECTION_META[type].title} 的 Base URL`);
        return;
      }
      if (!s.api_key && !s.masked_key) {
        setError(`请输入 ${SECTION_META[type].title} 的 API Key`);
        return;
      }
      if (!s.model) {
        setError(`请输入 ${SECTION_META[type].title} 的模型名称`);
        return;
      }
      setError(null);
      setTesting((p) => ({ ...p, [type]: true }));
      try {
        const result = await testConnection({
          config_type: type,
          base_url: s.base_url,
          api_key: s.api_key,
          model_name: s.model,
        });
        setTestResults((p) => ({ ...p, [type]: result }));
      } catch (err) {
        setTestResults((p) => ({
          ...p,
          [type]: {
            success: false,
            latency_ms: 0,
            message: err instanceof Error ? err.message : '测试失败',
          },
        }));
      } finally {
        setTesting((p) => ({ ...p, [type]: false }));
      }
    },
    [sections]
  );

  const inferProvider = (base_url: string, model: string): string => {
    const u = (base_url + ' ' + model).toLowerCase();
    if (u.includes('deepseek')) return 'deepseek';
    if (u.includes('siliconflow')) return 'siliconflow';
    if (u.includes('bigmodel') || u.includes('zhipu')) return 'zhipu';
    if (u.includes('dashscope') || u.includes('aliyun') || model.toLowerCase().includes('qwen')) {
      return 'qwen';
    }
    return 'custom';
  };

  const handleSave = useCallback(async () => {
    setError(null);
    const toSave: ConfigType[] = TYPE_ORDER.filter((t) => sections[t].base_url.trim());
    if (toSave.length === 0) {
      setError('请至少填写一类模型的配置');
      return;
    }

    setSaving(true);
    try {
      await Promise.all(
        toSave.map((t) => {
          const s = sections[t];
          return saveConfig({
            config_type: t,
            provider: inferProvider(s.base_url, s.model),
            base_url: s.base_url,
            api_key: s.api_key,
            model_name: s.model,
            is_active: true,
          });
        })
      );
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败');
    } finally {
      setSaving(false);
    }
  }, [sections, onClose]);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ color: '#7C4DFF', fontWeight: 600, pb: 1 }}>
        {editConfig ? '编辑 API 配置' : 'API 配置'}
      </DialogTitle>

      <DialogContent dividers sx={{ pt: 2 }}>
        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress sx={{ color: '#7C4DFF' }} />
          </Box>
        )}

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {!loading && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            <Typography variant="caption" sx={{ color: '#999', mb: 2 }}>
              三类模型可来自不同供应商，各自填写 Base URL 和 API Key。未填写的类型不会保存。
            </Typography>

            {TYPE_ORDER.map((type, idx) => {
              const meta = SECTION_META[type];
              const s = sections[type];
              const result = testResults[type];
              const isTesting = testing[type];
              const hasSavedKey = !!s.masked_key && s.masked_key !== '****';

              const section = (
                <Box key={type} sx={{ mb: idx < TYPE_ORDER.length - 1 ? 2 : 0 }}>
                  {/* 段标题 —— 带颜色 chip */}
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                    <Chip
                      size="small"
                      label={meta.title}
                      sx={{
                        height: 22,
                        fontSize: 11,
                        fontWeight: 600,
                        bgcolor: meta.bg,
                        color: meta.color,
                      }}
                    />
                    {hasSavedKey && (
                      <Typography variant="caption" sx={{ color: '#9E9E9E' }}>
                        已保存 {s.masked_key}
                      </Typography>
                    )}
                  </Box>

                  {/* 第一行:Base URL + Model 并排 */}
                  <Box sx={{ display: 'flex', gap: 1.5, mb: 1 }}>
                    <TextField
                      size="small"
                      label="Base URL"
                      value={s.base_url}
                      onChange={(e) => handleFieldChange(type, 'base_url', e.target.value)}
                      placeholder={meta.placeholder_url}
                      sx={{ flex: 1 }}
                    />
                    <TextField
                      size="small"
                      label="模型名称"
                      value={s.model}
                      onChange={(e) => handleFieldChange(type, 'model', e.target.value)}
                      placeholder={meta.placeholder_model}
                      sx={{ flex: 1 }}
                    />
                  </Box>

                  {/* 第二行:API Key + 测试按钮 */}
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                    <TextField
                      size="small"
                      label="API Key"
                      type={s.show_key ? 'text' : 'password'}
                      value={s.api_key}
                      onChange={(e) => handleFieldChange(type, 'api_key', e.target.value)}
                      placeholder={hasSavedKey ? '留空保持原有 Key' : '输入 API Key'}
                      sx={{ flex: 1 }}
                      InputProps={{
                        endAdornment: (
                          <IconButton
                            size="small"
                            onClick={() => handleFieldChange(type, 'show_key', !s.show_key)}
                            edge="end"
                          >
                            {s.show_key ? (
                              <VisibilityOffIcon sx={{ fontSize: 18 }} />
                            ) : (
                              <VisibilityIcon sx={{ fontSize: 18 }} />
                            )}
                          </IconButton>
                        ),
                      }}
                    />
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => handleTest(type)}
                      disabled={isTesting || !s.base_url || (!s.api_key && !s.masked_key) || !s.model}
                      startIcon={
                        isTesting ? (
                          <CircularProgress size={12} color="inherit" />
                        ) : (
                          <SmartToyOutlinedIcon sx={{ fontSize: 16 }} />
                        )
                      }
                      sx={{
                        minWidth: 100,
                        height: 40,
                        borderColor: meta.color,
                        color: meta.color,
                        fontSize: 12,
                        whiteSpace: 'nowrap',
                        '&:hover': { backgroundColor: `${meta.bg}` },
                        '&.Mui-disabled': { borderColor: '#DDD', color: '#BBB' },
                      }}
                    >
                      {isTesting ? '测试中' : '测试连接'}
                    </Button>
                  </Box>

                  {/* 测试结果 */}
                  {result && (
                    <Box
                      sx={{
                        mt: 1,
                        p: 1,
                        borderRadius: 1,
                        backgroundColor: result.success ? '#E8F5E9' : '#FFEBEE',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1,
                      }}
                    >
                      {result.success ? (
                        <CheckCircleIcon sx={{ color: '#4CAF50', fontSize: 16 }} />
                      ) : (
                        <ErrorIcon sx={{ color: '#EF5350', fontSize: 16 }} />
                      )}
                      <Typography variant="caption" sx={{ color: '#333' }}>
                        {result.success
                          ? `连接成功 · 延迟 ${result.latency_ms}ms`
                          : `连接失败: ${result.message}`}
                      </Typography>
                    </Box>
                  )}
                </Box>
              );

              // 段之间加分割线
              if (idx < TYPE_ORDER.length - 1) {
                return (
                  <Box key={type}>
                    {section}
                    <Divider sx={{ mb: 2, borderColor: '#F0F0F0' }} />
                  </Box>
                );
              }
              return section;
            })}
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={onClose} sx={{ color: '#666' }}>
          取消
        </Button>
        <Button
          variant="contained"
          onClick={handleSave}
          disabled={saving}
          sx={{
            backgroundColor: '#7C4DFF',
            '&:hover': { backgroundColor: '#651FFF' },
            '&.Mui-disabled': { backgroundColor: '#BDBDBD' },
          }}
        >
          {saving ? <CircularProgress size={18} color="inherit" /> : '保存'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ApiConfigDialog;
