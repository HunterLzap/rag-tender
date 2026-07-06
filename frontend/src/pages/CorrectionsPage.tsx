import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import RefreshIcon from '@mui/icons-material/Refresh';
import { getMatchCorrections } from '../api/match';
import type { MatchCorrection, MatchStatus } from '../types';

const STATUS_CONFIG: Record<
  MatchStatus | 'confirmed',
  { label: string; color: string; bg: string }
> = {
  matched: { label: '符合', color: '#2E7D32', bg: '#E8F5E9' },
  unmatched: { label: '不符合', color: '#C62828', bg: '#FFEBEE' },
  needs_review: { label: '需确认', color: '#EF6C00', bg: '#FFF3E0' },
  confirmed: { label: '已确认', color: '#5E35B1', bg: '#EDE7F6' },
};

const StatusChip: React.FC<{ status: MatchStatus | 'confirmed' | null }> = ({
  status,
}) => {
  if (!status) {
    return <Chip label="—" size="small" />;
  }
  const config = STATUS_CONFIG[status];
  return (
    <Chip
      label={config.label}
      size="small"
      sx={{
        height: 24,
        fontSize: 12,
        fontWeight: 600,
        color: config.color,
        backgroundColor: config.bg,
        border: `1px solid ${config.color}`,
      }}
    />
  );
};

const CorrectionsPage: React.FC = () => {
  const [corrections, setCorrections] = useState<MatchCorrection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadCorrections = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getMatchCorrections(200);
      setCorrections(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载错例记录失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadCorrections();
  }, []);

  const stats = useMemo(() => {
    return corrections.reduce(
      (acc, item) => {
        acc.total += 1;
        if (item.confirmed_status === 'matched') acc.toMatched += 1;
        if (item.confirmed_status === 'unmatched') acc.toUnmatched += 1;
        if (item.confirmed_status === 'needs_review') acc.toReview += 1;
        return acc;
      },
      { total: 0, toMatched: 0, toUnmatched: 0, toReview: 0 },
    );
  }, [corrections]);

  return (
    <Box sx={{ p: 3 }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          mb: 2,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0 }}>
          <Typography variant="h5" sx={{ fontWeight: 700, color: '#333' }}>
            错例库
          </Typography>
          <Tooltip title="人工确认过的匹配结果会沉淀在这里，用于复盘误判和补充规则。">
            <InfoOutlinedIcon
              aria-label="错例库说明"
              sx={{ fontSize: 16, color: '#777', flexShrink: 0 }}
            />
          </Tooltip>
        </Box>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={() => void loadCorrections()}
          sx={{ borderRadius: 0, borderColor: '#7C4DFF', color: '#7C4DFF' }}
        >
          刷新
        </Button>
      </Box>

      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 2, mb: 2 }}>
        {[
          { label: '错例总数', value: stats.total, color: '#5E35B1' },
          { label: '人工改为符合', value: stats.toMatched, color: '#2E7D32' },
          { label: '人工改为不符合', value: stats.toUnmatched, color: '#C62828' },
          { label: '人工改为需确认', value: stats.toReview, color: '#EF6C00' },
        ].map((item) => (
          <Paper
            key={item.label}
            sx={{
              p: 2,
              boxShadow: 'none',
              border: '1px solid #EDE7F6',
              borderRadius: 2,
            }}
          >
            <Typography variant="caption" sx={{ color: '#777' }}>
              {item.label}
            </Typography>
            <Typography variant="h5" sx={{ color: item.color, fontWeight: 700 }}>
              {item.value}
            </Typography>
          </Paper>
        ))}
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <TableContainer
        component={Paper}
        sx={{ boxShadow: 'none', border: '1px solid #EDE7F6' }}
      >
        <Table size="small">
          <TableHead>
            <TableRow sx={{ backgroundColor: '#F9F7FF' }}>
              <TableCell sx={{ fontWeight: 600, color: '#666', width: '17%' }}>
                标书
              </TableCell>
              <TableCell sx={{ fontWeight: 600, color: '#666', width: '24%' }}>
                招标要求
              </TableCell>
              <TableCell sx={{ fontWeight: 600, color: '#666', width: '17%' }}>
                候选证据
              </TableCell>
              <TableCell sx={{ fontWeight: 600, color: '#666', width: '10%' }}>
                原判断
              </TableCell>
              <TableCell sx={{ fontWeight: 600, color: '#666', width: '10%' }}>
                人工修正
              </TableCell>
              <TableCell sx={{ fontWeight: 600, color: '#666', width: '16%' }}>
                修正原因
              </TableCell>
              <TableCell sx={{ fontWeight: 600, color: '#666', width: '6%' }}>
                时间
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading && (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 5 }}>
                  <CircularProgress size={28} sx={{ color: '#7C4DFF' }} />
                </TableCell>
              </TableRow>
            )}
            {!loading && corrections.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 5 }}>
                  <Typography variant="body2" sx={{ color: '#999' }}>
                    暂无错例记录。人工确认匹配结果后，这里会自动沉淀。
                  </Typography>
                </TableCell>
              </TableRow>
            )}
            {!loading &&
              corrections.map((item) => (
                <TableRow key={item.id} hover>
                  <TableCell>
                    <Typography variant="body2" sx={{ color: '#333', fontWeight: 600 }}>
                      {item.tender_title || item.tender_filename || `标书 ${item.tender_id}`}
                    </Typography>
                    <Typography variant="caption" sx={{ color: '#888' }}>
                      ID: {item.tender_id}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ color: '#333', fontWeight: 600 }}>
                      {item.requirement_title || '—'}
                    </Typography>
                    <Typography variant="caption" sx={{ color: '#666' }}>
                      {item.requirement_content || '—'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ color: '#333' }}>
                      {item.qualification_name || '未关联资质记录'}
                    </Typography>
                    <Typography variant="caption" sx={{ color: '#888' }}>
                      {item.evidence_snapshot.length} 项证据快照
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <StatusChip status={item.previous_status} />
                  </TableCell>
                  <TableCell>
                    <StatusChip status={item.confirmed_status} />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ color: '#333' }}>
                      {item.correction_reason || '未填写'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="caption" sx={{ color: '#666' }}>
                      {item.created_at}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export default CorrectionsPage;
