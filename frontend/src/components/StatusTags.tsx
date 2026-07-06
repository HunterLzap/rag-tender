import { Chip, Stack, Tooltip } from '@mui/material';
import { alpha } from '@mui/material/styles';
import BookmarkIcon from '@mui/icons-material/Bookmark';
import CancelRoundedIcon from '@mui/icons-material/CancelRounded';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import CircleIcon from '@mui/icons-material/Circle';
import HourglassBottomRoundedIcon from '@mui/icons-material/HourglassBottomRounded';
import PriorityHighRoundedIcon from '@mui/icons-material/PriorityHighRounded';
import type { ElementType, ReactNode } from 'react';
import { colors } from '../theme';

export type DocCategory = keyof typeof colors.category;

export function CategoryTag({ category }: { category: DocCategory | string }) {
  const hex = (colors.category as Record<string, string>)[category] ?? colors.category.其他;

  return (
    <Chip
      label={category}
      size="small"
      variant="outlined"
      sx={{
        color: hex,
        borderColor: alpha(hex, 0.45),
        backgroundColor: alpha(hex, 0.07),
      }}
    />
  );
}

export type StatusKind = 'success' | 'info' | 'error' | 'neutral';

const STATUS_CONFIG: Record<
  StatusKind,
  { text: string; bg: string; icon: ElementType }
> = {
  success: { text: colors.status.success, bg: colors.status.successBg, icon: CheckCircleRoundedIcon },
  info: { text: colors.status.info, bg: colors.status.infoBg, icon: HourglassBottomRoundedIcon },
  error: { text: colors.status.error, bg: colors.status.errorBg, icon: CancelRoundedIcon },
  neutral: { text: colors.status.neutral, bg: colors.status.neutralBg, icon: CircleIcon },
};

export function StatusTag({ kind, label }: { kind: StatusKind; label: string }) {
  const cfg = STATUS_CONFIG[kind];
  const Icon = cfg.icon;

  return (
    <Chip
      icon={<Icon sx={{ fontSize: '14px !important', color: `${cfg.text} !important` }} />}
      label={label}
      size="small"
      sx={{
        color: cfg.text,
        backgroundColor: cfg.bg,
        '& .MuiChip-icon': { marginLeft: '6px' },
      }}
    />
  );
}

export function MandatoryTag({
  level,
}: {
  level: '硬性' | '软性' | '严格' | '一般' | '平衡' | '宽松';
}) {
  const isStrict = level === '硬性' || level === '严格';

  return (
    <Chip
      icon={<BookmarkIcon sx={{ fontSize: '13px !important', color: `${colors.mandatory.main} !important` }} />}
      label={level}
      size="small"
      sx={{
        color: colors.mandatory.main,
        backgroundColor: isStrict ? colors.mandatory.bg : alpha(colors.mandatory.main, 0.04),
        borderRadius: '4px',
        opacity: isStrict ? 1 : 0.7,
      }}
    />
  );
}

export function ActionTag({ label }: { label: string }) {
  return (
    <Chip
      icon={
        <PriorityHighRoundedIcon
          sx={{ fontSize: '13px !important', color: `${colors.warning.main} !important` }}
        />
      }
      label={label}
      size="small"
      sx={{
        color: colors.warning.main,
        backgroundColor: colors.warning.bg,
      }}
    />
  );
}

export function OverflowChipRow({
  items,
  max = 3,
  renderChip,
}: {
  items: string[];
  max?: number;
  renderChip?: (item: string) => ReactNode;
}) {
  const visible = items.slice(0, max);
  const hidden = items.slice(max);

  return (
    <Stack direction="row" spacing={0.5} flexWrap="nowrap" alignItems="center">
      {visible.map((item) =>
        renderChip ? (
          <span key={item}>{renderChip(item)}</span>
        ) : (
          <Chip key={item} label={item} size="small" variant="outlined" />
        ),
      )}
      {hidden.length > 0 && (
        <Tooltip title={hidden.join(' · ')} arrow>
          <Chip
            label={`+${hidden.length}`}
            size="small"
            variant="outlined"
            sx={{ color: colors.status.neutral, cursor: 'default' }}
          />
        </Tooltip>
      )}
    </Stack>
  );
}
