// RuleLibraryPage.tsx
// Revamp of 规则库 (DESIGN_SPEC.md §10).
// Swap `sampleRules` for real data — structure/markup is final.

import { useState } from 'react';
import {
  Box,
  Stack,
  Typography,
  Button,
  IconButton,
  Tooltip,
  Switch,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  Drawer,
  Divider,
  Chip,
} from '@mui/material';
import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import { CategoryTag, MandatoryTag, OverflowChipRow } from './StatusTags';
import { colors } from './theme';

interface Rule {
  id: string;
  name: string;
  key: string;
  domain: string;
  strictness: '严格' | '一般';
  keywords: string[];
  summary: string; // full 规则说明, shown in drawer
  hitAction: string; // full 命中动作, shown clamped in table + full in drawer
  source: string;
}

const sampleRules: Rule[] = [
  {
    id: '1',
    name: '投标保证金红线',
    key: 'submission.red_flag.deposit',
    domain: '投标待办',
    strictness: '严格',
    keywords: ['投标保证金', '保证金', '缴纳', '逾期', '无效投标', '不予受理'],
    summary:
      '保证金：金额、缴纳方式、到账/提交截止时间错误可导致废标。适用于所有涉及保证金条款的招标文件解析结果。',
    hitAction: '命中后标记为红线待办，需人工确认完成情况',
    source: '内置规则',
  },
  {
    id: '2',
    name: '提交截止时间红线',
    key: 'submission.red_flag.deadline',
    domain: '投标待办',
    strictness: '严格',
    keywords: ['截止时间', '递交截止', '提交截止', '逾期', '不予受理', '无效投标'],
    summary: '截止时间：投标文件、保证金或响应材料逾期可能导致无效投标。',
    hitAction: '命中后标记为红线待办，需人工确认完成情况',
    source: '内置规则',
  },
];

// ---------------------------------------------------------------------------

export default function RuleLibraryPage() {
  const [activeRule, setActiveRule] = useState<Rule | null>(null);

  return (
    <Box sx={{ p: 4 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" sx={{ mb: 3 }}>
        <Box>
          <Typography variant="h2">规则库</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            展示当前系统已启用的内置规则，用于核对哪些要求会被严格检查或标记为红线。
          </Typography>
        </Box>
        <Button variant="outlined" startIcon={<RefreshRoundedIcon />}>
          刷新
        </Button>
      </Stack>

      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell width={64}>启用</TableCell>
            <TableCell width={240}>规则</TableCell>
            <TableCell width={110}>业务域</TableCell>
            <TableCell width={90}>严格度</TableCell>
            <TableCell width={280}>关键词</TableCell>
            <TableCell>命中动作</TableCell>
            <TableCell width={60} align="right">
              详情
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {sampleRules.map((rule) => (
            <TableRow key={rule.id} className="zebra">
              <TableCell>
                <Switch size="small" defaultChecked />
              </TableCell>
              <TableCell>
                <Typography variant="body1" fontWeight={600}>
                  {rule.name}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {rule.key}
                </Typography>
              </TableCell>
              <TableCell>
                <CategoryTag category={rule.domain} />
              </TableCell>
              <TableCell>
                <MandatoryTag level={rule.strictness} />
              </TableCell>
              <TableCell>
                <OverflowChipRow items={rule.keywords} max={3} />
              </TableCell>
              <TableCell>
                <Tooltip title={rule.hitAction} arrow placement="top-start">
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{
                      display: '-webkit-box',
                      WebkitLineClamp: 1,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                      cursor: 'default',
                      maxWidth: 320,
                    }}
                  >
                    {rule.hitAction}
                  </Typography>
                </Tooltip>
              </TableCell>
              <TableCell align="right">
                <Tooltip title="查看详情">
                  <IconButton size="small" onClick={() => setActiveRule(rule)}>
                    <InfoOutlinedIcon fontSize="small" sx={{ color: 'text.secondary' }} />
                  </IconButton>
                </Tooltip>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {/* Detail drawer — replaces the old inline 规则说明 paragraph column */}
      <Drawer anchor="right" open={!!activeRule} onClose={() => setActiveRule(null)}>
        <Box sx={{ width: 420, p: 3 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
            <Typography variant="h3">{activeRule?.name}</Typography>
            <IconButton size="small" onClick={() => setActiveRule(null)}>
              <CloseRoundedIcon fontSize="small" />
            </IconButton>
          </Stack>

          <Stack direction="row" spacing={1} sx={{ mb: 3 }}>
            {activeRule && <CategoryTag category={activeRule.domain} />}
            {activeRule && <MandatoryTag level={activeRule.strictness} />}
          </Stack>

          <Typography variant="subtitle1" sx={{ mb: 1 }}>
            规则说明
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            {activeRule?.summary}
          </Typography>

          <Divider sx={{ mb: 3 }} />

          <Typography variant="subtitle1" sx={{ mb: 1 }}>
            关键词（全部）
          </Typography>
          <Stack direction="row" flexWrap="wrap" gap={0.75} sx={{ mb: 3 }}>
            {activeRule?.keywords.map((kw) => (
              <Chip key={kw} label={kw} size="small" variant="outlined" />
            ))}
          </Stack>

          <Divider sx={{ mb: 3 }} />

          <Typography variant="subtitle1" sx={{ mb: 1 }}>
            命中动作
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            {activeRule?.hitAction}
          </Typography>

          <Typography variant="caption" color="text.secondary">
            来源：{activeRule?.source}
          </Typography>
        </Box>
      </Drawer>
    </Box>
  );
}
