// StatusTags.tsx
// The four dedicated tag families from DESIGN_SPEC.md §6. Each family owns
// its own shape/color — never mix these visually, and never reuse the
// warning amber outside <ActionTag>.

import { Chip, Stack, Tooltip } from '@mui/material';
import { alpha } from '@mui/material/styles';
import BookmarkIcon from '@mui/icons-material/Bookmark';
import PriorityHighRoundedIcon from '@mui/icons-material/PriorityHighRounded';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import HourglassBottomRoundedIcon from '@mui/icons-material/HourglassBottomRounded';
import CancelRoundedIcon from '@mui/icons-material/CancelRounded';
import CircleIcon from '@mui/icons-material/Circle';
import { colors } from './theme';

// ---------------------------------------------------------------------------
// 1. Document Category Tag — outlined, one fixed hue per category, everywhere
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// 2. Status Tag — filled, semantic (success / info / error / neutral only)
// ---------------------------------------------------------------------------

export type StatusKind = 'success' | 'info' | 'error' | 'neutral';

const STATUS_CONFIG: Record<
  StatusKind,
  { text: string; bg: string; icon: React.ElementType }
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

// ---------------------------------------------------------------------------
// 3. Mandatory Level Tag — dark neutral, square-ish, never orange.
//    This is a rule ATTRIBUTE, not a task state.
// ---------------------------------------------------------------------------

export function MandatoryTag({ level }: { level: '硬性' | '软性' | '严格' | '一般' }) {
  const isStrict = level === '硬性' || level === '严格';
  return (
    <Chip
      icon={<BookmarkIcon sx={{ fontSize: '13px !important', color: `${colors.mandatory.main} !important` }} />}
      label={level}
      size="small"
      sx={{
        color: colors.mandatory.main,
        backgroundColor: isStrict ? colors.mandatory.bg : alpha(colors.mandatory.main, 0.04),
        borderRadius: '4px', // squarer than the default 6px chip — visually distinct family
        opacity: isStrict ? 1 : 0.7,
      }}
    />
  );
}

// ---------------------------------------------------------------------------
// 4. Action Reminder Tag — the ONLY tag family allowed to use warning amber.
//    Means "a human needs to do something now."
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Helper: keyword/overflow chip row for table cells (DESIGN_SPEC §7.3)
// Shows up to `max` chips, then a "+N" chip with a tooltip listing the rest.
// ---------------------------------------------------------------------------

export function OverflowChipRow({
  items,
  max = 3,
  renderChip,
}: {
  items: string[];
  max?: number;
  renderChip?: (item: string) => React.ReactNode;
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
        )
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
