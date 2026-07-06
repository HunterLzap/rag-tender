// RequirementConfirmationPage.tsx
// Revamp of 标书解析与需求确认 (DESIGN_SPEC.md §9).
// Swap `sampleRows` / `sampleMeta` for real data — structure/markup is final.

import { useState } from 'react';
import {
  Box,
  Stack,
  Typography,
  Button,
  IconButton,
  Tooltip,
  Checkbox,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  ToggleButtonGroup,
  ToggleButton,
  Select,
  MenuItem,
  TextField,
  InputAdornment,
  LinearProgress,
  Divider,
  Chip,
} from '@mui/material';
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded';
import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded';
import SearchRoundedIcon from '@mui/icons-material/SearchRounded';
import OpenInNewRoundedIcon from '@mui/icons-material/OpenInNewRounded';
import EditRoundedIcon from '@mui/icons-material/EditRounded';
import CheckRoundedIcon from '@mui/icons-material/CheckRounded';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import { CategoryTag, MandatoryTag, StatusTag, DocCategory } from './StatusTags';
import { colors } from './theme';

// ---------------------------------------------------------------------------
// Reusable: 2-line clamp with full text on hover (DESIGN_SPEC §7.2)
// ---------------------------------------------------------------------------

function ClampedText({ title, body }: { title: string; body: string }) {
  return (
    <Tooltip title={body} arrow placement="top-start">
      <Box sx={{ maxWidth: 480, cursor: 'default' }}>
        <Typography variant="body1" fontWeight={600} noWrap>
          {title}
        </Typography>
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {body}
        </Typography>
      </Box>
    </Tooltip>
  );
}

// ---------------------------------------------------------------------------
// Sample data — shape matches the current 招标文件正文 requirement list
// ---------------------------------------------------------------------------

type RequirementStatus = 'pending' | 'confirmed';

interface RequirementRow {
  id: number;
  category: DocCategory;
  mandatory: '硬性' | '软性';
  title: string;
  detail: string;
  status: RequirementStatus;
  page: string;
}

const sampleRows: RequirementRow[] = [
  {
    id: 1,
    category: '提交件',
    mandatory: '硬性',
    title: '开标一览表',
    detail:
      '开标一览表中投标报价不得有选择或有条件的投标报价，表中某一包别填写多个报价，均为无效报价。',
    status: 'pending',
    page: 'P72',
  },
  {
    id: 2,
    category: '提交件',
    mandatory: '硬性',
    title: '投标函',
    detail:
      '投标人须提交投标函，声明同意遵守招标文件各项条款、无异议，并承诺投标文件资料真实、企业运营正常。',
    status: 'pending',
    page: 'P73',
  },
  {
    id: 3,
    category: '其他',
    mandatory: '硬性',
    title: '商业信誉和财务制度',
    detail: '投标人须具有良好的商业信誉和健全的财务会计制度。',
    status: 'pending',
    page: 'P74',
  },
  {
    id: 5,
    category: '财务',
    mandatory: '硬性',
    title: '依法缴纳税收和社保',
    detail: '投标人须具有依法缴纳税收和社会保障资金的良好记录。',
    status: 'confirmed',
    page: 'P74',
  },
];

const summary = { total: 22, capability: 8, submission: 14, confirmed: 6 };

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function RequirementConfirmationPage() {
  const [segment, setSegment] = useState('all');
  const [selected, setSelected] = useState<number[]>([]);

  const toggleRow = (id: number) =>
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  return (
    <Box sx={{ p: 4 }}>
      {/* Header ------------------------------------------------------- */}
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
        <IconButton size="small">
          <ArrowBackRoundedIcon fontSize="small" />
        </IconButton>
        <Typography variant="body2" color="text.secondary">
          返回标书列表
        </Typography>
      </Stack>

      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" sx={{ mb: 3 }}>
        <Box>
          <Typography variant="h2">标书解析与需求确认</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            当前文件：招标文件正文
          </Typography>
        </Box>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <Chip
            label={`已确认 ${summary.confirmed}/${summary.total}`}
            size="small"
            sx={{ backgroundColor: colors.status.neutralBg, color: colors.status.neutral, fontWeight: 600 }}
          />
          <Button variant="outlined" startIcon={<RefreshRoundedIcon />}>
            按新分类重新解析
          </Button>
        </Stack>
      </Stack>

      {/* Toolbar: segmented filter + category + search ---------------- */}
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <ToggleButtonGroup
          value={segment}
          exclusive
          size="small"
          onChange={(_, v) => v && setSegment(v)}
        >
          <ToggleButton value="all">全部 {summary.total}</ToggleButton>
          <ToggleButton value="capability">能力要求 {summary.capability}</ToggleButton>
          <ToggleButton value="submission">提交资料 {summary.submission}</ToggleButton>
        </ToggleButtonGroup>

        <Stack direction="row" spacing={1.5}>
          <Select size="small" defaultValue="all" sx={{ minWidth: 140 }}>
            <MenuItem value="all">全部类别</MenuItem>
            <MenuItem value="提交件">提交件</MenuItem>
            <MenuItem value="财务">财务</MenuItem>
          </Select>
          <TextField
            size="small"
            placeholder="搜索解析结果..."
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchRoundedIcon fontSize="small" sx={{ color: 'text.disabled' }} />
                </InputAdornment>
              ),
            }}
          />
        </Stack>
      </Stack>

      {/* Table ---------------------------------------------------------- */}
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell padding="checkbox" />
            <TableCell width={48}>序号</TableCell>
            <TableCell width={110}>类别</TableCell>
            <TableCell width={90}>级别</TableCell>
            <TableCell>AI 提取的需求及核心指标</TableCell>
            <TableCell width={110}>状态</TableCell>
            <TableCell width={70}>原文</TableCell>
            <TableCell width={140} align="right">
              操作
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {sampleRows.map((row, i) => (
            <TableRow key={row.id} className="zebra" sx={{ '&:nth-of-type(odd)': i % 2 === 0 ? {} : {} }}>
              <TableCell padding="checkbox">
                <Checkbox
                  size="small"
                  checked={selected.includes(row.id)}
                  onChange={() => toggleRow(row.id)}
                />
              </TableCell>
              <TableCell>{row.id}</TableCell>
              <TableCell>
                <CategoryTag category={row.category} />
              </TableCell>
              <TableCell>
                <MandatoryTag level={row.mandatory} />
              </TableCell>
              <TableCell>
                <ClampedText title={row.title} body={row.detail} />
              </TableCell>
              <TableCell>
                {row.status === 'confirmed' ? (
                  <StatusTag kind="success" label="已确认" />
                ) : (
                  <StatusTag kind="neutral" label="待确认" />
                )}
              </TableCell>
              <TableCell>
                <Tooltip title="查看原文">
                  <Button
                    size="small"
                    startIcon={<OpenInNewRoundedIcon sx={{ fontSize: 14 }} />}
                    sx={{ minWidth: 0, color: 'primary.main', fontWeight: 500 }}
                  >
                    {row.page}
                  </Button>
                </Tooltip>
              </TableCell>
              <TableCell align="right">
                {/* DESIGN_SPEC §7.5 — edit/confirm grouped, delete separated */}
                <Stack direction="row" spacing={0.5} justifyContent="flex-end" alignItems="center">
                  <Tooltip title="编辑">
                    <IconButton size="small">
                      <EditRoundedIcon fontSize="small" sx={{ color: 'text.secondary' }} />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="确认无误">
                    <IconButton size="small">
                      <CheckRoundedIcon fontSize="small" sx={{ color: colors.status.success }} />
                    </IconButton>
                  </Tooltip>
                  <Divider orientation="vertical" flexItem sx={{ mx: 0.5, height: 16, alignSelf: 'center' }} />
                  <Tooltip title="删除">
                    <IconButton
                      size="small"
                      sx={{
                        color: 'text.secondary',
                        '&:hover': { color: 'error.main', backgroundColor: colors.status.errorBg },
                      }}
                    >
                      <DeleteOutlineRoundedIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Stack>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {/* Footer: batch actions ------------------------------------------ */}
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mt: 2 }}>
        <Button size="small" sx={{ color: 'primary.main' }}>
          + 手动添加需求项
        </Button>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <Typography variant="body2" color="text.secondary">
            已选 {selected.length} 项
          </Typography>
          <Button size="small" variant="outlined">
            批量确认无误
          </Button>
          <Button size="small" variant="outlined" color="error">
            批量删除
          </Button>
        </Stack>
      </Stack>
    </Box>
  );
}
