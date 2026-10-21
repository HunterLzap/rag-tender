import { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardActionArea,
  CardContent,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api, type Project } from '../lib/api';

const statusText: Record<string, string> = {
  active: '进行中',
  archived: '已归档',
};

export default function ProjectsPage() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [tenderNo, setTenderNo] = useState('');
  const projects = useQuery({
    queryKey: ['projects'],
    queryFn: async () => (await api.get<Project[]>('/projects')).data,
  });
  const create = useMutation({
    mutationFn: async () =>
      (
        await api.post<Project>('/projects', {
          name,
          tender_no: tenderNo || null,
        })
      ).data,
    onSuccess: async () => {
      setOpen(false);
      setName('');
      setTenderNo('');
      await queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });

  return (
    <Stack spacing={4}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          gap: 2,
          flexWrap: 'wrap',
        }}
      >
        <Box>
          <Typography variant="overline" color="secondary.main">
            BID RESPONSE WORKSPACE
          </Typography>
          <Typography variant="h3" sx={{ mb: 1 }}>
            项目
          </Typography>
          <Typography color="text.secondary" maxWidth={680}>
            从招标文件到处理结论，所有内容都保留原文位置和证据来源。
          </Typography>
        </Box>
        <Button variant="contained" size="large" onClick={() => setOpen(true)}>
          新建投标项目
        </Button>
      </Box>

      {projects.error && <Alert severity="error">项目加载失败</Alert>}
      {projects.data?.length === 0 && (
        <Box
          sx={{
            border: '1px dashed #b8aa94',
            p: 8,
            textAlign: 'center',
            bgcolor: 'rgba(255, 253, 247, 0.6)',
          }}
        >
          <Typography variant="h5" sx={{ mb: 1 }}>
            还没有项目
          </Typography>
          <Typography color="text.secondary">先建立项目，再上传招标文件。</Typography>
        </Box>
      )}
      <Grid container spacing={2.5}>
        {projects.data?.map((project) => (
          <Grid key={project.id} item xs={12} md={6} xl={4}>
            <Card variant="outlined" sx={{ bgcolor: 'rgba(255,253,247,.85)', height: '100%' }}>
              <CardActionArea
                component={Link}
                to={`/projects/${project.id}`}
                sx={{ height: '100%', p: 1 }}
              >
                <CardContent>
                  <Stack direction="row" justifyContent="space-between" spacing={2}>
                    <Typography variant="overline" color="primary.main">
                      {statusText[project.status] ?? project.status}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {project.document_count} 份文件
                    </Typography>
                  </Stack>
                  <Typography variant="h5" sx={{ mt: 1.5, mb: 1 }}>
                    {project.name}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {project.tender_no || '未填写招标编号'}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                    {project.latest_run_id
                      ? `最近分析：${project.latest_run_status ?? '处理中'}`
                      : '尚未开始分析'}
                  </Typography>
                </CardContent>
              </CardActionArea>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>新建投标项目</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <TextField
              label="项目名称"
              value={name}
              onChange={(event) => setName(event.target.value)}
              autoFocus
              required
            />
            <TextField
              label="招标编号"
              value={tenderNo}
              onChange={(event) => setTenderNo(event.target.value)}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>取消</Button>
          <Button variant="contained" disabled={!name.trim() || create.isPending} onClick={() => create.mutate()}>
            创建项目
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
