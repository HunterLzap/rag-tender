import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  IconButton,
  InputAdornment,
  InputLabel,
  MenuItem,
  Select,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import ClearIcon from '@mui/icons-material/Clear';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import FactCheckOutlinedIcon from '@mui/icons-material/FactCheckOutlined';
import SearchIcon from '@mui/icons-material/Search';

import FileUploader from '../components/FileUploader';
import { StatusTag, type StatusKind } from '../components/StatusTags';
import {
  deleteTender,
  getTenders,
  parseTender,
  uploadTender,
} from '../api/tenders';
import type { Tender, TenderStatus } from '../types';

const TENDER_STATUS_CONFIG: Record<TenderStatus, { label: string; kind: StatusKind }> = {
  pending: { label: '待处理', kind: 'neutral' },
  converting: { label: '转换中', kind: 'info' },
  parsing: { label: '解析中', kind: 'info' },
  extracting: { label: '提取中', kind: 'info' },
  retrying_vlm: { label: 'VLM兜底', kind: 'info' },
  completed: { label: '已完成', kind: 'success' },
  failed: { label: '失败', kind: 'error' },
};

const formatDate = (iso: string | null): string => {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const PROVINCES = [
  '北京', '天津', '上海', '重庆', '河北', '山西', '辽宁', '吉林',
  '黑龙江', '江苏', '浙江', '安徽', '福建', '江西', '山东', '河南',
  '湖北', '湖南', '广东', '海南', '四川', '贵州', '云南', '陕西',
  '甘肃', '青海', '台湾', '内蒙古', '广西', '西藏', '宁夏', '新疆',
  '香港', '澳门',
];

const TenderPage: React.FC = () => {
  const navigate = useNavigate();
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchText, setSearchText] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterRegion, setFilterRegion] = useState('');
  const [deletingTender, setDeletingTender] = useState<Tender | null>(null);
  const [deleting, setDeleting] = useState(false);

  const loadTenders = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await getTenders({
        search: searchText || undefined,
        status: filterStatus || undefined,
        region: filterRegion || undefined,
      });
      setTenders(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载标书列表失败');
    } finally {
      setLoading(false);
    }
  }, [filterRegion, filterStatus, searchText]);

  useEffect(() => {
    void loadTenders();
  }, [loadTenders]);

  useEffect(() => {
    if (!tenders.some((item) => !['completed', 'failed'].includes(item.status))) {
      return;
    }
    const timer = window.setInterval(() => {
      void loadTenders();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [loadTenders, tenders]);

  const handleFilesSelected = useCallback(async (files: File[]) => {
    if (!files.length) return;
    setUploading(true);
    setError(null);
    try {
      const tender = await uploadTender(files[files.length - 1]);
      await parseTender(tender.id);
      await loadTenders();
    } catch (err) {
      setError(err instanceof Error ? err.message : '上传标书失败');
    } finally {
      setUploading(false);
    }
  }, [loadTenders]);

  const handleDelete = useCallback(async () => {
    if (!deletingTender) return;
    setDeleting(true);
    try {
      await deleteTender(deletingTender.id);
      setDeletingTender(null);
      await loadTenders();
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败');
    } finally {
      setDeleting(false);
    }
  }, [deletingTender, loadTenders]);

  return (
    <Box>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Box sx={{ border: '1px solid #EDE7F6', backgroundColor: '#FFF' }}>
        <Box sx={{ p: 3, borderBottom: '1px solid #F0ECF7' }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>
            上传标书
          </Typography>
          <FileUploader
            accept=".pdf,.docx,.doc"
            multiple={false}
            onFilesSelected={handleFilesSelected}
            uploading={uploading}
          />
        </Box>

        <Box
          sx={{
            p: 2,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 1,
            flexWrap: 'wrap',
          }}
        >
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
            标书列表
          </Typography>
          {(searchText || filterStatus || filterRegion) && (
            <Button
              size="small"
              startIcon={<ClearIcon />}
              onClick={() => {
                setSearchText('');
                setFilterStatus('');
                setFilterRegion('');
              }}
              sx={{ color: '#777' }}
            >
              清除筛选
            </Button>
          )}
        </Box>

        <Box sx={{ px: 2, pb: 1.5, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          <TextField
            size="small"
            placeholder="搜索标书标题/文件名…"
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon sx={{ fontSize: 18, color: '#AAA' }} />
                </InputAdornment>
              ),
            }}
            sx={{ minWidth: 250, '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
          />
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>状态</InputLabel>
            <Select
              value={filterStatus}
              label="状态"
              onChange={(event) => setFilterStatus(event.target.value)}
              sx={{ borderRadius: 0 }}
            >
              <MenuItem value="">全部</MenuItem>
              <MenuItem value="pending">待处理</MenuItem>
              <MenuItem value="converting">转换中</MenuItem>
              <MenuItem value="parsing">解析中</MenuItem>
              <MenuItem value="extracting">提取中</MenuItem>
              <MenuItem value="completed">已完成</MenuItem>
              <MenuItem value="failed">失败</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel>地区</InputLabel>
            <Select
              value={filterRegion}
              label="地区"
              onChange={(event) => setFilterRegion(event.target.value)}
              sx={{ borderRadius: 0 }}
            >
              <MenuItem value="">全部</MenuItem>
              {PROVINCES.map((province) => (
                <MenuItem key={province} value={province}>
                  {province}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 5 }}>
            <CircularProgress sx={{ color: '#7C4DFF' }} />
          </Box>
        ) : tenders.length === 0 ? (
          <Typography sx={{ py: 5, textAlign: 'center', color: '#999' }}>
            暂无标书
          </Typography>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ backgroundColor: '#F9F7FF' }}>
                  <TableCell sx={{ fontWeight: 700 }}>文件名</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>地区</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>解析状态</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>页数</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>创建时间</TableCell>
                  <TableCell sx={{ fontWeight: 700, width: 240, whiteSpace: 'nowrap' }}>
                    操作
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {tenders.map((tender) => {
                  const statusConfig = TENDER_STATUS_CONFIG[tender.status];

                  return (
                    <TableRow
                      key={tender.id}
                      hover
                      className={tenders.length >= 15 ? 'zebra' : undefined}
                    >
                      <TableCell>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                          {tender.title || tender.filename}
                        </Typography>
                        {tender.procurement_type && (
                          <Typography variant="caption" sx={{ color: '#888' }}>
                            {tender.procurement_type}
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell sx={{ color: '#666' }}>
                        {tender.region || '—'}
                      </TableCell>
                      <TableCell>
                        <StatusTag kind={statusConfig.kind} label={statusConfig.label} />
                      </TableCell>
                      <TableCell sx={{ color: '#666' }}>
                        {tender.total_pages || '—'}
                      </TableCell>
                      <TableCell sx={{ color: '#666' }}>
                        {formatDate(tender.upload_time)}
                      </TableCell>
                      <TableCell sx={{ width: 240, whiteSpace: 'nowrap' }}>
                        <Box
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 1,
                            flexWrap: 'nowrap',
                          }}
                        >
                          {tender.status === 'completed' && (
                            <Tooltip title="核对结果">
                              <Button
                                size="small"
                                startIcon={<FactCheckOutlinedIcon />}
                                onClick={() =>
                                  navigate(`/tenders/${tender.id}/review`)
                                }
                                sx={{
                                  color: '#7C4DFF',
                                  whiteSpace: 'nowrap',
                                  flexShrink: 0,
                                }}
                              >
                                核对结果
                              </Button>
                            </Tooltip>
                          )}
                          {tender.status === 'completed' && (
                            <Box
                              sx={{
                                width: '1px',
                                height: 22,
                                flex: '0 0 1px',
                                backgroundColor: 'divider',
                              }}
                            />
                          )}
                          <Tooltip title="删除">
                            <IconButton
                              size="small"
                              onClick={() => setDeletingTender(tender)}
                              sx={{
                                color: 'text.secondary',
                                flexShrink: 0,
                                '&:hover': { color: 'error.main' },
                              }}
                            >
                              <DeleteOutlineIcon sx={{ fontSize: 18 }} />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Box>

      <Dialog
        open={Boolean(deletingTender)}
        onClose={() => setDeletingTender(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>确认删除</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ color: '#666' }}>
            确定删除标书“{deletingTender?.title || deletingTender?.filename}”吗？
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeletingTender(null)}>取消</Button>
          <Button
            variant="contained"
            color="error"
            disabled={deleting}
            onClick={() => void handleDelete()}
          >
            {deleting ? <CircularProgress size={18} color="inherit" /> : '删除'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default TenderPage;
