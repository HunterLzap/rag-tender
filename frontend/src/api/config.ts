import client from './client';
import type {
  ApiConfig,
  ApiConfigInput,
  ConfigPreset,
  ConfigType,
  TestConnectionRequest,
  TestConnectionResult,
} from '../types';

/**
 * API configuration module (P0-10).
 */

/** GET /config — fetch all saved API configurations (api_key masked). */
export async function getConfigs(): Promise<ApiConfig[]> {
  const res = await client.get<ApiConfig[]>('/config');
  return res.data;
}

/** 按 config_type 取已保存的活跃配置(脱敏 Key)。
 *  供弹窗编辑模式回填使用 —— 三类模型各自独立,所以分别查询。
 *  找不到返回 null。
 */
export async function getConfigsByType(type: ConfigType): Promise<ApiConfig | null> {
  const all = await getConfigs();
  return (
    all.find((c) => c.config_type === type && c.is_active) ||
    all.find((c) => c.config_type === type) ||
    null
  );
}

/** POST /config — save or update an API configuration. */
export async function saveConfig(data: ApiConfigInput): Promise<ApiConfig> {
  const res = await client.post<ApiConfig>('/config', data);
  return res.data;
}

/** DELETE /config/{id} — delete an API configuration by ID. */
export async function deleteConfig(configId: number): Promise<{ deleted: boolean }> {
  const res = await client.delete<{ deleted: boolean }>(`/config/${configId}`);
  return res.data;
}

/** POST /config/test — test connectivity for a given configuration. */
export async function testConnection(
  data: TestConnectionRequest
): Promise<TestConnectionResult> {
  const res = await client.post<TestConnectionResult>('/config/test', data);
  return res.data;
}

/** GET /config/presets — fetch provider presets (deepseek/siliconflow/zhipu/custom).
 *
 * 后端返回嵌套对象格式：{ presets: { deepseek: { llm: {base_url, model_name} }, siliconflow: {...}, ... } }
 * 前端需要扁平数组：ConfigPreset[]，每条含 provider + config_type + base_url + default_model。
 * 此函数负责格式转换，并做防御性处理（确保返回数组）。
 */
export async function getPresets(): Promise<ConfigPreset[]> {
  type PresetField = { base_url: string; model_name: string };
  type PresetsMap = Record<string, Record<string, PresetField>>;

  const res = await client.get<{ presets: PresetsMap }>('/config/presets');
  const raw = res.data?.presets;

  // 防御性处理：如果后端返回格式异常，返回空数组而不是 undefined（否则 .map 会崩）
  if (!raw || typeof raw !== 'object') {
    console.warn('[getPresets] 后端返回格式异常，已降级为空数组:', res.data);
    return [];
  }

  const labels: Record<string, string> = {
    deepseek: 'DeepSeek',
    siliconflow: '硅基流动',
    zhipu: '智谱',
    custom: '自定义',
  };

  const result: ConfigPreset[] = [];
  for (const [provider, types] of Object.entries(raw)) {
    // custom 供应商没有预设字段，跳过（前端用单独的 MenuItem 处理）
    if (provider === 'custom' || !types || typeof types !== 'object') continue;
    for (const [type, cfg] of Object.entries(types)) {
      if (!cfg || !cfg.base_url) continue;
      result.push({
        provider,
        label: labels[provider] || provider,
        config_type: type as ConfigType,
        base_url: cfg.base_url,
        default_model: cfg.model_name || '',
        models: cfg.model_name ? [cfg.model_name] : [],
      });
    }
  }
  return result;
}
