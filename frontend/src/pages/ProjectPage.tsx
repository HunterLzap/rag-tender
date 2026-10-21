import { useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import {
  api,
  uploadDocument,
  type AnalysisRun,
  type Bid,
  type DocumentItem,
  type Job,
  type Project,
  type ResponseValue,
} from '../lib/api';
import { formatBytes, formatDate } from '../lib/format';

const roles = [
  ['tender', '招标文件'],
  ['addendum', '补遗/答疑'],
  ['template', '投标模板'],
  ['evidence', '证据文件'],
] as const;

const roleLabel = Object.fromEntries(roles) as Record<string, string>;

export default function ProjectPage() {
  const { projectId = '' } = useParams();
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [role, setRole] = useState('tender');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [bidOpen, setBidOpen] = useState(false);
  const [bidderName, setBidderName] = useState('');
  const [bidDeadline, setBidDeadline] = useState('');
  const [valueOpen, setValueOpen] = useState(false);
  const [valueKey, setValueKey] = useState('');
  const [valueLabel, setValueLabel] = useState('');
  const [valueText, setValueText] = useState('');

  const project = useQuery({
    queryKey: ['project', projectId],
    queryFn: async () => (await api.get<Project>(`/projects/${projectId}`)).data,
  });
  const runtime = useQuery({
    queryKey: ['runtime'],
    queryFn: async () => (await api.get<{ live_model_calls: boolean }>('/health')).data,
  });
  const documents = useQuery({
    queryKey: ['documents', projectId],
    queryFn: async () => (await api.get<DocumentItem[]>(`/projects/${projectId}/documents`)).data,
    refetchInterval: 2500,
  });
  const runs = useQuery({
    queryKey: ['runs', projectId],
    queryFn: async () => (await api.get<AnalysisRun[]>(`/projects/${projectId}/analysis-runs`)).data,
    refetchInterval: 2500,
  });
  const jobs = useQuery({
    queryKey: ['jobs', projectId],
    queryFn: async () => (await api.get<Job[]>(`/projects/${projectId}/jobs`)).data,
    refetchInterval: 1500,
  });
  const bids = useQuery({
    queryKey: ['bids', projectId],
    queryFn: async () => (await api.get<Bid[]>(`/projects/${projectId}/bids`)).data,
  });
  const responseValues = useQuery({
    queryKey: ['response-values', projectId],
    queryFn: async () =>
      (await api.get<ResponseValue[]>(`/projects/${projectId}/response-values`)).data,
  });
  const analyze = useMutation({
    mutationFn: async () =>
      (await api.post<AnalysisRun>(`/projects/${projectId}/analysis-runs`, {})).data,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['runs', projectId] });
    },
    onError: (err) => setError(apiError(err, '分析任务创建失败')),
  });
  const createBid = useMutation({
    mutationFn: async () =>
      (
        await api.post<Bid>(`/projects/${projectId}/bids`, {
          bidder_name: bidderName || project.data?.bidder_name || '投标人',
          bid_deadline: bidDeadline ? new Date(bidDeadline).toISOString() : null,
          as_of_date: bidDeadline ? bidDeadline.slice(0, 10) : null,
        })
      ).data,
    onSuccess: async () => {
      setBidOpen(false);
      setBidDeadline('');
      await queryClient.invalidateQueries({ queryKey: ['bids', projectId] });
      await queryClient.invalidateQueries({ queryKey: ['project', projectId] });
    },
    onError: (err) => setError(apiError(err, '保存标段失败')),
  });
  const createValue = useMutation({
    mutationFn: async () =>
      (
        await api.post<ResponseValue>(`/projects/${projectId}/response-values`, {
          key: valueKey,
          label: valueLabel,
          value_text: valueText,
          source: 'manual',
          review_status: 'verified',
        })
      ).data,
    onSuccess: async () => {
      setValueOpen(false);
      setValueKey('');
      setValueLabel('');
      setValueText('');
      await queryClient.invalidateQueries({ queryKey: ['response-values', projectId] });
    },
    onError: (err) => setError(apiError(err, '保存响应值失败')),
  });

  async function handleUpload(file: File) {
    setError('');
    setUploading(true);
    try {
      await uploadDocument(projectId, role, file);
      await queryClient.invalidateQueries({ queryKey: ['documents', projectId] });
      await queryClient.invalidateQueries({ queryKey: ['jobs', projectId] });
    } catch (err) {
      setError(apiError(err, '上传失败'));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  const parsedDocuments = documents.data?.filter((doc) => doc.current_revision_id) ?? [];
  const activeRun = runs.data?.[0];

  return (
    <Stack spacing={4}>
      <Box>
        <Typography variant="overline" color="secondary.main">
          PROJECT / {project.data?.tender_no || 'NO TENDER NUMBER'}
        </Typography>
        <Typography variant="h3">{project.data?.name || '项目'}</Typography>
      </Box>
      {error && <Alert severity="error">{error}</Alert>}

      <Grid container spacing={3}>
        <Grid item xs={12} lg={8}>
          <Paper variant="outlined" sx={{ p: { xs: 2, md: 3 }, bgcolor: 'rgba(255,253,247,.82)' }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
              <Typography variant="h5">项目文件</Typography>
              <Stack direction="row" spacing={1}>
                <TextField
                  size="small"
                  select
                  value={role}
                  onChange={(event) => setRole(event.target.value)}
                  sx={{ minWidth: 140 }}
                >
                  {roles.map(([value, label]) => (
                    <MenuItem key={value} value={value}>
                      {label}
                    </MenuItem>
                  ))}
                </TextField>
                <Button variant="contained" disabled={uploading} onClick={() => fileRef.current?.click()}>
                  {uploading ? '上传中' : '上传文件'}
                </Button>
              </Stack>
              <input
                ref={fileRef}
                hidden
                type="file"
                accept=".pdf,.doc,.docx,.xlsx,.csv"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void handleUpload(file);
                }}
              />
            </Stack>
            <Stack divider={<Divider flexItem />} spacing={1.5}>
              {documents.data?.length === 0 && (
                <Typography color="text.secondary">上传招标文件后，系统会自动解析原文。</Typography>
              )}
              {documents.data?.map((document) => (
                <Stack
                  key={document.id}
                  direction={{ xs: 'column', sm: 'row' }}
                  justifyContent="space-between"
                  spacing={1}
                >
                  <Box>
                    <Typography>{document.filename}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {roleLabel[document.role] ?? document.role} ·{' '}
                      {document.current_revision_id
                        ? `${document.page_count} 页 · ${formatBytes(document.file_size)}`
                        : '等待解析'}
                      {` · ${formatDate(document.created_at)}`}
                    </Typography>
                  </Box>
                  <Chip
                    size="small"
                    color={document.current_revision_id ? 'success' : 'default'}
                    label={document.current_revision_id ? '可用' : '处理中'}
                  />
                </Stack>
              ))}
            </Stack>
          </Paper>
        </Grid>
        <Grid item xs={12} lg={4}>
          <Paper variant="outlined" sx={{ p: 3, bgcolor: 'rgba(255,253,247,.82)' }}>
            <Typography variant="h5" sx={{ mb: 2 }}>
              分析
            </Typography>
            <Stack spacing={2}>
              <Typography variant="body2" color="text.secondary">
                {parsedDocuments.length
                  ? `已解析 ${parsedDocuments.reduce((sum, doc) => sum + doc.page_count, 0)} 页`
                  : '等待文档解析完成'}
              </Typography>
              {activeRun && (
                <Button component={Link} to={`/runs/${activeRun.id}`} variant="outlined">
                  打开最近分析
                </Button>
              )}
              <Button
                variant="contained"
                disabled={
                  !parsedDocuments.length || analyze.isPending || !runtime.data?.live_model_calls
                }
                onClick={() => analyze.mutate()}
              >
                开始新一轮分析
              </Button>
              {runtime.data && !runtime.data.live_model_calls && (
                <Typography variant="body2" color="text.secondary">
                  离线开发模式：真实分析已关闭，可查看已有结果和编辑填写建议。
                </Typography>
              )}
              {jobs.data?.slice(0, 3).map((job) => (
                <Box key={job.id}>
                  <Typography variant="caption">{job.stage}</Typography>
                  {job.error && <Typography variant="body2" color="error">{job.error}</Typography>}
                  <Divider />
                </Box>
              ))}
            </Stack>
          </Paper>
          <Paper variant="outlined" sx={{ p: 3, mt: 3, bgcolor: 'rgba(255,253,247,.82)' }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center">
              <Typography variant="h5">投标信息</Typography>
              <Button size="small" onClick={() => setBidOpen(true)}>
                设置截止日
              </Button>
            </Stack>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              截止日会用于证书和资质有效期判断，而不是使用当天日期。
            </Typography>
            <Typography sx={{ mt: 2 }}>
              {bids.data?.[0]?.bid_deadline
                ? `截止：${formatDate(bids.data[0].bid_deadline)}`
                : project.data?.bid_deadline
                  ? `截止：${formatDate(project.data.bid_deadline)}`
                  : '尚未设置截止日'}
            </Typography>
          </Paper>
        </Grid>
      </Grid>

      <Paper variant="outlined" sx={{ p: 3, bgcolor: 'rgba(255,253,247,.82)' }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
          <Box>
            <Typography variant="h5">填写响应值</Typography>
            <Typography variant="body2" color="text.secondary">
              这些字段用于投标模板的填写建议，例如投标人名称、报价、工期和联系人。
            </Typography>
          </Box>
          <Button variant="outlined" onClick={() => setValueOpen(true)}>
            新增响应值
          </Button>
        </Stack>
        {responseValues.data?.length === 0 && (
          <Typography color="text.secondary">暂无响应值。</Typography>
        )}
        <Stack divider={<Divider flexItem />} spacing={1.5}>
          {responseValues.data?.map((value) => (
            <Stack
              key={value.id}
              direction={{ xs: 'column', sm: 'row' }}
              justifyContent="space-between"
            >
              <Typography>
                {value.label}{' '}
                <Typography component="span" color="text.secondary">
                  ({value.key})
                </Typography>
              </Typography>
              <Typography>
                {value.value_text || value.value_number || value.value_date || '未填写'}
              </Typography>
            </Stack>
          ))}
        </Stack>
      </Paper>

      <Dialog open={bidOpen} onClose={() => setBidOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>设置投标截止日</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <TextField
              label="投标人名称"
              value={bidderName}
              onChange={(event) => setBidderName(event.target.value)}
            />
            <TextField
              label="投标截止时间"
              type="datetime-local"
              value={bidDeadline}
              onChange={(event) => setBidDeadline(event.target.value)}
              InputLabelProps={{ shrink: true }}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setBidOpen(false)}>取消</Button>
          <Button
            variant="contained"
            disabled={!bidDeadline || createBid.isPending}
            onClick={() => createBid.mutate()}
          >
            保存
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={valueOpen} onClose={() => setValueOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>新增填写响应值</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <TextField
              label="字段标识"
              value={valueKey}
              onChange={(event) => setValueKey(event.target.value)}
              helperText="例如 bidder_name、total_price、delivery_days"
            />
            <TextField
              label="显示名称"
              value={valueLabel}
              onChange={(event) => setValueLabel(event.target.value)}
              helperText="需要与模板中的字段名称匹配，例如 投标人名称"
            />
            <TextField
              label="填写内容"
              multiline
              minRows={2}
              value={valueText}
              onChange={(event) => setValueText(event.target.value)}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setValueOpen(false)}>取消</Button>
          <Button
            variant="contained"
            disabled={!valueKey.trim() || !valueLabel.trim() || createValue.isPending}
            onClick={() => createValue.mutate()}
          >
            保存
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}

function apiError(error: unknown, fallback: string) {
  if (typeof error === 'object' && error && 'response' in error) {
    const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (detail) return detail;
  }
  return error instanceof Error ? error.message : fallback;
}
