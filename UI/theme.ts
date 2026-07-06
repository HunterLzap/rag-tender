// theme.ts
// MUI v5 theme implementing DESIGN_SPEC.md. Wrap the app root:
//   <ThemeProvider theme={theme}><CssBaseline />{app}</ThemeProvider>

import { createTheme, alpha } from '@mui/material/styles';

// ---------------------------------------------------------------------------
// Design tokens — exported separately so components can reference raw values
// (e.g. custom tag components in StatusTags.tsx) without reaching into the
// theme object.
// ---------------------------------------------------------------------------

export const colors = {
  primary: {
    main: '#7C5CFC',
    light: '#9B81FF',
    dark: '#5B3FD1',
    contrastText: '#FFFFFF',
  },
  status: {
    success: '#1B8A5A',
    successBg: '#E7F6EE',
    info: '#2E6ADE',
    infoBg: '#E9F0FD',
    error: '#C4362E',
    errorBg: '#FBEAE9',
    neutral: '#5B5F6B',
    neutralBg: '#EEEFF2',
  },
  // Deliberately NOT part of the success/info/error/neutral status family —
  // see DESIGN_SPEC.md §1.3. Only <ActionTag> may use this.
  warning: {
    main: '#B5750A',
    bg: '#FDF1DD',
  },
  // Deliberately NOT orange — see DESIGN_SPEC.md §1.3. Only <MandatoryTag> uses this.
  mandatory: {
    main: '#1F2430',
    bg: '#E7E8EC',
  },
  disabled: {
    text: '#9CA0AB',
    bg: '#F2F3F5',
  },
  divider: '#E4E5EA',
  surface: '#FFFFFF',
  surfaceAlt: '#FAFAFB', // zebra stripe on compact tables
  canvas: '#F5F5F7',
  category: {
    提交件: '#5B4FE9',
    资质: '#2E6ADE',
    业绩: '#1B8A5A',
    财务: '#B5750A',
    人员: '#C4362E',
    产品参数: '#0E8C8C',
    其他: '#5B5F6B',
  },
} as const;

export const spacingTokens = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

// ---------------------------------------------------------------------------
// Theme
// ---------------------------------------------------------------------------

const theme = createTheme({
  palette: {
    primary: colors.primary,
    success: { main: colors.status.success },
    info: { main: colors.status.info },
    error: { main: colors.status.error },
    warning: { main: colors.warning.main }, // used sparingly — see spec §1.3
    text: {
      primary: '#1A1C23',
      secondary: colors.status.neutral,
      disabled: colors.disabled.text,
    },
    divider: colors.divider,
    background: {
      default: colors.canvas,
      paper: colors.surface,
    },
  },
  shape: { borderRadius: 8 },
  spacing: 8, // theme.spacing(1) === 8px, per DESIGN_SPEC.md §3
  typography: {
    fontFamily: '"Inter", "PingFang SC", "Microsoft YaHei", Roboto, sans-serif',
    h1: { fontSize: 28, fontWeight: 700, lineHeight: 1.3 },
    h2: { fontSize: 22, fontWeight: 700, lineHeight: 1.35 },
    h3: { fontSize: 17, fontWeight: 600, lineHeight: 1.4 },
    subtitle1: { fontSize: 14, fontWeight: 600, lineHeight: 1.4 },
    body1: { fontSize: 14, fontWeight: 400, lineHeight: 1.6 },
    body2: { fontSize: 13, fontWeight: 400, lineHeight: 1.5 },
    caption: { fontSize: 12, fontWeight: 400, lineHeight: 1.4 },
    button: { fontSize: 14, fontWeight: 600, textTransform: 'none' },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: { backgroundColor: colors.canvas },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: { borderRadius: 6, paddingInline: 16, boxShadow: 'none' },
        contained: {
          '&:hover': { boxShadow: 'none' },
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: { borderRadius: 6 },
        sizeSmall: { padding: 6 },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { borderRadius: 6, fontWeight: 600, fontSize: 12 },
        sizeSmall: { height: 22 },
        outlined: { backgroundColor: 'transparent' },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          border: `1px solid ${colors.divider}`,
          boxShadow: 'none',
          borderRadius: 10,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        // Only affects elevation-based paper (menus, popovers); Card above
        // is the source of truth for bordered surfaces.
        elevation1: { boxShadow: '0 2px 8px rgba(20, 20, 30, 0.08)' },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderColor: colors.divider,
          padding: '10px 12px',
          fontSize: 13,
        },
        head: {
          fontWeight: 600,
          fontSize: 12,
          color: colors.status.neutral,
          backgroundColor: colors.surfaceAlt,
          textTransform: 'none',
        },
        sizeSmall: { padding: '6px 12px' }, // compact density, DESIGN_SPEC §5
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          '&.zebra:nth-of-type(odd)': {
            backgroundColor: colors.surfaceAlt,
          },
          '&:hover': {
            backgroundColor: alpha(colors.primary.main, 0.04),
          },
        },
      },
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          fontSize: 12,
          backgroundColor: '#1A1C23',
          padding: '6px 10px',
        },
      },
    },
    MuiSwitch: {
      styleOverrides: {
        switchBase: {
          '&.Mui-checked': { color: colors.primary.main },
          '&.Mui-checked + .MuiSwitch-track': {
            backgroundColor: colors.primary.main,
          },
        },
      },
    },
  },
});

export default theme;
