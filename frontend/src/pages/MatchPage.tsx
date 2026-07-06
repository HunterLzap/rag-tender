import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  Box,
  Paper,
  Typography,
  Button,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  CircularProgress,
  LinearProgress,
  Alert,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import HelpIcon from '@mui/icons-material/Help';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import FileUploader from '../components/FileUploader';
import MatchResultTabs from '../components/MatchResultTabs';
import { StatusTag } from '../components/StatusTags';
import { colors } from '../theme';
import { getTenders } from '../api/tenders';
import { matchTender, getMatchResults, confirmMatch, getMatchStatus } from '../api/match';
import { uploadTemplate, fillTemplate, downloadFilled } from '../api/fill';
import { exportCheckReport } from '../api/checklist';
import type { Tender, MatchProgress, MatchResult, MatchStatus, FillTemplate } from '../types';

interface MatchStats {
  matched: number;
  unmatched: number;
  needsReview: number;
}

interface TenderMatchSummary {
  tender: Tender;
  matched: number;
  unmatched: number;
  needsReview: number;
  total: number;
  latestAt: string | null;
}

const TENDER_STATUS_LABELS: Record<Tender['status'], string> = {
  pending: '待处理',
  converting: '转换中',
  parsing: '解析中',
  extracting: '提取中',
  retrying_vlm: '重试识别中',
  completed: '已解析',
  failed: '解析失败',
};

const STAT_CARDS: {
  key: keyof MatchStats;
  label: string;
  color: string;
  icon: React.ReactNode;
}[] = [
  {
    key: 'matched',
    label: '通过',
    color: '#4CAF50',
    icon: <CheckCircleIcon />,
  },
  {
    key: 'unmatched',
    label: '不通过',
    color: '#EF5350',
    icon: <CancelIcon />,
  },
  {
    key: 'needsReview',
    label: '待确认',
    color: '#FF9800',
    icon: <HelpIcon />,
  },
];

/**
 * Match results page (routes: /match and /match/:id).
 * Select a tender, trigger matching, view results with statistics,
 * and auto-fill a template for download.
 */
const MatchPage: React.FC = () => {
  const { id: urlId } = useParams<{ id: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const isSummaryPage = !urlId;
  const matchingStartedFromReview = Boolean(
    (location.state as { matchingStarted?: boolean } | null)?.matchingStarted,
  );
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [summaries, setSummaries] = useState<TenderMatchSummary[]>([]);
  const [loadingSummaries, setLoadingSummaries] = useState(false);
  const [reanalyzingId, setReanalyzingId] = useState<number | null>(null);
  const [selectedTenderId, setSelectedTenderId] = useState<number | null>(null);
  const [results, setResults] = useState<MatchResult[]>([]);
  const [matching, setMatching] = useState(matchingStartedFromReview);
  const [matchProgress, setMatchProgress] = useState<MatchProgress | null>(null);
  const [loadingTenders, setLoadingTenders] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Auto-fill dialog state
  const [fillDialogOpen, setFillDialogOpen] = useState(false);
  const [fillTemplateInfo, setFillTemplateInfo] = useState<FillTemplate | null>(null);
  const [uploadingTemplate, setUploadingTemplate] = useState(false);
  const [filling, setFilling] = useState(false);
  const [fillResult, setFillResult] = useState<FillTemplate | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [reportDownloading, setReportDownloading] = useState(false);
  const [fillError, setFillError] = useState<string | null>(null);

  /** Load tenders list for the dropdown. */
  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const list = await getTenders();
        if (!mounted) return;
        setTenders(list);
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : '加载标书列表失败');
        }
      } finally {
        if (mounted) setLoadingTenders(false);
      }
    };
    load();
    return () => {
      mounted = false;
    };
  }, []);

  /** Auto-select tender from URL parameter. */
  useEffect(() => {
    if (urlId) {
      const id = Number(urlId);
      if (!isNaN(id)) {
        setSelectedTenderId(id);
      }
    }
  }, [urlId]);

  const loadSummaries = useCallback(async () => {
    setLoadingSummaries(true);
    setError(null);
    try {
      const list = tenders.length ? tenders : await getTenders();
      if (!tenders.length && list.length) setTenders(list);
      const rows = await Promise.all(
        list.map(async (tender) => {
          const matchResults = await getMatchResults(tender.id);
          return {
            tender,
            matched: matchResults.filter((item) => item.match_status === 'matched').length,
            unmatched: matchResults.filter((item) => item.match_status === 'unmatched').length,
            needsReview: matchResults.filter((item) => item.match_status === 'needs_review').length,
            total: matchResults.length,
            latestAt: (() => {
              const times = matchResults
                .map((item) => item.created_at)
                .filter(Boolean)
                .sort();
              return times.length ? times[times.length - 1] : null;
            })(),
          };
        }),
      );
      setSummaries(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载匹配汇总失败');
    } finally {
      setLoadingSummaries(false);
    }
  }, [tenders]);

  useEffect(() => {
    if (isSummaryPage && !loadingTenders) {
      void loadSummaries();
    }
  }, [isSummaryPage, loadingTenders, loadSummaries]);

  const waitForMatchDone = useCallback(async (tenderId: number) => {
    for (let attempt = 0; attempt < 180; attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
      const progress = await getMatchStatus(tenderId);
      if (progress.status === 'completed') return;
      if (progress.status === 'failed') {
        throw new Error(progress.error || progress.message || '匹配任务失败');
      }
      if (progress.status === 'idle') return;
    }
    throw new Error('匹配任务等待超时，请稍后重试');
  }, []);

  const handleReanalyzeFromSummary = useCallback(
    async (tenderId: number) => {
      setReanalyzingId(tenderId);
      setError(null);
      try {
        await matchTender(tenderId);
        await waitForMatchDone(tenderId);
        await loadSummaries();
      } catch (err) {
        setError(err instanceof Error ? err.message : '重新分析失败');
      } finally {
        setReanalyzingId(null);
      }
    },
    [loadSummaries, waitForMatchDone],
  );

  /** Load existing results only. Selecting a tender never starts matching. */
  useEffect(() => {
    if (!selectedTenderId || matching) return;

    let mounted = true;

    const loadExistingResults = async () => {
      setError(null);
      try {
        const matchResults = await getMatchResults(selectedTenderId);
        if (mounted) setResults(matchResults);
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : '获取匹配结果失败');
        }
      }
    };

    void loadExistingResults();

    return () => {
      mounted = false;
    };
  }, [matching, selectedTenderId]);

  /** Poll progress while a matching task has explicitly been started. */
  useEffect(() => {
    if (!selectedTenderId || !matching) return;

    let mounted = true;
    let attempts = 0;
    const timer = window.setInterval(async () => {
      attempts += 1;
      try {
        const progress = await getMatchStatus(selectedTenderId);
        if (!mounted) return;
        setMatchProgress(progress);

        if (progress.status === 'idle') {
          const matchResults = await getMatchResults(selectedTenderId);
          if (!mounted) return;
          setResults(matchResults);
          setMatching(false);
          if (matchResults.length === 0) {
            setError('当前没有正在运行的匹配任务，也没有已有匹配结果，请重新点击匹配');
          }
          window.clearInterval(timer);
        } else if (progress.status === 'completed') {
          const matchResults = await getMatchResults(selectedTenderId);
          if (!mounted) return;
          setResults(matchResults);
          setMatching(false);
          window.clearInterval(timer);
        } else if (progress.status === 'failed') {
          setMatching(false);
          setError(progress.error || progress.message || '匹配任务失败');
          window.clearInterval(timer);
        } else if (attempts >= 180) {
          setMatching(false);
          setError('匹配任务等待超时，请稍后点击重新匹配');
          window.clearInterval(timer);
        }
      } catch (err) {
        if (mounted) {
          setMatching(false);
          setError(err instanceof Error ? err.message : '获取匹配进度失败，请检查后端服务是否启动');
          window.clearInterval(timer);
        }
      }
    }, 2000);

    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, [matching, selectedTenderId]);

  /** Explicitly start or restart matching. */
  const handleStartMatch = useCallback(async () => {
    if (!selectedTenderId) return;
    setMatching(true);
    setResults([]);
    setMatchProgress({
      tender_id: selectedTenderId,
      status: 'queued',
      stage: 'queued',
      current: 0,
      total: 0,
      matched: 0,
      unmatched: 0,
      needs_review: 0,
      message: '匹配任务已提交，等待后端开始处理',
      current_requirement: null,
      started_at: null,
      updated_at: null,
      finished_at: null,
      error: null,
    });
    setError(null);
    try {
      await matchTender(selectedTenderId);
    } catch (err) {
      setMatching(false);
      setError(err instanceof Error ? err.message : '启动匹配失败');
    }
  }, [selectedTenderId]);

  /** Compute statistics from the current results. */
  const stats = useMemo<MatchStats>(() => {
    return results.reduce(
      (acc, r) => {
        if (r.match_status === 'matched') acc.matched++;
        else if (r.match_status === 'unmatched') acc.unmatched++;
        else if (r.match_status === 'needs_review') acc.needsReview++;
        return acc;
      },
      { matched: 0, unmatched: 0, needsReview: 0 }
    );
  }, [results]);

  const selectedTender = useMemo(
    () => tenders.find((tender) => tender.id === selectedTenderId) || null,
    [selectedTenderId, tenders],
  );

  /** Handle manual confirmation of a match result. */
  const handleConfirm = useCallback(
    async (matchId: number, status: MatchStatus, correctionReason?: string) => {
      try {
        await confirmMatch(matchId, status, correctionReason);
        setResults((prev) =>
          prev.map((r) =>
            r.id === matchId
              ? { ...r, match_status: status, confirmed_status: 'confirmed' }
              : r
          )
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : '确认失败');
      }
    },
    []
  );

  /** Open the auto-fill dialog and reset its state. */
  const handleOpenFillDialog = useCallback(() => {
    setFillTemplateInfo(null);
    setFillResult(null);
    setFillError(null);
    setFillDialogOpen(true);
  }, []);

  /** Upload a fill template file. */
  const handleTemplateUpload = useCallback(
    async (files: File[]) => {
      if (files.length === 0 || !selectedTenderId) return;
      setUploadingTemplate(true);
      setFillError(null);
      try {
        const result = await uploadTemplate(
          selectedTenderId,
          files[files.length - 1]
        );
        setFillTemplateInfo(result);
      } catch (err) {
        setFillError(err instanceof Error ? err.message : '模板上传失败');
      } finally {
        setUploadingTemplate(false);
      }
    },
    [selectedTenderId]
  );

  /** Trigger the auto-fill process. */
  const handleStartFill = useCallback(async () => {
    if (!selectedTenderId) return;
    setFilling(true);
    setFillError(null);
    try {
      const result = await fillTemplate(selectedTenderId);
      setFillResult(result);
    } catch (err) {
      setFillError(err instanceof Error ? err.message : '填写失败');
    } finally {
      setFilling(false);
    }
  }, [selectedTenderId]);

  /** Download the filled document in the specified format. */
  const handleDownload = useCallback(
    async (format: 'docx' | 'pdf') => {
      if (!selectedTenderId) return;
      setDownloading(true);
      setFillError(null);
      try {
        const blob = await downloadFilled(selectedTenderId, format);
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `tender_${selectedTenderId}_filled.${format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      } catch (err) {
        setFillError(err instanceof Error ? err.message : '下载失败');
      } finally {
        setDownloading(false);
      }
    },
    [selectedTenderId]
  );

  const handleExportReport = useCallback(async () => {
    if (!selectedTenderId) return;
    setReportDownloading(true);
    setError(null);
    try {
      const report = await exportCheckReport(selectedTenderId);
      const blob = new Blob([report.content], {
        type: report.content_type || 'text/markdown;charset=utf-8',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = report.filename || `tender_${selectedTenderId}_check_report.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : '导出检查报告失败');
    } finally {
      setReportDownloading(false);
    }
  }, [selectedTenderId]);

  if (isSummaryPage) {
    return (
      <Box>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 2,
            flexWrap: 'wrap',
            mb: 2,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0 }}>
            <Typography variant="h2" sx={{ color: '#333' }}>
              匹配结果汇总
            </Typography>
            <Tooltip title="每条数据对应一个标书。点击匹配数字可查看具体匹配/不匹配明细。">
              <InfoOutlinedIcon
                aria-label="匹配结果汇总说明"
                sx={{ fontSize: 16, color: '#777', flexShrink: 0 }}
              />
            </Tooltip>
          </Box>
          <Button
            variant="outlined"
            onClick={loadSummaries}
            disabled={loadingSummaries || reanalyzingId !== null}
            sx={{ borderRadius: 0, borderColor: '#7C4DFF', color: '#7C4DFF' }}
          >
            刷新汇总
          </Button>
        </Box>

        <TableContainer
          component={Paper}
          sx={{
            backgroundColor: '#FFFFFF',
            border: `1px solid ${colors.divider}`,
            boxShadow: 'none',
          }}
        >
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>标书</TableCell>
                <TableCell sx={{ width: 110 }}>解析状态</TableCell>
                <TableCell sx={{ width: 90 }} align="center">
                  总匹配项
                </TableCell>
                <TableCell sx={{ width: 90 }} align="center">
                  通过
                </TableCell>
                <TableCell sx={{ width: 90 }} align="center">
                  不通过
                </TableCell>
                <TableCell sx={{ width: 90 }} align="center">
                  待确认
                </TableCell>
                <TableCell sx={{ width: 160 }}>最近匹配</TableCell>
                <TableCell sx={{ width: 220 }}>操作</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(loadingSummaries || loadingTenders) && (
                <TableRow>
                  <TableCell colSpan={8} align="center" sx={{ py: 5 }}>
                    <CircularProgress size={22} sx={{ color: '#7C4DFF' }} />
                    <Typography variant="body2" sx={{ color: '#777', mt: 1 }}>
                      正在加载匹配汇总…
                    </Typography>
                  </TableCell>
                </TableRow>
              )}

              {!loadingSummaries && !loadingTenders && summaries.length === 0 && (
                <TableRow>
                  <TableCell colSpan={8} align="center" sx={{ py: 5, color: '#999' }}>
                    暂无标书
                  </TableCell>
                </TableRow>
              )}

              {!loadingSummaries &&
                !loadingTenders &&
                summaries.map((row) => {
                  const title = row.tender.title || row.tender.filename || `标书 ${row.tender.id}`;
                  const busy = reanalyzingId === row.tender.id;
                  return (
                    <TableRow key={row.tender.id} hover sx={{ height: 44 }}>
                      <TableCell>
                        <Typography variant="body2" sx={{ color: '#333', fontWeight: 650 }}>
                          {title}
                        </Typography>
                        <Typography variant="caption" sx={{ color: '#999' }}>
                          ID {row.tender.id}
                          {row.tender.region ? ` · ${row.tender.region}` : ''}
                          {row.tender.budget ? ` · 预算 ${row.tender.budget}` : ''}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <StatusTag
                          kind={row.tender.status === 'completed' ? 'info' : 'neutral'}
                          label={TENDER_STATUS_LABELS[row.tender.status] || '待处理'}
                        />
                      </TableCell>
                      {[
                        { value: row.total, color: '#7C4DFF' },
                        { value: row.matched, color: '#2E7D32' },
                        { value: row.unmatched, color: '#C62828' },
                        { value: row.needsReview, color: '#B56A00' },
                      ].map((item, index) => (
                        <TableCell key={index} align="center">
                          <Button
                            size="small"
                            disabled={row.total === 0}
                            onClick={() => navigate(`/match/${row.tender.id}`)}
                            sx={{
                              minWidth: 32,
                              p: 0,
                              color: item.color,
                              fontWeight: 800,
                              fontSize: 16,
                            }}
                          >
                            {item.value}
                          </Button>
                        </TableCell>
                      ))}
                      <TableCell>
                        <Typography variant="caption" sx={{ color: '#777' }}>
                          {row.latestAt ? new Date(row.latestAt).toLocaleString() : '尚未匹配'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                          <Tooltip title="查看匹配明细">
                            <span>
                              <Button
                                size="small"
                                variant="outlined"
                                onClick={() => navigate(`/match/${row.tender.id}`)}
                                disabled={row.total === 0 || busy}
                                sx={{ borderColor: '#7C4DFF', color: '#7C4DFF' }}
                              >
                                查看明细
                              </Button>
                            </span>
                          </Tooltip>
                          <Tooltip title={row.total > 0 ? '重新匹配' : '开始匹配'}>
                            <span>
                              <Button
                                size="small"
                                variant="contained"
                                onClick={() => handleReanalyzeFromSummary(row.tender.id)}
                                disabled={busy || reanalyzingId !== null || row.tender.status !== 'completed'}
                                sx={{
                                  backgroundColor: '#7C4DFF',
                                  '&:hover': { backgroundColor: '#651FFF' },
                                }}
                              >
                                {busy ? '分析中…' : row.total > 0 ? '重新分析' : '开始分析'}
                              </Button>
                            </span>
                          </Tooltip>
                        </Box>
                      </TableCell>
                    </TableRow>
                  );
                })}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    );
  }

  return (
    <Box
      onClick={() => navigate('/match')}
      sx={{
        position: 'fixed',
        inset: 0,
        zIndex: 1200,
        backgroundColor: 'rgba(40, 32, 58, 0.22)',
        display: 'flex',
        justifyContent: 'flex-end',
      }}
    >
      <Paper
        elevation={0}
        onClick={(event) => event.stopPropagation()}
        sx={{
          width: { xs: '100%', md: '78vw', lg: '72vw' },
          maxWidth: 1220,
          height: '100vh',
          overflow: 'auto',
          p: { xs: 1.5, md: 2 },
          borderRadius: 0,
          borderLeft: '1px solid #E4DDF0',
          boxShadow: '-12px 0 28px rgba(39, 28, 62, 0.18)',
          backgroundColor: '#FFFFFF',
        }}
      >
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Detail header */}
      <Paper
        sx={{
          p: 2,
          mb: 2,
          backgroundColor: '#FFFFFF',
          border: '1px solid #EDE7F6',
          borderRadius: 2,
        }}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 2,
            flexWrap: 'wrap',
          }}
        >
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
              <IconButton
                aria-label="返回匹配汇总"
                title="返回匹配汇总"
                onClick={() => navigate('/match')}
                sx={{
                  width: 32,
                  height: 32,
                  color: '#7C4DFF',
                  backgroundColor: '#F4EEFF',
                  '&:hover': { backgroundColor: '#E7DBFF' },
                }}
              >
                <ArrowBackIcon fontSize="small" />
              </IconButton>
              <Typography variant="h2" sx={{ color: '#333' }}>
                匹配明细
              </Typography>
            </Box>
            <Typography variant="body2" sx={{ color: '#777', mt: 0.25 }}>
              当前标书：{selectedTender?.title || selectedTender?.filename || `标书 ${selectedTenderId || ''}`}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <Tooltip title="重新匹配">
              <span>
                <Button
                  variant="outlined"
                  onClick={handleStartMatch}
                  disabled={!selectedTenderId || matching}
                  sx={{ borderColor: '#7C4DFF', color: '#7C4DFF' }}
                >
                  {matching ? '匹配中…' : '重新匹配'}
                </Button>
              </span>
            </Tooltip>
            {results.length > 0 && (
              <Tooltip title="导出检查报告">
                <span>
                  <Button
                    variant="outlined"
                    startIcon={<DownloadIcon />}
                    onClick={handleExportReport}
                    disabled={!selectedTenderId || reportDownloading}
                    sx={{ borderColor: '#7C4DFF', color: '#7C4DFF' }}
                  >
                    {reportDownloading ? '导出中…' : '导出检查报告'}
                  </Button>
                </span>
              </Tooltip>
            )}
            {results.length > 0 && (
              <Tooltip title="自动填写">
                <Button
                  variant="contained"
                  onClick={handleOpenFillDialog}
                  sx={{
                    backgroundColor: '#7C4DFF',
                    '&:hover': { backgroundColor: '#651FFF' },
                  }}
                >
                  自动填写
                </Button>
              </Tooltip>
            )}
          </Box>
        </Box>
      </Paper>

      {loadingTenders && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress sx={{ color: '#7C4DFF' }} />
        </Box>
      )}

      {/* Matching in progress */}
      {matching && (
        <Paper
          sx={{
            p: 3,
            mb: 3,
            backgroundColor: '#FFFFFF',
            border: '1px solid #EDE7F6',
            borderRadius: 2,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.5 }}>
            <CircularProgress size={22} sx={{ color: '#7C4DFF' }} />
            <Box sx={{ flex: 1 }}>
              <Typography variant="subtitle1" sx={{ color: '#333', fontWeight: 700 }}>
                {matchProgress?.message || '正在匹配中'}
              </Typography>
              <Typography variant="body2" sx={{ color: '#777', mt: 0.25 }}>
                {matchProgress?.current_requirement
                  ? `当前要求：${matchProgress.current_requirement}`
                  : '系统正在准备匹配任务'}
              </Typography>
            </Box>
            <Typography variant="body2" sx={{ color: '#7C4DFF', fontWeight: 700 }}>
              {matchProgress?.total
                ? `${matchProgress.current}/${matchProgress.total}`
                : matchProgress?.status === 'queued'
                  ? '排队中'
                  : '处理中'}
            </Typography>
          </Box>
          <LinearProgress
            variant={matchProgress?.total ? 'determinate' : 'indeterminate'}
            value={
              matchProgress?.total
                ? Math.min(100, (matchProgress.current / matchProgress.total) * 100)
                : undefined
            }
            sx={{
              height: 8,
              borderRadius: 99,
              backgroundColor: '#F1ECFF',
              '& .MuiLinearProgress-bar': { backgroundColor: '#7C4DFF' },
            }}
          />
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mt: 1.5 }}>
            <Typography variant="caption" sx={{ color: '#4CAF50' }}>
              已匹配：{matchProgress?.matched ?? 0}
            </Typography>
            <Typography variant="caption" sx={{ color: '#EF5350' }}>
              不匹配：{matchProgress?.unmatched ?? 0}
            </Typography>
            <Typography variant="caption" sx={{ color: '#FF9800' }}>
              待确认：{matchProgress?.needs_review ?? 0}
            </Typography>
            <Typography variant="caption" sx={{ color: '#999', ml: 'auto' }}>
              LLM 已绕过，当前使用本地规则匹配
            </Typography>
          </Box>
        </Paper>
      )}

      {/* Results */}
      {!matching && selectedTenderId && results.length > 0 && (
        <Box>
          {/* Statistics cards */}
          <Grid container spacing={2} sx={{ mb: 3 }}>
            {STAT_CARDS.map((card) => (
              <Grid item xs={12} sm={4} key={card.key}>
                <Paper
                  sx={{
                    p: 2.5,
                    backgroundColor: '#FFFFFF',
                    border: `1px solid ${colors.divider}`,
                    borderRadius: '10px',
                    boxShadow: 'none',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1.5,
                  }}
                >
                  <Box sx={{ color: card.color }}>{card.icon}</Box>
                  <Box>
                    <Typography variant="subtitle1" color="text.secondary">
                      {card.label}
                    </Typography>
                    <Typography variant="h4" sx={{ color: card.color, fontWeight: 700 }}>
                      {stats[card.key]}
                    </Typography>
                  </Box>
                </Paper>
              </Grid>
            ))}
          </Grid>

          {/* Match results table — wrapped in MatchResultTabs for 3-tab layout */}
          <MatchResultTabs
            tenderId={selectedTenderId}
            matchResults={results}
            onConfirm={handleConfirm}
          />
        </Box>
      )}

      {/* Empty state: tender selected but no results */}
      {!matching && selectedTenderId && results.length === 0 && !error && (
        <Paper
          sx={{
            p: 4,
            backgroundColor: '#F9F7FF',
            border: '1px solid #EDE7F6',
            borderRadius: 2,
            textAlign: 'center',
          }}
        >
          <Typography variant="body1" sx={{ color: '#666' }}>
            尚未进行资质匹配
          </Typography>
          <Typography variant="body2" sx={{ color: '#999', mt: 0.75, mb: 2 }}>
            建议先在标书核对页面确认解析结果，再开始匹配。
          </Typography>
          <Button
            variant="contained"
            onClick={handleStartMatch}
            sx={{
              borderRadius: 0,
              backgroundColor: '#7C4DFF',
              '&:hover': { backgroundColor: '#651FFF' },
            }}
          >
            开始匹配
          </Button>
        </Paper>
      )}

      {/* No tender selected */}
      {!selectedTenderId && !loadingTenders && (
        <Paper
          sx={{
            p: 4,
            backgroundColor: '#F9F7FF',
            border: '1px solid #EDE7F6',
            borderRadius: 2,
            textAlign: 'center',
          }}
        >
          <Typography variant="body1" sx={{ color: '#666' }}>
            未找到要查看的标书，请返回匹配汇总重新进入。
          </Typography>
          <Button
            variant="contained"
            onClick={() => navigate('/match')}
            sx={{ mt: 2, backgroundColor: '#7C4DFF', '&:hover': { backgroundColor: '#651FFF' } }}
          >
            返回匹配汇总
          </Button>
        </Paper>
      )}

      {/* ===== Auto-fill dialog ===== */}
      </Paper>

      <Dialog
        open={fillDialogOpen}
        onClose={() => setFillDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ color: '#7C4DFF', fontWeight: 600 }}>
          自动填写
        </DialogTitle>
        <DialogContent>
          {fillError && (
            <Alert severity="error" sx={{ mb: 2 }} onClose={() => setFillError(null)}>
              {fillError}
            </Alert>
          )}

          {/* Step 1: Upload template */}
          {!fillResult && (
            <Box>
              <Typography variant="body2" sx={{ color: '#666', mb: 2 }}>
                请上传填写模板（.docx / .pdf / .xlsx）
              </Typography>
              <FileUploader
                accept=".docx,.pdf,.xlsx"
                multiple={false}
                onFilesSelected={handleTemplateUpload}
                uploading={uploadingTemplate}
              />
            </Box>
          )}

          {/* Step 2: Start fill (template uploaded) */}
          {fillTemplateInfo && !fillResult && (
            <Box sx={{ mt: 2 }}>
              <Alert severity="success" sx={{ mb: 2 }}>
                模板已上传，可以开始填写
              </Alert>
              <Button
                variant="contained"
                onClick={handleStartFill}
                disabled={filling}
                fullWidth
                sx={{
                  backgroundColor: '#7C4DFF',
                  '&:hover': { backgroundColor: '#651FFF' },
                }}
              >
                {filling ? (
                  <CircularProgress size={20} color="inherit" />
                ) : (
                  '开始填写'
                )}
              </Button>
            </Box>
          )}

          {/* Step 3: Download (fill completed) */}
          {fillResult && (
            <Box sx={{ mt: 2 }}>
              <Alert severity="success" sx={{ mb: 2 }}>
                填写完成，请选择下载格式
              </Alert>
              <Box sx={{ display: 'flex', gap: 2 }}>
                <Button
                  variant="outlined"
                  startIcon={<DownloadIcon />}
                  onClick={() => handleDownload('docx')}
                  disabled={downloading}
                  fullWidth
                  sx={{
                    borderColor: '#7C4DFF',
                    color: '#7C4DFF',
                    '&:hover': { borderColor: '#651FFF', backgroundColor: '#EDE7F6' },
                  }}
                >
                  下载 DOCX
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<DownloadIcon />}
                  onClick={() => handleDownload('pdf')}
                  disabled={downloading}
                  fullWidth
                  sx={{
                    borderColor: '#7C4DFF',
                    color: '#7C4DFF',
                    '&:hover': { borderColor: '#651FFF', backgroundColor: '#EDE7F6' },
                  }}
                >
                  下载 PDF
                </Button>
              </Box>
              {downloading && (
                <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
                  <CircularProgress size={20} sx={{ color: '#7C4DFF' }} />
                </Box>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setFillDialogOpen(false)} sx={{ color: '#666' }}>
            关闭
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default MatchPage;
