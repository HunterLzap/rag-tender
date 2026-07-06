import React, { useState } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Box,
  Typography,
  IconButton,
  Collapse,
  Chip,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Menu,
  MenuItem,
  TextField,
  Tooltip,
} from '@mui/material';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import HelpIcon from '@mui/icons-material/Help';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import VisibilityIcon from '@mui/icons-material/Visibility';
import type { MatchResult, MatchStatus } from '../types';
import { getKnowledgeFilePreviewUrl } from '../api/knowledge';
import { getMatchEvidenceSummary } from './matchEvidenceSummary';
import { getMatchExplanation } from './matchExplanation';
import { getMatchRiskLevel } from './matchRiskLevel';
import { canSubmitMatchConfirmation } from './matchConfirmation';
import {
  ActionTag,
  MandatoryTag,
  StatusTag,
  type StatusKind,
} from './StatusTags';
import { colors } from '../theme';

interface MatchResultTableProps {
  results: MatchResult[];
  onConfirm?: (matchId: number, status: MatchStatus, correctionReason?: string) => void;
}

const STATUS_CONFIG: Record<
  MatchStatus,
  { label: string; color: string; bg: string; icon: React.ReactElement }
> = {
  matched: {
    label: '符合',
    color: '#4CAF50',
    bg: '#E8F5E9',
    icon: <CheckCircleIcon sx={{ fontSize: 16 }} />,
  },
  unmatched: {
    label: '不符合',
    color: '#EF5350',
    bg: '#FFEBEE',
    icon: <CancelIcon sx={{ fontSize: 16 }} />,
  },
  needs_review: {
    label: '需确认',
    color: '#FF9800',
    bg: '#FFF3E0',
    icon: <HelpIcon sx={{ fontSize: 16 }} />,
  },
};

const EVIDENCE_STATUS_CONFIG = {
  pass: { label: '通过', color: '#2E7D32', bg: '#E8F5E9' },
  fail: { label: '失败', color: '#C62828', bg: '#FFEBEE' },
  unknown: { label: '待确认', color: '#EF6C00', bg: '#FFF3E0' },
} as const;

const SUMMARY_STATUS_CONFIG = {
  error: { color: '#C62828', bg: '#FFEBEE', border: '#EF5350' },
  warning: { color: '#EF6C00', bg: '#FFF3E0', border: '#FF9800' },
  success: { color: '#2E7D32', bg: '#E8F5E9', border: '#4CAF50' },
  info: { color: '#5E35B1', bg: '#F3E5F5', border: '#7C4DFF' },
} as const;

const RISK_STATUS_CONFIG = {
  hard_blocker: { color: '#B71C1C', bg: '#FFEBEE', border: '#B71C1C' },
  hard_review: { color: '#E65100', bg: '#FFF3E0', border: '#E65100' },
  high: { color: '#C62828', bg: '#FFEBEE', border: '#EF5350' },
  medium: { color: '#EF6C00', bg: '#FFF3E0', border: '#FF9800' },
  low: { color: '#2E7D32', bg: '#E8F5E9', border: '#4CAF50' },
} as const;

const isCustomTightenRuleEvidence = (checkKey: string) => checkKey.startsWith('custom_rule:');

const ClampedText: React.FC<{
  text: string;
  lines?: number;
  color?: string;
  emptyText?: string;
  fontWeight?: number;
}> = ({ text, lines = 2, color = 'text.primary', emptyText = '—', fontWeight }) => {
  const displayText = text || emptyText;

  return (
    <Tooltip title={displayText} arrow placement="top-start">
      <Typography
        variant="body2"
        color={color}
        sx={{
          display: '-webkit-box',
          WebkitLineClamp: lines,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
          cursor: 'default',
          fontWeight,
        }}
      >
        {displayText}
      </Typography>
    </Tooltip>
  );
};

const MATCH_STATUS_KIND: Record<MatchStatus, StatusKind> = {
  matched: 'success',
  unmatched: 'error',
  needs_review: 'neutral',
};

/**
 * Match result comparison table (P0-08).
 *
 * NOTE: Results are already filtered by the backend's `_should_match()` function
 * in match_service.py — only capability-class requirements reach this component.
 * product_spec and submission-class requirements are skipped during matching
 * and handled by TechnicalResponseTable / SubmissionChecklistTable respectively.
 * No additional frontend filtering is needed.
 *
 * Dual-column layout: tender requirement vs. our qualification.
 * Status tags use the shared StatusTags system.
 * Unmatched items expand to show 3-layer detail:
 * 1. Specific mismatch point
 * 2. Expected qualification
 * 3. Knowledge base status (file uploaded or not)
 */
const MatchResultTable: React.FC<MatchResultTableProps> = ({ results, onConfirm }) => {
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [anchorEl, setAnchorEl] = useState<{ [key: number]: HTMLElement | null }>({});
  const [preview, setPreview] = useState<{
    fileId: number;
    title: string;
  } | null>(null);
  const [pendingConfirm, setPendingConfirm] = useState<{
    matchId: number;
    status: MatchStatus;
    label: string;
  } | null>(null);
  const [correctionReason, setCorrectionReason] = useState('');

  const handleToggle = (id: number) => {
    setExpandedRow(expandedRow === id ? null : id);
  };

  const handleConfirmMenuOpen = (event: React.MouseEvent<HTMLButtonElement>, id: number) => {
    setAnchorEl((prev) => ({ ...prev, [id]: event.currentTarget }));
  };

  const handleConfirmMenuClose = (id: number, status: MatchStatus | null) => {
    setAnchorEl((prev) => ({ ...prev, [id]: null }));
    if (status) {
      const label = STATUS_CONFIG[status]?.label || '需确认';
      setPendingConfirm({ matchId: id, status, label });
      setCorrectionReason('');
    }
  };

  const handleConfirmSubmit = () => {
    if (pendingConfirm && onConfirm) {
      onConfirm(
        pendingConfirm.matchId,
        pendingConfirm.status,
        correctionReason.trim() || undefined,
      );
    }
    setPendingConfirm(null);
    setCorrectionReason('');
  };

  return (
    <>
      <TableContainer component={Paper} sx={{ backgroundColor: '#FFFFFF', boxShadow: 'none', border: `1px solid ${colors.divider}` }}>
        <Table size="small" sx={{ tableLayout: 'fixed' }}>
        <TableHead>
          <TableRow>
            <TableCell sx={{ width: 40 }} />
            <TableCell sx={{ width: '40%' }}>标书要求</TableCell>
            <TableCell sx={{ width: '35%' }}>我的资质</TableCell>
            <TableCell sx={{ width: '15%' }}>状态</TableCell>
            <TableCell sx={{ width: '10%' }}>确认</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {results.length === 0 && (
            <TableRow>
              <TableCell colSpan={5} align="center" sx={{ py: 4 }}>
                <Typography variant="body2" sx={{ color: '#999' }}>
                  暂无匹配结果
                </Typography>
              </TableCell>
            </TableRow>
          )}
          {results.map((result) => {
            const config = STATUS_CONFIG[result.match_status] || STATUS_CONFIG.needs_review;
            const isExpanded = expandedRow === result.id;
            const req = result.requirement;
            const qual = result.qualification;
            const isPerformanceResult = req?.category === 'performance';
            const evidenceSummary = getMatchEvidenceSummary({
              evidenceItems: result.evidence_items,
              inKnowledgeBase: result.in_knowledge_base,
            });
            const matchExplanation = getMatchExplanation({
              matchStatus: result.match_status,
              reason: result.reason,
              mismatchDetail: result.mismatch_detail,
              evidenceItems: result.evidence_items,
              inKnowledgeBase: result.in_knowledge_base,
            });
            const matchRisk = getMatchRiskLevel({
              isHardRequirement: Boolean(req?.is_hard),
              matchStatus: result.match_status,
              evidenceItems: result.evidence_items,
              inKnowledgeBase: result.in_knowledge_base,
            });
            const summaryConfig = SUMMARY_STATUS_CONFIG[evidenceSummary.severity];
            const riskConfig = RISK_STATUS_CONFIG[matchRisk.level];

            return (
              <React.Fragment key={result.id}>
                <TableRow
                  sx={{
                    height: 44,
                    backgroundColor: config.bg,
                    '&:hover': { filter: 'brightness(0.98)' },
                  }}
                >
                  <TableCell>
                    <Tooltip title={isExpanded ? '收起详情' : '展开详情'}>
                      <IconButton size="small" onClick={() => handleToggle(result.id)}>
                        {isExpanded ? (
                          <KeyboardArrowUpIcon sx={{ color: '#666' }} />
                        ) : (
                          <KeyboardArrowDownIcon sx={{ color: '#666' }} />
                        )}
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                  <TableCell>
                    <ClampedText text={req?.title || req?.content || '—'} fontWeight={600} />
                  </TableCell>
                  <TableCell>
                    {qual ? (
                      <Box>
                        <ClampedText text={qual.name} fontWeight={600} />
                        <Typography variant="caption" color="text.secondary">
                          {qual.number ? `编号: ${qual.number}` : ''}
                          {qual.expiry_date ? ` · 有效期: ${qual.expiry_date}` : ''}
                        </Typography>
                        {qual.file_id && (
                          <Tooltip title="查看证据">
                            <Button
                              size="small"
                              startIcon={<VisibilityIcon sx={{ fontSize: 14 }} />}
                              onClick={() =>
                                setPreview({
                                  fileId: qual.file_id as number,
                                  title: qual.name || '资质文件',
                                })
                              }
                              sx={{
                                mt: 0.5,
                                p: 0,
                                minWidth: 0,
                                color: '#7C4DFF',
                                fontSize: 12,
                              }}
                            >
                              查看证据
                            </Button>
                          </Tooltip>
                        )}
                      </Box>
                    ) : isPerformanceResult && result.in_knowledge_base ? (
                      <Box>
                        <Typography variant="body2" sx={{ color: '#333', fontWeight: 500 }}>
                          业绩库候选项目
                        </Typography>
                        <Typography variant="caption" sx={{ color: '#666' }}>
                          {result.reason || '已在业绩库中找到候选记录'}
                        </Typography>
                      </Box>
                    ) : (
                      <Typography variant="body2" sx={{ color: '#999', fontStyle: 'italic' }}>
                        资质库未找到
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap' }}>
                      {result.match_status === 'needs_review' ? (
                        <ActionTag label="需确认" />
                      ) : (
                        <StatusTag
                          kind={MATCH_STATUS_KIND[result.match_status]}
                          label={config.label}
                        />
                      )}
                      {req?.is_hard && <MandatoryTag level="硬性" />}
                      {result.confirmed_status === 'confirmed' && (
                        <StatusTag kind="success" label="已确认" />
                      )}
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Tooltip title="确认">
                      <Button
                        size="small"
                        onClick={(e) => handleConfirmMenuOpen(e, result.id)}
                        sx={{ color: '#7C4DFF', fontSize: 12, minWidth: 'auto' }}
                      >
                        确认
                      </Button>
                    </Tooltip>
                    <Menu
                      anchorEl={anchorEl[result.id]}
                      open={Boolean(anchorEl[result.id])}
                      onClose={() => handleConfirmMenuClose(result.id, null)}
                    >
                      <MenuItem onClick={() => handleConfirmMenuClose(result.id, 'matched')}>
                        标记为符合
                      </MenuItem>
                      <MenuItem onClick={() => handleConfirmMenuClose(result.id, 'unmatched')}>
                        标记为不符合
                      </MenuItem>
                      <MenuItem onClick={() => handleConfirmMenuClose(result.id, 'needs_review')}>
                        标记为需确认
                      </MenuItem>
                    </Menu>
                  </TableCell>
                </TableRow>

                {/* Expandable detail row */}
                <TableRow>
                  <TableCell style={{ paddingBottom: 0, paddingTop: 0 }} colSpan={5}>
                    <Collapse in={isExpanded} timeout="auto" unmountOnExit>
                      <Box sx={{ p: 2, backgroundColor: '#F9F7FF' }}>
                        <Box
                          sx={{
                            mb: 1.5,
                            px: 1.25,
                            py: 1,
                            border: `1px solid ${riskConfig.border}`,
                            borderRadius: 1,
                            backgroundColor: '#FFFFFF',
                          }}
                        >
                          <Typography variant="caption" sx={{ color: config.color, fontWeight: 700 }}>
                            结论解释：{matchExplanation.title}
                          </Typography>
                          <Typography variant="body2" sx={{ color: riskConfig.color, mt: 0.4, fontWeight: 700 }}>
                            风险等级：{matchRisk.label}
                          </Typography>
                          <Box sx={{ mt: 0.4 }}>
                            <ClampedText text={`依据：${matchExplanation.basis}`} />
                          </Box>
                          <Box sx={{ mt: 0.4 }}>
                            <ClampedText
                              text={`建议动作：${matchRisk.action} ${matchExplanation.action}`}
                              color="text.secondary"
                            />
                          </Box>
                        </Box>

                        <Box
                          sx={{
                            mb: 1.5,
                            px: 1.25,
                            py: 1,
                            border: `1px solid ${summaryConfig.border}`,
                            borderRadius: 1,
                            backgroundColor: summaryConfig.bg,
                          }}
                        >
                          <Typography variant="caption" sx={{ color: summaryConfig.color, fontWeight: 700 }}>
                            证据链摘要
                          </Typography>
                          <Box sx={{ mt: 0.25 }}>
                            <ClampedText text={evidenceSummary.primaryText} color={summaryConfig.color} />
                          </Box>
                          {(evidenceSummary.missingLabels.length > 0 || evidenceSummary.reviewLabels.length > 0) && (
                            <Typography variant="caption" sx={{ color: '#6D4C41', display: 'block', mt: 0.5 }}>
                              {[
                                evidenceSummary.missingLabels.length
                                  ? `缺失/不满足 ${evidenceSummary.missingLabels.length} 项`
                                  : '',
                                evidenceSummary.reviewLabels.length
                                  ? `需复核 ${evidenceSummary.reviewLabels.length} 项`
                                  : '',
                              ]
                                .filter(Boolean)
                                .join('，')}
                            </Typography>
                          )}
                        </Box>

                        {/* Reason / match detail */}
                        {result.reason && (
                          <Box sx={{ mb: 1.5 }}>
                            <Typography variant="caption" sx={{ color: '#7C4DFF', fontWeight: 600 }}>
                              匹配详情
                            </Typography>
                            <ClampedText text={result.reason} />
                          </Box>
                        )}

                        {req && (
                          <Box sx={{ mb: 1.5 }}>
                            <Typography variant="caption" sx={{ color: '#7C4DFF', fontWeight: 600 }}>
                              标书要求原文
                            </Typography>
                            <ClampedText text={req.content || req.raw_text || req.title || '—'} />
                          </Box>
                        )}

                        {qual && (
                          <Box sx={{ mb: 1.5 }}>
                            <Typography variant="caption" sx={{ color: '#7C4DFF', fontWeight: 600 }}>
                              匹配到的资质记录
                            </Typography>
                            <ClampedText
                              text={[
                                qual.name,
                                qual.number ? `编号：${qual.number}` : '',
                                qual.issuing_authority ? `机构：${qual.issuing_authority}` : '',
                                qual.scope ? `范围：${qual.scope}` : '',
                                qual.expiry_date ? `有效期：${qual.expiry_date}` : '',
                              ]
                                .filter(Boolean)
                                .join(' · ') || '—'}
                            />
                            {qual.file_id ? (
                              <Box sx={{ mt: 0.75, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                                <Tooltip title="查看证据">
                                  <Button
                                    size="small"
                                    variant="outlined"
                                    startIcon={<VisibilityIcon />}
                                    onClick={() =>
                                      setPreview({
                                        fileId: qual.file_id as number,
                                        title: qual.name || '资质文件',
                                      })
                                    }
                                    sx={{ borderColor: '#7C4DFF', color: '#7C4DFF' }}
                                  >
                                    网页查看证据文件
                                  </Button>
                                </Tooltip>
                                <Tooltip title="新窗口打开证据">
                                  <Button
                                    size="small"
                                    component="a"
                                    href={getKnowledgeFilePreviewUrl(qual.file_id, 'inline')}
                                    target="_blank"
                                    rel="noreferrer"
                                    startIcon={<OpenInNewIcon />}
                                    sx={{ color: '#7C4DFF' }}
                                  >
                                    新窗口打开
                                  </Button>
                                </Tooltip>
                              </Box>
                            ) : (
                              <Typography variant="caption" sx={{ color: '#999' }}>
                                这条资质是手工录入或来源文件已删除，暂无可查看证据文件。
                              </Typography>
                            )}
                          </Box>
                        )}

                        {result.evidence_items.length > 0 && (
                          <Box sx={{ mb: 1.5 }}>
                            <Typography
                              variant="caption"
                              sx={{ color: '#7C4DFF', fontWeight: 600, display: 'block', mb: 0.75 }}
                            >
                              证据矩阵
                            </Typography>
                            {result.evidence_items
                              .filter((item) => isCustomTightenRuleEvidence(item.check_key))
                              .map((item) => (
                                <Box
                                  key={`${result.id}-${item.check_key}-notice`}
                                  sx={{
                                    mb: 1,
                                    px: 1.25,
                                    py: 1,
                                    border: '1px solid #EF5350',
                                    borderRadius: 1,
                                    backgroundColor: '#FFEBEE',
                                    display: 'flex',
                                    alignItems: 'flex-start',
                                    gap: 1,
                                  }}
                                >
                                  <CancelIcon sx={{ fontSize: 18, color: '#EF5350', mt: '1px' }} />
                                  <Box>
                                    <Typography variant="body2" sx={{ color: '#C62828', fontWeight: 700 }}>
                                      命中自定义收紧规则：{item.actual_value || item.label}
                                    </Typography>
                                    <Typography variant="caption" sx={{ color: '#6D4C41', display: 'block', mt: 0.25 }}>
                                      {item.reason || '该要求不能自动判定为符合，需要人工复核。'}
                                    </Typography>
                                  </Box>
                                </Box>
                              ))}
                            <TableContainer
                              component={Paper}
                              sx={{
                                boxShadow: 'none',
                                border: '1px solid #EDE7F6',
                                backgroundColor: '#FFFFFF',
                              }}
                            >
                              <Table size="small">
                                <TableHead>
                                  <TableRow sx={{ backgroundColor: '#F7F3FF' }}>
                                    <TableCell sx={{ fontWeight: 600, color: '#666', width: '16%' }}>
                                      核验项
                                    </TableCell>
                                    <TableCell sx={{ fontWeight: 600, color: '#666', width: '28%' }}>
                                      招标要求
                                    </TableCell>
                                    <TableCell sx={{ fontWeight: 600, color: '#666', width: '28%' }}>
                                      我的证据
                                    </TableCell>
                                    <TableCell sx={{ fontWeight: 600, color: '#666', width: '12%' }}>
                                      结果
                                    </TableCell>
                                    <TableCell sx={{ fontWeight: 600, color: '#666', width: '16%' }}>
                                      说明
                                    </TableCell>
                                  </TableRow>
                                </TableHead>
                                <TableBody>
                                  {result.evidence_items.map((item) => {
                                    const evidenceConfig = EVIDENCE_STATUS_CONFIG[item.status];
                                    const isCustomRule = isCustomTightenRuleEvidence(item.check_key);
                                    return (
                                      <TableRow
                                        key={`${result.id}-${item.check_key}`}
                                        sx={{
                                          backgroundColor: isCustomRule ? '#FFF5F5' : 'inherit',
                                          '& td': isCustomRule ? { borderTop: '1px solid #FFCDD2' } : undefined,
                                        }}
                                      >
                                        <TableCell>
                                          <ClampedText
                                            text={item.label}
                                            color={isCustomRule ? '#C62828' : 'text.primary'}
                                            fontWeight={600}
                                          />
                                        </TableCell>
                                        <TableCell>
                                          <ClampedText text={item.expected_value || '—'} />
                                        </TableCell>
                                        <TableCell>
                                          <ClampedText text={item.actual_value || '未识别'} />
                                        </TableCell>
                                        <TableCell>
                                          <Chip
                                            label={evidenceConfig.label}
                                            size="small"
                                            sx={{
                                              height: 22,
                                              fontSize: 12,
                                              fontWeight: 600,
                                              backgroundColor: evidenceConfig.bg,
                                              color: evidenceConfig.color,
                                              border: `1px solid ${evidenceConfig.color}`,
                                            }}
                                          />
                                        </TableCell>
                                        <TableCell>
                                          <ClampedText text={item.reason || '—'} color="text.secondary" />
                                        </TableCell>
                                      </TableRow>
                                    );
                                  })}
                                </TableBody>
                              </Table>
                            </TableContainer>
                          </Box>
                        )}

                        {/* For unmatched: 3-layer detail */}
                        {result.match_status === 'unmatched' && (
                          <Box
                            sx={{
                              border: '1px solid #EDE7F6',
                              borderRadius: 2,
                              p: 1.5,
                              backgroundColor: '#FFFFFF',
                            }}
                          >
                            <Typography
                              variant="caption"
                              sx={{ color: '#EF5350', fontWeight: 600, display: 'block', mb: 1 }}
                            >
                              不符合详情
                            </Typography>

                            {/* Layer 1: Specific mismatch point */}
                            {result.mismatch_detail && (
                              <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                                <Typography
                                  variant="body2"
                                  sx={{
                                    color: '#7C4DFF',
                                    fontWeight: 700,
                                    minWidth: 20,
                                  }}
                                >
                                  ①
                                </Typography>
                                <Box>
                                  <Typography variant="caption" sx={{ color: '#666' }}>
                                    不符合点
                                  </Typography>
                                  <ClampedText text={result.mismatch_detail} />
                                </Box>
                              </Box>
                            )}

                            {/* Layer 2: Expected qualification */}
                            {result.expected_qualification && (
                              <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                                <Typography
                                  variant="body2"
                                  sx={{ color: '#7C4DFF', fontWeight: 700, minWidth: 20 }}
                                >
                                  ②
                                </Typography>
                                <Box>
                                  <Typography variant="caption" sx={{ color: '#666' }}>
                                    期望资质
                                  </Typography>
                                  <ClampedText text={result.expected_qualification} />
                                </Box>
                              </Box>
                            )}

                            {/* Layer 3: Knowledge base status */}
                            <Box sx={{ display: 'flex', gap: 1 }}>
                              <Typography
                                variant="body2"
                                sx={{ color: '#7C4DFF', fontWeight: 700, minWidth: 20 }}
                              >
                                ③
                              </Typography>
                              <Box>
                                <Typography variant="caption" sx={{ color: '#666' }}>
                                  资质库检查
                                </Typography>
                                <ClampedText
                                  text={result.in_knowledge_base === true
                                    ? '✅ 已上传相关文件（参数不符，需更新资质信息）'
                                    : result.in_knowledge_base === false
                                      ? '⚠️ 未上传 → 请检查是否已有该资质并上传文件'
                                      : '—'}
                                />
                              </Box>
                            </Box>
                          </Box>
                        )}

                        {/* Similarity score */}
                        {result.similarity_score > 0 && (
                          <Typography variant="caption" sx={{ color: '#999', display: 'block', mt: 1 }}>
                            相似度：{(result.similarity_score * 100).toFixed(1)}%
                          </Typography>
                        )}
                      </Box>
                    </Collapse>
                  </TableCell>
                </TableRow>
              </React.Fragment>
            );
          })}
        </TableBody>
        </Table>
      </TableContainer>

      <Dialog
        open={preview !== null}
        onClose={() => setPreview(null)}
        maxWidth="lg"
        fullWidth
        PaperProps={{ sx: { height: '86vh' } }}
      >
        <DialogTitle
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 2,
            color: '#333',
            fontWeight: 700,
          }}
        >
          <span>{preview?.title || '证据文件'}</span>
          {preview && (
            <Button
              component="a"
              href={getKnowledgeFilePreviewUrl(preview.fileId, 'inline')}
              target="_blank"
              rel="noreferrer"
              size="small"
              startIcon={<OpenInNewIcon />}
              sx={{ color: '#7C4DFF' }}
            >
              新窗口打开
            </Button>
          )}
        </DialogTitle>
        <DialogContent sx={{ p: 0, height: '100%' }}>
          {preview && (
            <Box
              component="iframe"
              title="资质证据文件预览"
              src={getKnowledgeFilePreviewUrl(preview.fileId, 'inline')}
              sx={{
                width: '100%',
                height: '100%',
                border: 0,
                backgroundColor: '#F7F5FA',
              }}
            />
          )}
        </DialogContent>
      </Dialog>

      <Dialog
        open={pendingConfirm !== null}
        onClose={() => setPendingConfirm(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ color: '#333', fontWeight: 700 }}>
          人工确认匹配结果
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ color: '#666', mb: 1.5 }}>
            将该条结果标记为「{pendingConfirm?.label || '—'}」。修正原因会进入错例记录，后续可用于补规则。
          </Typography>
          <TextField
            fullWidth
            multiline
            minRows={3}
            required
            value={correctionReason}
            onChange={(event) => setCorrectionReason(event.target.value)}
            placeholder="例如：认证范围不覆盖本项目服务内容；证书有效期未覆盖投标截止日"
            label="修正原因"
            helperText="必填。该原因会进入错例库，并用于后续规则建议。"
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setPendingConfirm(null)} sx={{ color: '#666' }}>
            取消
          </Button>
          <Button
            variant="contained"
            onClick={handleConfirmSubmit}
            disabled={!canSubmitMatchConfirmation(correctionReason)}
            sx={{
              backgroundColor: '#7C4DFF',
              '&:hover': { backgroundColor: '#6A3EE6' },
            }}
          >
            确认
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default MatchResultTable;
