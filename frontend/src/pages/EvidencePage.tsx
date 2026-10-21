import { Alert, Box, Chip, Divider, Paper, Stack, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { api, type Evidence } from '../lib/api';

export default function EvidencePage() {
  const { projectId = '' } = useParams();
  const evidence = useQuery({
    queryKey: ['evidence', projectId],
    queryFn: async () => (await api.get<Evidence[]>(`/projects/${projectId}/evidence`)).data,
  });

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="overline" color="secondary.main">
          EVIDENCE LIBRARY
        </Typography>
        <Typography variant="h3">证据库</Typography>
        <Typography color="text.secondary" sx={{ mt: 1 }}>
          企业资质、人员、业绩和财务证据都保留原文来源。
        </Typography>
      </Box>
      <Alert severity="info">
        当前证据通过 API 录入。后续会在文件解析完成后增加证据抽取和逐字段确认。
      </Alert>
      <Paper variant="outlined" sx={{ p: 3, bgcolor: 'rgba(255,253,247,.85)' }}>
        {evidence.data?.length === 0 && (
          <Typography color="text.secondary">暂无证据。</Typography>
        )}
        <Stack divider={<Divider flexItem />} spacing={2}>
          {evidence.data?.map((item) => (
            <Box key={item.id}>
              <Stack direction="row" justifyContent="space-between" gap={2}>
                <Box>
                  <Typography variant="h6">{item.title}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {item.holder || '主体未填写'} · {item.identifier || '编号未填写'}
                  </Typography>
                </Box>
                <Chip label={item.kind} size="small" />
              </Stack>
              <Typography variant="body2" sx={{ mt: 1 }}>
                {item.facts.length} 个结构化事实
              </Typography>
            </Box>
          ))}
        </Stack>
      </Paper>
      <Link to={`/projects/${projectId}`}>返回项目</Link>
    </Stack>
  );
}
