import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Grid,
  Paper,
  Typography,
  Box,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  CircularProgress,
  Alert,
} from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import LibraryBooksIcon from '@mui/icons-material/LibraryBooks';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import { StatusTag, type StatusKind } from '../components/StatusTags';
import { colors } from '../theme';
import { getTenders } from '../api/tenders';
import { getQualifications } from '../api/knowledge';
import { getMatchResults } from '../api/match';
import type { Tender } from '../types';

/** Format an ISO datetime string to a localized display string. */
const formatDate = (iso: string | null): string => {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

interface QuickEntry {
  title: string;
  description: string;
  path: string;
  icon: React.ReactNode;
}

const QUICK_ENTRIES: QuickEntry[] = [
  {
    title: '上传标书',
    description: '上传并解析标书文件',
    path: '/tenders',
    icon: <UploadFileIcon sx={{ fontSize: 40 }} />,
  },
  {
    title: '资质库管理',
    description: '管理企业资质与文件',
    path: '/knowledge',
    icon: <LibraryBooksIcon sx={{ fontSize: 40 }} />,
  },
  {
    title: '查看匹配',
    description: '标书要求与资质匹配',
    path: '/match',
    icon: <CompareArrowsIcon sx={{ fontSize: 40 }} />,
  },
];

const TENDER_STATUS_LABELS: Record<Tender['status'], string> = {
  pending: '待处理',
  converting: '转换中',
  parsing: '解析中',
  extracting: '提取中',
  retrying_vlm: '重试识别中',
  completed: '已完成',
  failed: '失败',
};

const TENDER_STATUS_KIND: Record<Tender['status'], StatusKind> = {
  pending: 'neutral',
  converting: 'info',
  parsing: 'info',
  extracting: 'info',
  retrying_vlm: 'info',
  completed: 'success',
  failed: 'error',
};

interface DashboardStats {
  tenderCount: number;
  qualCount: number;
  pendingMatchCount: number;
}

/**
 * Dashboard page (route: /).
 * Shows a welcome banner, quick-entry cards, statistics, and a recent tenders table.
 */
const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [stats, setStats] = useState<DashboardStats>({
    tenderCount: 0,
    qualCount: 0,
    pendingMatchCount: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [tenderList, qualList] = await Promise.all([
        getTenders(),
        getQualifications(),
      ]);
      setTenders(tenderList);

      // Count pending (needs_review) matches across the most recent
      // completed tenders (capped at 20 to limit API calls).
      const completedTenders = tenderList
        .filter((t) => t.status === 'completed')
        .slice(0, 20);

      const matchResponses = await Promise.allSettled(
        completedTenders.map((t) => getMatchResults(t.id))
      );

      let pendingCount = 0;
      matchResponses.forEach((response) => {
        if (response.status === 'fulfilled') {
          pendingCount += response.value.filter(
            (r) => r.match_status === 'needs_review'
          ).length;
        }
      });

      setStats({
        tenderCount: tenderList.length,
        qualCount: qualList.length,
        pendingMatchCount: pendingCount,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载数据失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress sx={{ color: '#7C4DFF' }} />
      </Box>
    );
  }

  const recentTenders = tenders.slice(0, 5);

  return (
    <Box>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Box sx={{ mb: 3 }}>
        <Typography variant="h2">
          资质通
        </Typography>
      </Box>

      {/* Statistics cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={4}>
          <Card
            sx={{
              p: 2.5,
              backgroundColor: colors.surface,
              border: `1px solid ${colors.divider}`,
              borderRadius: '10px',
              boxShadow: 'none',
            }}
          >
            <Typography variant="subtitle1" color="text.secondary">
              标书总数
            </Typography>
            <Typography variant="h2" component="p" sx={{ color: 'primary.main', mt: 0.5 }}>
              {stats.tenderCount}
            </Typography>
          </Card>
        </Grid>
        <Grid item xs={12} sm={4}>
          <Card
            sx={{
              p: 2.5,
              backgroundColor: colors.surface,
              border: `1px solid ${colors.divider}`,
              borderRadius: '10px',
              boxShadow: 'none',
            }}
          >
            <Typography variant="subtitle1" color="text.secondary">
              资质总数
            </Typography>
            <Typography variant="h2" component="p" sx={{ color: 'primary.main', mt: 0.5 }}>
              {stats.qualCount}
            </Typography>
          </Card>
        </Grid>
        <Grid item xs={12} sm={4}>
          <Card
            sx={{
              p: 2.5,
              backgroundColor: colors.surface,
              border: `1px solid ${colors.divider}`,
              borderRadius: '10px',
              boxShadow: 'none',
            }}
          >
            <Typography variant="subtitle1" color="text.secondary">
              待处理匹配
            </Typography>
            <Typography variant="h2" component="p" sx={{ color: 'text.primary', mt: 0.5 }}>
              {stats.pendingMatchCount}
            </Typography>
          </Card>
        </Grid>
      </Grid>

      {/* Quick-entry cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        {QUICK_ENTRIES.map((entry) => (
          <Grid item xs={12} sm={4} key={entry.path}>
            <Card
              onClick={() => navigate(entry.path)}
              sx={{
                cursor: 'pointer',
                backgroundColor: colors.surface,
                border: `1px solid ${colors.divider}`,
                borderRadius: '10px',
                boxShadow: 'none',
                transition: 'border-color 0.2s ease, background-color 0.2s ease',
                '&:hover': {
                  backgroundColor: colors.surfaceAlt,
                  borderColor: colors.primary.main,
                },
              }}
            >
              <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box sx={{ color: '#7C4DFF' }}>{entry.icon}</Box>
                <Box>
                  <Typography variant="h3" sx={{ color: 'text.primary' }}>
                    {entry.title}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {entry.description}
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Recent tenders table */}
      <Paper
        sx={{
          p: 2,
          backgroundColor: '#FFFFFF',
          border: `1px solid ${colors.divider}`,
          borderRadius: '10px',
          boxShadow: 'none',
        }}
      >
        <Typography variant="h3" sx={{ mb: 2 }}>
          最近标书
        </Typography>
        {recentTenders.length === 0 ? (
          <Typography
            variant="body2"
            sx={{ color: '#999', py: 3, textAlign: 'center' }}
          >
            暂无标书，点击"上传标书"开始
          </Typography>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>文件名</TableCell>
                  <TableCell>状态</TableCell>
                  <TableCell>创建时间</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {recentTenders.map((tender) => (
                  <TableRow
                    key={tender.id}
                    hover
                    onClick={() => navigate('/tenders')}
                    sx={{ cursor: 'pointer' }}
                  >
                    <TableCell sx={{ color: '#333' }}>{tender.title}</TableCell>
                    <TableCell>
                      <StatusTag
                        kind={TENDER_STATUS_KIND[tender.status]}
                        label={TENDER_STATUS_LABELS[tender.status]}
                      />
                    </TableCell>
                    <TableCell sx={{ color: '#666' }}>
                      {formatDate(tender.upload_time)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>
    </Box>
  );
};

export default Dashboard;
