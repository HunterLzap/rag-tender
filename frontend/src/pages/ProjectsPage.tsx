import { useState } from 'react';
import {
  Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, InputAdornment,
  MenuItem, Paper, Stack, Table, TableBody, TableCell, TableContainer, TableHead,
  TablePagination, TableRow, TextField, Typography,
} from '@mui/material';
import AddRounded from '@mui/icons-material/AddRounded';
import SearchRounded from '@mui/icons-material/SearchRounded';
import ArrowForwardRounded from '@mui/icons-material/ArrowForwardRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { api, apiError, type Organization, type Project } from '../lib/api';
import { formatDate } from '../lib/format';
import { ConfirmDialog, EmptyState, Notice, PageHeader, StatusChip } from '../components/Workspace';

export default function ProjectsPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Project | null>(null);
  const [deleting, setDeleting] = useState<Project | null>(null);
  const [name, setName] = useState('');
  const [tenderNo, setTenderNo] = useState('');
  const [organizationId, setOrganizationId] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('active');
  const [page, setPage] = useState(0);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const projects = useQuery({
    queryKey: ['projects'],
    queryFn: async () => (await api.get<Project[]>('/projects')).data,
  });
  const organizations = useQuery({
    queryKey: ['organizations'],
    queryFn: async () => (await api.get<Organization[]>('/organizations')).data,
  });
  const selectedOrganization = organizationId ?? (!editing ? organizations.data?.[0]?.id ?? '' : '');
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['projects'] });
  const save = useMutation({
    mutationFn: async () => {
      const payload = {
        name: name.trim(), tender_no: tenderNo.trim() || null,
        organization_id: selectedOrganization || null,
      };
      return (editing
        ? await api.patch<Project>(`/projects/${editing.id}`, payload)
        : await api.post<Project>('/projects', payload)).data;
    },
    onSuccess: async (project) => {
      setOpen(false);
      await refresh();
      if (!editing) navigate(`/projects/${project.id}`);
      else setMessage('项目信息已更新');
    },
    onError: (err) => setError(apiError(err, '保存项目失败')),
  });
  const archive = useMutation({
    mutationFn: async (project: Project) => api.patch(`/projects/${project.id}`, { status: project.status === 'archived' ? 'active' : 'archived' }),
    onSuccess: async () => { setMessage('项目状态已更新'); await refresh(); },
    onError: (err) => setError(apiError(err, '更新项目失败')),
  });
  const remove = useMutation({
    mutationFn: async () => api.delete(`/projects/${deleting!.id}`),
    onSuccess: async () => { setDeleting(null); setPage(0); setMessage('项目已删除'); await refresh(); },
    onError: (err) => { setDeleting(null); setError(apiError(err, '删除项目失败')); },
  });
  function edit(project: Project | null) {
    setEditing(project); setName(project?.name ?? ''); setTenderNo(project?.tender_no ?? '');
    setOrganizationId(project ? project.organization_id ?? '' : null);
    setError(''); setMessage(''); setOpen(true); save.reset();
  }
  const rows = (projects.data ?? []).filter((project) =>
    (filter === 'all' || project.status === filter)
    && `${project.name} ${project.tender_no ?? ''}`.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <Stack spacing={2}>
      <PageHeader title="项目" actions={<Button variant="contained" startIcon={<AddRounded />} onClick={() => edit(null)}>新建项目</Button>} />
      <Notice message={message} onClose={() => setMessage('')} />
      {error && !open && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      {projects.error && <Alert severity="error">项目加载失败，请刷新页面重试。</Alert>}
      <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={2} sx={{ p: 2.5, borderBottom: '1px solid', borderColor: 'divider' }}>
          <Typography variant="body2" color="text.secondary" sx={{ alignSelf: { sm: 'center' } }}>{rows.length} 个项目</Typography>
          <Stack direction="row" gap={1}>
            <TextField label="搜索项目" placeholder="项目名称或招标编号" value={search} onChange={(event) => { setSearch(event.target.value); setPage(0); }} InputProps={{ startAdornment: <InputAdornment position="start"><SearchRounded sx={{ fontSize: 18 }} /></InputAdornment> }} sx={{ width: { xs: '100%', sm: 250 } }} />
            <TextField select label="项目状态" value={filter} onChange={(event) => { setFilter(event.target.value); setPage(0); }} sx={{ minWidth: 115, width: 125 }}><MenuItem value="active">进行中</MenuItem><MenuItem value="archived">已归档</MenuItem><MenuItem value="all">全部状态</MenuItem></TextField>
          </Stack>
        </Stack>
        {projects.isLoading ? <EmptyState title="正在加载项目" loading /> : rows.length ? <>
          <TableContainer>
            <Table sx={{ minWidth: 700 }} aria-label="投标项目列表">
              <TableHead><TableRow><TableCell>项目名称 / 招标编号</TableCell><TableCell>文件</TableCell><TableCell>当前进度</TableCell><TableCell>更新时间</TableCell><TableCell align="right">操作</TableCell></TableRow></TableHead>
              <TableBody>{rows.slice(page * 10, page * 10 + 10).map((project) => <TableRow key={project.id} hover>
                <TableCell><Typography component={Link} to={`/projects/${project.id}`} fontWeight={600} sx={{ display: 'block', '&:hover': { color: 'primary.main' } }}>{project.name}</Typography><Typography variant="caption" color="text.secondary">{project.tender_no || '未填写招标编号'}</Typography></TableCell>
                <TableCell>{project.document_count} 份</TableCell>
                <TableCell><StatusChip status={project.status === 'archived' ? 'archived' : project.latest_run_status ?? 'pending'} label={!project.latest_run_id && project.status !== 'archived' ? '待准备资料' : undefined} /></TableCell>
                <TableCell sx={{ whiteSpace: 'nowrap' }}>{formatDate(project.updated_at)}</TableCell>
                <TableCell align="right"><Stack direction="row" gap={0.25} justifyContent="flex-end"><Button size="small" onClick={() => edit(project)}>编辑</Button><Button size="small" color="inherit" disabled={archive.isPending} onClick={() => archive.mutate(project)}>{project.status === 'archived' ? '恢复' : '归档'}</Button><Button size="small" color="error" onClick={() => setDeleting(project)}>删除</Button><Button component={Link} to={`/projects/${project.id}`} size="small" aria-label={`进入项目 ${project.name}`}><ArrowForwardRounded sx={{ fontSize: 17 }} /></Button></Stack></TableCell>
              </TableRow>)}</TableBody>
            </Table>
          </TableContainer>
          <TablePagination component="div" count={rows.length} rowsPerPage={10} rowsPerPageOptions={[10]} page={page} onPageChange={(_, next) => setPage(next)} labelDisplayedRows={({ from, to, count }) => `${from}–${to} / 共 ${count} 项`} getItemAriaLabel={(type) => type === 'next' ? '下一页' : '上一页'} />
        </> : <EmptyState title={search ? '没有匹配的项目' : '还没有项目'} description={search ? '换个关键词试试，或切换项目状态。' : '新建项目后，先上传采购方发布的招标文件。'} action={<Button variant="contained" onClick={() => edit(null)}>新建项目</Button>} />}
      </Paper>
      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>{editing ? '编辑项目' : '新建投标项目'}</DialogTitle>
        <DialogContent><Stack spacing={2.5} sx={{ pt: 1 }}>
          {save.isError && <Alert severity="error">{error}</Alert>}
          <TextField label="项目名称" placeholder="例如：2026 年配电柜采购项目" value={name} onChange={(event) => setName(event.target.value)} autoFocus required />
          <TextField label="招标编号（选填）" value={tenderNo} onChange={(event) => setTenderNo(event.target.value)} />
          <TextField select label="投标企业" value={selectedOrganization} onChange={(event) => setOrganizationId(event.target.value)} helperText="引用企业资料库，材料可跨项目复用。"><MenuItem value="">暂不关联</MenuItem>{organizations.data?.map((item) => <MenuItem key={item.id} value={item.id}>{item.name}</MenuItem>)}</TextField>
          {!organizations.data?.length && <Button component={Link} to="/library">先建立企业资料库</Button>}
        </Stack></DialogContent>
        <DialogActions><Button onClick={() => setOpen(false)}>取消</Button><Button variant="contained" disabled={!name.trim() || save.isPending} onClick={() => save.mutate()}>{save.isPending ? '保存中…' : editing ? '保存修改' : '创建并准备资料'}</Button></DialogActions>
      </Dialog>
      <ConfirmDialog open={Boolean(deleting)} title="删除项目？" description={`将删除「${deleting?.name ?? ''}」及其文件记录、分析结果、填写建议和证据资料。此操作无法撤销。`} pending={remove.isPending} onClose={() => setDeleting(null)} onConfirm={() => remove.mutate()} />
    </Stack>
  );
}
