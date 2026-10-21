import { alpha, createTheme } from '@mui/material/styles';

export const colors = {
  brand: '#B7432B',
  brandDark: '#943620',
  teal: '#1D5C56',
  canvas: '#F6F7F9',
  paper: '#FFFFFF',
  ink: '#202939',
  muted: '#667085',
  border: '#E4E7EC',
};

const fontFamily = '"Avenir Next", "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", sans-serif';

export const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: colors.brand, dark: colors.brandDark },
    secondary: { main: colors.teal },
    background: { default: colors.canvas, paper: colors.paper },
    text: { primary: colors.ink, secondary: colors.muted },
    divider: colors.border,
    success: { main: '#167451' },
    warning: { main: '#9A6300' },
    error: { main: '#C4323B' },
    info: { main: '#285DAA' },
  },
  typography: {
    fontFamily,
    fontSize: 14,
    h1: { fontSize: '2rem', fontWeight: 700, lineHeight: 1.3 },
    h2: { fontSize: '1.75rem', fontWeight: 700, lineHeight: 1.4 },
    h3: { fontSize: '1.65rem', fontWeight: 700, lineHeight: 1.4 },
    h4: { fontSize: '1.4rem', fontWeight: 700, lineHeight: 1.4 },
    h5: { fontSize: '1.125rem', fontWeight: 600 },
    h6: { fontSize: '1rem', fontWeight: 600 },
    subtitle1: { fontSize: '0.9375rem', fontWeight: 600 },
    subtitle2: { fontSize: '0.875rem', fontWeight: 600 },
    body1: { fontSize: '0.875rem', lineHeight: 1.7 },
    body2: { fontSize: '0.8125rem', lineHeight: 1.7 },
    caption: { fontSize: '0.75rem', lineHeight: 1.6 },
    button: { fontSize: '0.875rem', fontWeight: 600, textTransform: 'none' },
    overline: { fontSize: '0.6875rem', fontWeight: 600, letterSpacing: '0.08em' },
  },
  shape: { borderRadius: 8 },
  components: {
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: { minHeight: 36, paddingInline: 16, whiteSpace: 'nowrap' },
        sizeSmall: { minHeight: 30, paddingInline: 10, fontSize: 12 },
        sizeLarge: { minHeight: 42 },
        outlined: { borderColor: colors.border },
      },
    },
    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: { outlined: { borderColor: colors.border, backgroundImage: 'none' } },
    },
    MuiTextField: { defaultProps: { size: 'small', fullWidth: true } },
    MuiOutlinedInput: {
      styleOverrides: {
        root: { backgroundColor: '#FFF', fontSize: 14 },
        notchedOutline: { borderColor: '#D0D5DD' },
      },
    },
    MuiChip: {
      defaultProps: { size: 'small' },
      styleOverrides: {
        root: { borderRadius: 5, fontSize: 12, fontWeight: 500 },
        colorSuccess: { backgroundColor: '#EAF7F0', color: '#126443' },
        colorWarning: { backgroundColor: '#FFF4DF', color: '#875400' },
        colorError: { backgroundColor: '#FDECEB', color: '#B4232B' },
        colorInfo: { backgroundColor: '#EBF2FE', color: '#285DAA' },
        colorPrimary: { backgroundColor: alpha(colors.brand, 0.09), color: colors.brandDark },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: { borderRadius: 8, paddingBlock: 6, fontSize: 13 },
        standardInfo: { backgroundColor: '#EFF5FF', color: '#244D80' },
        standardWarning: { backgroundColor: '#FFF7E8', color: '#805319' },
        standardSuccess: { backgroundColor: '#EDF8F1', color: '#156046' },
      },
    },
    MuiDialogTitle: { styleOverrides: { root: { fontSize: 18, fontWeight: 600, padding: 24 } } },
    MuiDialogActions: { styleOverrides: { root: { padding: '16px 24px', gap: 8, borderTop: `1px solid ${colors.border}` } } },
    MuiTableCell: {
      styleOverrides: {
        root: { borderBottomColor: colors.border, fontSize: 13, padding: '14px 16px' },
        head: { background: '#F9FAFB', color: colors.muted, fontWeight: 600 },
      },
    },
    MuiTabs: { styleOverrides: { root: { minHeight: 48 }, indicator: { height: 3 } } },
    MuiTab: { styleOverrides: { root: { textTransform: 'none', minHeight: 48, fontSize: 14 } } },
  },
});
