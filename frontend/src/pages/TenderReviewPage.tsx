import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import RefreshIcon from '@mui/icons-material/Refresh';

import RequirementReviewWorkbench from '../components/RequirementReviewWorkbench';
import { getTenderDetail, reparseRequirements, getStatus } from '../api/tenders';
import { getMatchResults, getMatchStatus, matchTender } from '../api/match';
import { getQualifications } from '../api/knowledge';
import type {
  MatchProgress,
  MatchResult,
  Qualification,
  Tender,
  TenderRequirement,
} from '../types';

const TenderReviewPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const tenderId = Number(id);
  const [tender, setTender] = useState<Tender | null>(null);
  const [requirements, setRequirements] = useState<TenderRequirement[]>([]);
  const [matchResults, setMatchResults] = useState<MatchResult[]>([]);
  const [qualifications, setQualifications] = useState<Qualification[]>([]);
  const [loading, setLoading] = useState(true);
  const [matching, setMatching] = useState(false);
  const [matchProgress, setMatchProgress] = useState<MatchProgress | null>(null);
  const [reparsing, setReparsing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!Number.isInteger(tenderId) || tenderId <= 0) {
      setError('无效的标书 ID');
      setLoading(false);
      return;
    }

    let mounted = true;
    const load = async () => {
      try {
        const detail = await getTenderDetail(tenderId);
        if (!mounted) return;
        setTender(detail.tender);
        setRequirements(detail.requirements);
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : '加载核对数据失败');
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };
    void load();
    return () => {
      mounted = false;
    };
  }, [tenderId]);

  const reviewStats = useMemo(() => {
    const confirmed = requirements.filter(
      (item) => item.review_status === 'confirmed',
    ).length;
    return {
      confirmed,
      pending: requirements.length - confirmed,
    };
  }, [requirements]);

  const handleMatch = useCallback(async () => {
    if (!tender) return;

    setMatching(true);
    setError(null);
    setMatchResults([]);
    setMatchProgress({
      tender_id: tender.id,
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
    try {
      const qualificationList = await getQualifications();
      setQualifications(qualificationList);
      await matchTender(tender.id);
      for (let attempt = 0; attempt < 180; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        const progress = await getMatchStatus(tender.id);
        setMatchProgress(progress);
        if (progress.status === 'completed') {
          const results = await getMatchResults(tender.id);
          setMatchResults(results);
          navigate('/match');
          return;
        }
        if (progress.status === 'failed') {
          throw new Error(progress.error || progress.message || '匹配任务失败');
        }
        if (progress.status === 'idle') {
          const results = await getMatchResults(tender.id);
          setMatchResults(results);
          if (results.length === 0) {
            throw new Error('当前没有正在运行的匹配任务，也没有已有匹配结果，请重新点击匹配');
          }
          navigate('/match');
          return;
        }
      }
      throw new Error('匹配任务等待超时，请稍后重新匹配');
    } catch (err) {
      setError(err instanceof Error ? err.message : '启动匹配失败');
    } finally {
      setMatching(false);
    }
  }, [requirements.length, tender]);

  const handleRequirementsChange = useCallback(
    (next: TenderRequirement[], invalidateMatch = true) => {
      setRequirements(next);
      if (invalidateMatch && matchResults.length > 0) {
        setMatchResults([]);
      }
    },
    [matchResults.length],
  );

  const handleReparse = useCallback(async () => {
    if (!tender) return;
    if (
      !window.confirm(
        '确定按新分类重新解析？这将清空当前所有要求、匹配结果、技术响应和待办清单数据。',
      )
    )
      return;

    setReparsing(true);
    setError(null);
    setMatchResults([]);
    try {
      await reparseRequirements(tender.id);
      // Poll until completed
      for (let attempt = 0; attempt < 180; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 2000));
        const status = await getStatus(tender.id);
        if (status.status === 'completed') {
          const detail = await getTenderDetail(tender.id);
          setTender(detail.tender);
          setRequirements(detail.requirements);
          return;
        }
        if (status.status === 'failed') {
          throw new Error('重新解析失败');
        }
      }
      throw new Error('重新解析等待超时');
    } catch (err) {
      setError(err instanceof Error ? err.message : '重新解析失败');
    } finally {
      setReparsing(false);
    }
  }, [tender]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress sx={{ color: '#7C4DFF' }} />
      </Box>
    );
  }

  if (error || !tender) {
    return (
      <Box>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate('/tenders')}
          sx={{ mb: 2 }}
        >
          返回标书列表
        </Button>
        <Alert severity="error">{error || '标书不存在'}</Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 2,
          flexWrap: 'wrap',
          mb: 1.5,
        }}
      >
        <Box>
          <Button
            size="small"
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate('/tenders')}
            sx={{ color: '#666', px: 0, mb: 0.5 }}
          >
            返回标书列表
          </Button>
          <Typography variant="h6" sx={{ color: '#333', fontWeight: 700 }}>
            标书解析与需求确认
          </Typography>
          <Typography variant="body2" sx={{ color: '#666', mt: 0.25 }}>
            当前文件：{tender.title || tender.filename}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="body2" sx={{ color: '#666' }}>
            已确认 {reviewStats.confirmed}/{requirements.length}
          </Typography>
          <Button
            variant="outlined"
            size="small"
            startIcon={
              reparsing ? <CircularProgress size={14} /> : <RefreshIcon />
            }
            onClick={handleReparse}
            disabled={reparsing}
            sx={{
              borderColor: '#7C4DFF',
              color: '#7C4DFF',
              borderRadius: 0,
              '&:hover': {
                borderColor: '#651FFF',
                backgroundColor: '#EDE7F6',
              },
            }}
          >
            {reparsing ? '重新解析中…' : '按新分类重新解析'}
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 1.5 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <RequirementReviewWorkbench
        tender={tender}
        requirements={requirements}
        matchResults={matchResults}
        qualifications={qualifications}
        onRequirementsChange={handleRequirementsChange}
        onStartMatch={handleMatch}
        matching={matching}
        matchProgress={matchProgress}
      />
    </Box>
  );
};

export default TenderReviewPage;
