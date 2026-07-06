import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  Typography,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Grid,
  Chip,
  IconButton,
  Tooltip,
  CircularProgress,
} from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import InfoIcon from '@mui/icons-material/Info';
import FolderIcon from '@mui/icons-material/Folder';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import EditIcon from '@mui/icons-material/Edit';
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined';
import PowerSettingsNewIcon from '@mui/icons-material/PowerSettingsNew';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import ApiConfigDialog from '../components/ApiConfigDialog';
import { getConfigs, deleteConfig, saveConfig, testConnection } from '../api/config';
import type { ApiConfig } from '../types';

/** 供应商显示名 */
const PROVIDER_LABELS: Record<string, string> = {
  deepseek: 'DeepSeek',
  siliconflow: '硅基流动',
  zhipu: '智谱 AI',
  qwen: '通义千问 (DashScope)',
  custom: '自定义',
};

/** ConfigType 显示标签 */
const TYPE_META: Record<string, { label: string; color: string; bg: string }> = {
  llm: { label: '对话', color: '#1565C0', bg: '#E3F2FD' },
  embedding: { label: '向量', color: '#6A1B9A', bg: '#F3E5F5' },
  vision: { label: '视觉', color: '#E65100', bg: '#FFF3E0' },
};

const TYPE_ORDER: string[] = ['llm', 'embedding', 'vision'];

/**
 * Settings page (route: /settings).
 *
 * 参考 DashScope 风格：
 * - API 配置区：卡片列表，每张卡片显示一个配置组（名称+来源+3个模型+Key+URL）
 * - 点击编辑打开统一表单弹窗
 * - 支持多配置组（未来可扩展）
 * - 数据目录、关于、缓存管理等辅助功能
 */
const SettingsPage: React.FC = () => {
  const [configOpen, setConfigOpen] = useState(false);
  const [editConfig, setEditConfig] = useState<ApiConfig | null>(null);
  const [configs, setConfigs] = useState<ApiConfig[]>([]);
  const [cacheDialogOpen, setCacheDialogOpen] = useState(false);
  const [cacheCleared, setCacheCleared] = useState(false);
  const [testingGroup, setTestingGroup] = useState<string | null>(null);
  const [groupTestResults, setGroupTestResults] = useState<Record<string, { success: boolean; message: string } | null>>({});

  const loadConfigs = useCallback(async () => {
    try {
      const list = await getConfigs();
      setConfigs(list);
    } catch {
      // 静默失败
    }
  }, []);

  useEffect(() => {
    loadConfigs();
  }, [loadConfigs]);

  /** 按 base_url 分组:同一 URL 的三类模型归为一个配置组 */
  const configGroups = useMemo(() => {
    const map = new Map<string, ApiConfig[]>();
    for (const cfg of configs) {
      const key = cfg.base_url || '__unsaved__';
      const group = map.get(key) || [];
      group.push(cfg);
      map.set(key, group);
    }
    return Array.from(map.entries());
  }, [configs]);

  /** 从一组配置推断 provider 标签 */
  const getGroupProvider = (group: ApiConfig[]): string => {
    const cfg = group.find((c) => c.provider && c.provider !== 'custom');
    return cfg?.provider || 'custom';
  };

  /** 从一组配置获取 base_url */
  const getGroupBaseUrl = (group: ApiConfig[]): string => {
    return group[0]?.base_url || '';
  };

  /** 从一组配置获取 masked_key */
  const getGroupKey = (group: ApiConfig[]): string => {
    for (const t of TYPE_ORDER) {
      const cfg = group.find((c) => c.config_type === t);
      if (cfg?.api_key && cfg.api_key !== '****') return cfg.api_key;
    }
    return '';
  };

  /** 整个配置组是否全部启用 */
  const isGroupActive = (group: ApiConfig[]): boolean => {
    return group.some((c) => c.is_active);
  };

  const handleAddNew = useCallback(() => {
    setEditConfig(null);
    setConfigOpen(true);
  }, []);

  const handleEdit = useCallback((cfg: ApiConfig) => {
    setEditConfig(cfg);
    setConfigOpen(true);
  }, []);

  const handleCloseConfig = useCallback(() => {
    setConfigOpen(false);
    setEditConfig(null);
    setTimeout(loadConfigs, 300);
  }, [loadConfigs]);

  /** 删除整个配置组 */
  const handleDeleteGroup = useCallback(async (group: ApiConfig[]) => {
    try {
      await Promise.all(group.map((c) => deleteConfig(c.id)));
      await loadConfigs();
    } catch {
      // 静默处理
    }
  }, [loadConfigs]);

  /** 开关整个配置组 */
  const handleToggleGroup = useCallback(async (group: ApiConfig[]) => {
    const newActive = !isGroupActive(group);
    try {
      await Promise.all(
        group.map((c) =>
          saveConfig({
            config_type: c.config_type,
            provider: c.provider,
            base_url: c.base_url,
            api_key: '',
            model_name: c.model_name,
            is_active: newActive,
          })
        )
      );
      await loadConfigs();
    } catch {
      // 静默处理
    }
  }, [loadConfigs]);

  /** 测试整个配置组连接(逐个测试,汇总结果) */
  const handleTestGroup = useCallback(async (group: ApiConfig[]) => {
    const baseUrl = getGroupBaseUrl(group);
    setTestingGroup(baseUrl);
    setGroupTestResults((prev) => ({ ...prev, [baseUrl]: null }));
    const results: string[] = [];
    let allOk = true;
    for (const cfg of group) {
      try {
        const r = await testConnection({
          config_type: cfg.config_type,
          base_url: cfg.base_url,
          api_key: '',
          model_name: cfg.model_name,
        });
        const meta = TYPE_META[cfg.config_type] || { label: cfg.config_type };
        if (r.success) {
          results.push(`${meta.label} ✓`);
        } else {
          results.push(`${meta.label} ✗ ${r.message}`);
          allOk = false;
        }
      } catch (err: any) {
        const meta = TYPE_META[cfg.config_type] || { label: cfg.config_type };
        results.push(`${meta.label} ✗ ${err?.message || '请求失败'}`);
        allOk = false;
      }
    }
    setGroupTestResults((prev) => ({
      ...prev,
      [baseUrl]: { success: allOk, message: results.join('  ') },
    }));
    setTestingGroup(null);
  }, []);

  /** 清除缓存 */
  const handleClearCache = useCallback(() => {
    try {
      localStorage.clear();
      setCacheCleared(true);
      setCacheDialogOpen(false);
    } catch {
      // ignore
    }
  }, []);

  return (
    <Box>
      <Grid container spacing={3}>
        {/* API Configuration section */}
        <Grid item xs={12}>
          <Box sx={{ p: 3, backgroundColor: '#FFF', border: '1px solid #EDE7F6', borderRadius: 0 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <SettingsIcon sx={{ color: '#7C4DFF' }} />
                <Typography variant="h6" sx={{ color: '#333', fontWeight: 600 }}>API 配置</Typography>
              </Box>
              <Button variant="outlined" size="small" startIcon={<AddCircleOutlineIcon />} onClick={handleAddNew}
                sx={{ borderColor: '#7C4DFF', color: '#7C4DFF', '&:hover': { borderColor: '#651FFF', backgroundColor: '#EDE7F6' } }}>
                添加配置
              </Button>
            </Box>

            {configs.length === 0 ? (
              <Box sx={{ textAlign: 'center', py: 4, color: '#999' }}>
                <Typography variant="body2">暂无已保存的配置</Typography>
                <Typography variant="caption">点击上方「添加配置」按钮开始设置</Typography>
              </Box>
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {configGroups.map(([baseUrl, group]) => {
                  const firstConfig = group[0];
                  if (!firstConfig) return null;
                  const provider = getGroupProvider(group);
                  const providerLabel = PROVIDER_LABELS[provider] || provider;
                  const active = isGroupActive(group);
                  const maskedKey = getGroupKey(group);
                  const isTesting = testingGroup === baseUrl;
                  const testResult = groupTestResults[baseUrl];

                  return (
                    <Box key={baseUrl}
                      sx={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        px: 2, py: 1.5, border: '1px solid #EDE7F6', borderRadius: 0,
                        '&:hover': { borderColor: '#D1C4E9' }, transition: 'border-color 0.2s', gap: 2,
                      }}
                    >
                      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5, flex: 1, minWidth: 0 }}>
                        <Box sx={{ width: 36, height: 36, borderRadius: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#EDE7F6', color: '#7C4DFF', flexShrink: 0 }}>
                          <SmartToyOutlinedIcon sx={{ fontSize: 20 }} />
                        </Box>
                        <Box sx={{ flex: 1, minWidth: 0 }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap' }}>
                            <Typography variant="body2" sx={{ fontWeight: 600, color: '#333' }}>API 配置</Typography>
                            {active && <Chip size="small" label="默认" sx={{ height: 18, fontSize: 10, bgcolor: '#E8F5E9', color: '#2E7D32', fontWeight: 500 }} />}
                            <Chip size="small" label={providerLabel}
                              sx={{ height: 18, fontSize: 10, bgcolor: '#F5F5F5', color: '#616161', border: '1px solid #E0E0E0', fontWeight: 500 }} />
                          </Box>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.5, flexWrap: 'wrap' }}>
                            {TYPE_ORDER.map((t) => {
                              const cfg = group.find((c) => c.config_type === t);
                              if (!cfg || !cfg.model_name) return null;
                              const meta = TYPE_META[t];
                              return <Chip key={t} size="small" label={`${meta.label}: ${cfg.model_name}`}
                                sx={{ height: 20, fontSize: 10, bgcolor: meta.bg, color: meta.color, fontWeight: 500 }} />;
                            })}
                          </Box>
                          <Typography variant="caption" sx={{ color: '#999', mt: 0.25, display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 460 }}>
                            {baseUrl}{maskedKey && <Typography component="span" variant="caption" sx={{ fontFamily: 'monospace', color: '#BDBDBD', ml: 0.5 }}>· {maskedKey}</Typography>}
                          </Typography>
                          {testResult && testingGroup === null && (
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.5 }}>
                              {testResult.success ? <CheckCircleIcon sx={{ fontSize: 14, color: '#4CAF50' }} /> : <ErrorIcon sx={{ fontSize: 14, color: '#EF5350' }} />}
                              <Typography variant="caption" sx={{ color: testResult.success ? '#4CAF50' : '#EF5350' }}>{testResult.message}</Typography>
                            </Box>
                          )}
                        </Box>
                      </Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25, flexShrink: 0 }}>
                        <Tooltip title="编辑" arrow><IconButton size="small" onClick={() => handleEdit(firstConfig)} sx={{ color: '#999', '&:hover': { color: '#7C4DFF' } }}><EditIcon sx={{ fontSize: 18 }} /></IconButton></Tooltip>
                        <Tooltip title="测试连接" arrow><IconButton size="small" onClick={() => handleTestGroup(group)} disabled={isTesting} sx={{ color: '#999', '&:hover': { color: '#1565C0' } }}>
                          {isTesting ? <CircularProgress size={16} /> : <SmartToyOutlinedIcon sx={{ fontSize: 18 }} />}</IconButton></Tooltip>
                        <Tooltip title={active ? '停用' : '启用'} arrow><IconButton size="small" onClick={() => handleToggleGroup(group)}
                          sx={{ color: active ? '#4CAF50' : '#BDBDBD' }}><PowerSettingsNewIcon sx={{ fontSize: 18 }} /></IconButton></Tooltip>
                        <Tooltip title={active ? '默认配置不可删除' : '删除'} arrow><span>
                          <IconButton size="small" onClick={() => handleDeleteGroup(group)} disabled={active}
                            sx={{ color: '#EF5350', '&.Mui-disabled': { opacity: 0.4 } }}><DeleteOutlineIcon sx={{ fontSize: 18 }} /></IconButton></span></Tooltip>
                      </Box>
                    </Box>
                  );
                })}
              </Box>
            )}
          </Box>
        </Grid>

        {/* Info bar — compact single row */}
        <Grid item xs={12}>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <Box sx={{ flex: 1, minWidth: 200, p: 2, border: '1px solid #EDE7F6', borderRadius: 0 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <FolderIcon sx={{ color: '#7C4DFF', fontSize: 20 }} />
                <Typography variant="body2" sx={{ fontWeight: 600, color: '#333' }}>数据目录</Typography>
              </Box>
              <Typography variant="caption" sx={{ fontFamily: 'monospace', color: '#7C4DFF', wordBreak: 'break-all' }}>
                D:\projects\RAG-Tender Assistant\data\
              </Typography>
            </Box>
            <Box sx={{ flex: 1, minWidth: 200, p: 2, border: '1px solid #EDE7F6', borderRadius: 0 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <InfoIcon sx={{ color: '#7C4DFF', fontSize: 20 }} />
                <Typography variant="body2" sx={{ fontWeight: 600, color: '#333' }}>关于</Typography>
              </Box>
              <Typography variant="caption" sx={{ color: '#666' }}>RAG-Tender Assistant v1.0.0 · React 18 + FastAPI + SQLite</Typography>
            </Box>
            <Box sx={{ flex: 1, minWidth: 200, p: 2, border: '1px solid #EDE7F6', borderRadius: 0 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <DeleteOutlineIcon sx={{ color: '#7C4DFF', fontSize: 20 }} />
                <Typography variant="body2" sx={{ fontWeight: 600, color: '#333' }}>缓存管理</Typography>
              </Box>
              {cacheCleared ? (
                <Typography variant="caption" sx={{ color: '#4CAF50' }}>缓存已清除</Typography>
              ) : (
                <Button size="small" variant="outlined" onClick={() => setCacheDialogOpen(true)}
                  sx={{ borderColor: '#EF5350', color: '#EF5350', fontSize: 12, '&:hover': { borderColor: '#D32F2F', backgroundColor: '#FFEBEE' } }}>
                  清除缓存
                </Button>
              )}
            </Box>
          </Box>
        </Grid>
      </Grid>

      {/* API configuration dialog */}
      <ApiConfigDialog
        open={configOpen}
        onClose={handleCloseConfig}
        editConfig={editConfig}
      />

      {/* Clear cache confirmation dialog */}
      <Dialog
        open={cacheDialogOpen}
        onClose={() => setCacheDialogOpen(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle sx={{ color: '#333', fontWeight: 600 }}>确认清除缓存</DialogTitle>
        <DialogContent>
          <Typography variant="body1" sx={{ color: '#666' }}>
            确定要清除浏览器本地缓存吗？此操作不会删除已上传的文件和数据。
          </Typography>
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setCacheDialogOpen(false)} sx={{ color: '#666' }}>
            取消
          </Button>
          <Button
            variant="contained"
            onClick={handleClearCache}
            sx={{
              backgroundColor: '#EF5350',
              '&:hover': { backgroundColor: '#D32F2F' },
            }}
          >
            确认清除
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default SettingsPage;
