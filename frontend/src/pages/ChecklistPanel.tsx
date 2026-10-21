import { Alert, Box, Checkbox, Chip, Paper, Stack, Typography } from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type ChecklistItem } from '../lib/api';

interface Props {
  runId: string;
}

const severityLabel: Record<string, string> = {
  blocker: '阻断',
  warning: '警告',
  info: '提示',
};

export default function ChecklistPanel({ runId }: Props) {
  const queryClient = useQueryClient();
  const checklist = useQuery({
    queryKey: ['checklist', runId],
    queryFn: async () =>
      (await api.get<ChecklistItem[]>(`/analysis-runs/${runId}/checklist`)).data,
  });
  const toggle = useMutation({
    mutationFn: async (item: ChecklistItem) =>
      (
        await api.patch<ChecklistItem>(`/checklist/${item.id}`, {
          completed: !item.completed,
        })
      ).data,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['checklist', runId] });
      await queryClient.invalidateQueries({ queryKey: ['run', runId] });
    },
  });

  const open = checklist.data?.filter((item) => !item.completed) ?? [];
  return (
    <Stack spacing={2}>
      <Alert severity={open.length ? 'warning' : 'success'}>
        {open.length ? `仍有 ${open.length} 项交付事项未完成。` : '当前检查清单已全部完成。'}
      </Alert>
      <Paper variant="outlined" sx={{ bgcolor: 'rgba(255,253,247,.88)' }}>
        <Box sx={{ p: 2, borderBottom: '1px solid #ded5c5' }}>
          <Typography variant="h6">交付检查</Typography>
          <Typography variant="body2" color="text.secondary">
            未通过和待确认要求会自动生成待办；完成后再提交。
          </Typography>
        </Box>
        <Stack divider={<Box sx={{ borderBottom: '1px solid #eee7db' }} />}>
          {checklist.data?.map((item) => (
            <Stack key={item.id} direction="row" alignItems="flex-start" spacing={1.5} sx={{ p: 2 }}>
              <Checkbox
                checked={item.completed}
                disabled={toggle.isPending}
                onChange={() => toggle.mutate(item)}
              />
              <Box sx={{ flex: 1 }}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography fontWeight={600}>{item.title}</Typography>
                  <Chip
                    size="small"
                    color={item.severity === 'blocker' ? 'error' : 'warning'}
                    label={severityLabel[item.severity] ?? item.severity}
                  />
                </Stack>
                {item.detail && (
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                    {item.detail}
                  </Typography>
                )}
              </Box>
            </Stack>
          ))}
          {checklist.data?.length === 0 && (
            <Typography color="text.secondary" sx={{ p: 3 }}>
              分析完成后，这里会生成交付检查项。
            </Typography>
          )}
        </Stack>
      </Paper>
    </Stack>
  );
}
