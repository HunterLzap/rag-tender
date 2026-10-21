import type { ReactNode } from 'react';
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogContentText, DialogTitle, Paper, Snackbar, Stack, Typography,
} from '@mui/material';
import ArrowForwardRounded from '@mui/icons-material/ArrowForwardRounded';
import CheckCircleOutlineRounded from '@mui/icons-material/CheckCircleOutlineRounded';
import FolderOpenOutlined from '@mui/icons-material/FolderOpenOutlined';
import { Link } from 'react-router-dom';
import { statusColor, statusLabels } from '../lib/labels';

export function PageHeader({ title, description, eyebrow, actions }: {
  title: string; description?: string; eyebrow?: string; actions?: ReactNode;
}) {
  return (
    <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={2} alignItems={{ sm: 'center' }}>
      <Box minWidth={0}>
        {eyebrow && <Typography variant="overline" color="primary.main">{eyebrow}</Typography>}
        <Typography component="h1" variant="h5" sx={{ fontSize: 20, overflowWrap: 'anywhere' }}>{title}</Typography>
        {description && <Typography color="text.secondary" sx={{ mt: 0.75, maxWidth: 760 }}>{description}</Typography>}
      </Box>
      {actions && <Stack direction="row" gap={1} flexWrap="wrap" flexShrink={0}>{actions}</Stack>}
    </Stack>
  );
}

export function Notice({ message, onClose }: { message: string; onClose: () => void }) {
  return <Snackbar open={Boolean(message)} autoHideDuration={3500} onClose={onClose} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}><Alert severity="success" onClose={onClose} variant="filled" sx={{ boxShadow: 2 }}>{message}</Alert></Snackbar>;
}

const steps = [
  ['准备资料', '上传文件 · 补充信息'],
  ['核对要求', '检查原文 · 复核结论'],
  ['填写建议', '确认内容 · 查看标注'],
  ['检查导出', '处理待办 · 导出报告'],
];

export function WorkflowNav({ projectId, runId, active }: { projectId: string; runId?: string; active: number }) {
  const paths = [
    `/projects/${projectId}`,
    `/runs/${runId}?tab=requirements`,
    `/runs/${runId}?tab=fill`,
    `/runs/${runId}?tab=checklist`,
  ];
  return (
    <Paper variant="outlined" component="nav" aria-label="投标准备流程" sx={{ p: 1, display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' }, gap: 0.5 }}>
      {steps.map(([title, detail], index) => (
        <Button
          key={title} component={Link} to={paths[index]} disabled={index > 0 && !runId}
          aria-current={active === index ? 'step' : undefined}
          sx={{ justifyContent: 'flex-start', textAlign: 'left', p: { xs: 1, sm: 1.5 }, color: active === index ? 'primary.main' : 'text.secondary', bgcolor: active === index ? 'primary.main' : undefined, '&[aria-current="step"]': { bgcolor: 'rgba(183,67,43,.07)' } }}
        >
          <Box sx={{ width: 30, height: 30, borderRadius: 1, flexShrink: 0, mr: 1.25, display: 'grid', placeItems: 'center', fontWeight: 700, bgcolor: active === index ? 'primary.main' : '#F0F2F5', color: active === index ? '#FFF' : 'text.secondary' }}>{index + 1}</Box>
          <Box>
            <Typography variant="subtitle2" color="inherit">{title}</Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: { xs: 'none', sm: 'block' } }}>{detail}</Typography>
          </Box>
        </Button>
      ))}
    </Paper>
  );
}

export function Guidance({ title, children, action, step }: { title: string; children: ReactNode; action?: ReactNode; step?: string }) {
  return (
    <Paper variant="outlined" sx={{ p: 2, borderLeft: '3px solid', borderLeftColor: 'primary.main', background: 'linear-gradient(105deg, #FFF8F4, #FFFFFF 76%)' }}>
      <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" alignItems={{ sm: 'center' }} gap={2}>
        <Box>
          <Stack direction="row" gap={1} alignItems="center" flexWrap="wrap" sx={{ mb: 0.5 }}>
            {step && <Chip label={step} color="primary" size="small" />}
            <Typography variant="subtitle2">{title}</Typography>
          </Stack>
          <Typography variant="body2" color="text.secondary" component="div">{children}</Typography>
        </Box>
        {action && <Box flexShrink={0}>{action}</Box>}
      </Stack>
    </Paper>
  );
}

export function EmptyState({ title, description, action, loading = false }: { title: string; description?: string; action?: ReactNode; loading?: boolean }) {
  return (
    <Stack alignItems="center" textAlign="center" spacing={1.5} sx={{ px: 3, py: 5 }}>
      <Box sx={{ width: 48, height: 48, bgcolor: '#F1F3F6', color: 'text.secondary', borderRadius: 2, display: 'grid', placeItems: 'center' }}>
        {loading ? <CircularProgress size={22} /> : <FolderOpenOutlined />}
      </Box>
      <Typography variant="subtitle1">{title}</Typography>
      {description && <Typography variant="body2" color="text.secondary" maxWidth={480}>{description}</Typography>}
      {action}
    </Stack>
  );
}

export function StatusChip({ status, label }: { status: string; label?: string }) {
  return <Chip size="small" color={statusColor(status)} label={label ?? statusLabels[status] ?? '待处理'} />;
}

export function ConfirmDialog({ open, title, description, pending, onClose, onConfirm }: {
  open: boolean; title: string; description: string; pending?: boolean; onClose: () => void; onConfirm: () => void;
}) {
  return (
    <Dialog open={open} onClose={pending ? undefined : onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent><DialogContentText>{description}</DialogContentText></DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={pending}>取消</Button>
        <Button color="error" variant="contained" onClick={onConfirm} disabled={pending}>{pending ? '正在删除…' : '确认删除'}</Button>
      </DialogActions>
    </Dialog>
  );
}

export function NextButton({ to, children }: { to: string; children: ReactNode }) {
  return <Button component={Link} to={to} variant="contained" endIcon={<ArrowForwardRounded fontSize="small" />}>{children}</Button>;
}

export function ReadyItem({ label, ready }: { label: string; ready: boolean }) {
  return <Stack direction="row" gap={1} alignItems="center"><CheckCircleOutlineRounded sx={{ fontSize: 17, color: ready ? 'success.main' : '#98A2B3' }} /><Typography variant="body2" color={ready ? 'text.primary' : 'text.secondary'}>{label}</Typography></Stack>;
}
