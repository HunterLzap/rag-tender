import { useState } from 'react';
import {
  AppBar, Box, Breadcrumbs, Button, Chip, Collapse, Divider, Drawer, IconButton,
  Link as MuiLink, List, ListItemButton, ListItemIcon, ListItemText, Stack,
  Toolbar, Typography,
} from '@mui/material';
import ArticleOutlined from '@mui/icons-material/ArticleOutlined';
import DashboardOutlined from '@mui/icons-material/DashboardOutlined';
import SettingsOutlined from '@mui/icons-material/SettingsOutlined';
import FolderOutlined from '@mui/icons-material/FolderOutlined';
import HelpOutlineRounded from '@mui/icons-material/HelpOutlineRounded';
import MenuRounded from '@mui/icons-material/MenuRounded';
import CloseRounded from '@mui/icons-material/CloseRounded';
import ExpandMoreRounded from '@mui/icons-material/ExpandMoreRounded';
import ChevronRightRounded from '@mui/icons-material/ChevronRightRounded';
import NavigateNextRounded from '@mui/icons-material/NavigateNextRounded';
import { useQuery } from '@tanstack/react-query';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { api, type AnalysisRun, type Project } from '../lib/api';

const sidebarWidth = 216;

export default function Shell() {
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [projectOpen, setProjectOpen] = useState(true);
  const [helpOpen, setHelpOpen] = useState(false);
  const routeProjectId = location.pathname.match(/^\/projects\/([^/]+)/)?.[1];
  const runId = location.pathname.match(/^\/runs\/([^/]+)/)?.[1];
  const run = useQuery({
    queryKey: ['run', runId],
    enabled: Boolean(runId),
    queryFn: async () => (await api.get<AnalysisRun>(`/analysis-runs/${runId}`)).data,
  });
  const projectId = routeProjectId ?? run.data?.project_id;
  const project = useQuery({
    queryKey: ['project', projectId],
    enabled: Boolean(projectId),
    queryFn: async () => (await api.get<Project>(`/projects/${projectId}`)).data,
  });
  const projectRuns = useQuery({
    queryKey: ['runs', projectId],
    enabled: Boolean(projectId && !runId),
    queryFn: async () => (await api.get<AnalysisRun[]>(`/projects/${projectId}/analysis-runs`)).data,
  });
  const latestRunId = runId ?? projectRuns.data?.[0]?.id;
  const runtime = useQuery({
    queryKey: ['runtime'],
    queryFn: async () => (await api.get<{ live_model_calls: boolean }>('/health')).data,
  });
  const tab = new URLSearchParams(location.search).get('tab') ?? 'requirements';
  const sectionTitle = location.pathname === '/' ? '全部项目'
    : location.pathname === '/settings' ? '模型设置'
      : location.pathname.endsWith('/evidence') ? '证据资料'
        : runId ? ({ requirements: '要求核对', fill: '填写建议', checklist: '检查导出' }[tab] ?? '要求核对')
          : location.hash === '#history' ? '分析记录' : '资料准备';
  const submenus = [
    { label: '资料准备', to: `/projects/${projectId}`, selected: Boolean(routeProjectId && !location.pathname.endsWith('/evidence') && location.hash !== '#history') },
    { label: '要求核对', to: `/runs/${latestRunId}?tab=requirements`, selected: Boolean(runId && tab === 'requirements'), disabled: !latestRunId },
    { label: '填写建议', to: `/runs/${latestRunId}?tab=fill`, selected: Boolean(runId && tab === 'fill'), disabled: !latestRunId },
    { label: '检查导出', to: `/runs/${latestRunId}?tab=checklist`, selected: Boolean(runId && tab === 'checklist'), disabled: !latestRunId },
    { label: '证据资料', to: `/projects/${projectId}/evidence`, selected: location.pathname.endsWith('/evidence') },
    { label: '分析记录', to: `/projects/${projectId}#history`, selected: location.hash === '#history' },
  ];
  const nav = (
    <Stack sx={{ height: '100%', bgcolor: '#FFF', borderRight: '1px solid', borderColor: 'divider' }}>
      <Box component={Link} to="/" onClick={() => setMobileOpen(false)} sx={{ display: 'flex', alignItems: 'center', gap: 1.25, height: 76, px: 2.5 }}>
        <Box sx={{ width: 35, height: 38, display: 'grid', placeItems: 'center', bgcolor: 'primary.main', color: '#FFF', borderRadius: 1.25 }}><ArticleOutlined /></Box>
        <Box><Typography fontWeight={700} sx={{ fontSize: 15 }}>投标响应工作台</Typography><Typography variant="overline" color="text.secondary" sx={{ fontSize: 9 }}>TENDER WORKSPACE</Typography></Box>
      </Box>
      <Box sx={{ px: 1.5, pt: 2, flex: 1 }}>
        <List sx={{ pt: 1 }}>
          <ListItemButton component={Link} to="/" selected={location.pathname === '/'} onClick={() => setMobileOpen(false)} sx={navStyle}>
            <ListItemIcon sx={{ minWidth: 34, color: 'inherit' }}><DashboardOutlined fontSize="small" /></ListItemIcon><ListItemText primary="全部项目" />
          </ListItemButton>
          {projectId && <>
            <ListItemButton onClick={() => setProjectOpen(!projectOpen)} aria-expanded={projectOpen} sx={{ ...navStyle, mt: 1 }}>
              <ListItemIcon sx={{ minWidth: 34 }}><FolderOutlined fontSize="small" /></ListItemIcon>
              <ListItemText primary="当前项目" secondary={project.data?.name ?? '正在加载…'} secondaryTypographyProps={{ noWrap: true, fontSize: 11 }} />
              {projectOpen ? <ExpandMoreRounded fontSize="small" /> : <ChevronRightRounded fontSize="small" />}
            </ListItemButton>
            <Collapse in={projectOpen}>
              <List component="div" disablePadding sx={{ ml: 2.25, pl: 1, borderLeft: '1px solid', borderColor: 'divider' }}>
                {submenus.map((item) => (
                  <ListItemButton key={item.label} component={Link} to={item.to} selected={item.selected} disabled={item.disabled} onClick={() => setMobileOpen(false)} sx={{ ...navStyle, py: 0.6, pl: 2 }} aria-current={item.selected ? 'page' : undefined}>
                    <ListItemText primary={item.label} primaryTypographyProps={{ fontSize: 13 }} />
                    {item.selected && <Box sx={{ width: 5, height: 5, borderRadius: '50%', bgcolor: 'primary.main' }} />}
                  </ListItemButton>
                ))}
              </List>
            </Collapse>
          </>}
        </List>
        <Divider sx={{ my: 2 }} />
        <List>
          <ListItemButton component={Link} to="/settings" selected={location.pathname === '/settings'} onClick={() => setMobileOpen(false)} sx={navStyle}>
            <ListItemIcon sx={{ minWidth: 34, color: 'inherit' }}><SettingsOutlined fontSize="small" /></ListItemIcon><ListItemText primary="模型设置" />
          </ListItemButton>
          <ListItemButton onClick={() => { setHelpOpen(true); setMobileOpen(false); }} sx={navStyle}>
            <ListItemIcon sx={{ minWidth: 34 }}><HelpOutlineRounded fontSize="small" /></ListItemIcon><ListItemText primary="操作指南" />
          </ListItemButton>
        </List>
      </Box>
    </Stack>
  );

  return (
    <Box minHeight="100vh">
      <a href="#main-content" className="skip-link">跳到主要内容</a>
      <Box component="aside" sx={{ width: sidebarWidth, position: 'fixed', inset: '0 auto 0 0', display: { xs: 'none', md: 'block' }, zIndex: 1200 }}>{nav}</Box>
      <Drawer open={mobileOpen} onClose={() => setMobileOpen(false)} sx={{ display: { md: 'none' } }} PaperProps={{ sx: { width: sidebarWidth } }}>{nav}</Drawer>
      <Box sx={{ ml: { md: `${sidebarWidth}px` } }}>
        <AppBar position="sticky" elevation={0} sx={{ bgcolor: 'rgba(255,255,255,.96)', color: 'text.primary', borderBottom: '1px solid', borderColor: 'divider', backdropFilter: 'blur(12px)' }}>
          <Toolbar sx={{ minHeight: '52px !important', gap: 1, px: { xs: 2, lg: 3 } }}>
            <IconButton aria-label="打开导航菜单" onClick={() => setMobileOpen(true)} sx={{ display: { md: 'none' }, mr: 1 }}><MenuRounded /></IconButton>
            <Breadcrumbs aria-label="面包屑导航" separator={<NavigateNextRounded sx={{ fontSize: 15 }} />} sx={{ flex: 1, minWidth: 0, '& ol': { flexWrap: 'nowrap' } }}>
              <MuiLink component={Link} to="/" underline="hover" color="text.secondary" fontSize={13}>项目</MuiLink>
              {projectId && <MuiLink component={Link} to={`/projects/${projectId}`} underline="hover" color="text.secondary" sx={{ display: 'block', maxWidth: { xs: 95, sm: 250 }, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 13 }}>{project.data?.name ?? '当前项目'}</MuiLink>}
              <Typography color="text.primary" fontSize={13} aria-current="page">{sectionTitle}</Typography>
            </Breadcrumbs>
            {runtime.data && <Chip label={runtime.data.live_model_calls ? '模型调用已启用' : '离线模式'} variant="outlined" sx={{ display: { xs: 'none', sm: 'inline-flex' }, bgcolor: '#F9FAFB', borderColor: 'divider', color: 'text.secondary', mr: 1 }} />}
            <IconButton aria-label="打开操作指南" onClick={() => setHelpOpen(true)}><HelpOutlineRounded fontSize="small" /></IconButton>
          </Toolbar>
        </AppBar>
        <Box component="main" id="main-content" className="workspace-content" sx={{ maxWidth: 1600, mx: 'auto', px: { xs: 2, sm: 3 }, py: 2.5 }}>
          <Outlet />
        </Box>
      </Box>
      <Drawer anchor="right" open={helpOpen} onClose={() => setHelpOpen(false)} PaperProps={{ sx: { width: { xs: '100%', sm: 420 } } }}>
        <Stack sx={{ p: 3 }} spacing={2.5}>
          <Stack direction="row" alignItems="center" justifyContent="space-between"><Typography variant="h5">操作指南</Typography><IconButton onClick={() => setHelpOpen(false)} aria-label="关闭操作指南"><CloseRounded /></IconButton></Stack>
          <Typography color="text.secondary">按以下四步准备投标响应。每次返回项目，都可以从当前进度继续。</Typography>
          {[
            ['1', '准备资料', '新建项目，上传招标文件及投标模板；补充投标人、截止时间和准备填写的内容。证明材料在「证据资料」中登记。'],
            ['2', '核对要求', '可创建人工工作台，或在模型启用后开始分析。逐条查看原文和证据；漏提要求可手工补充，并保存复核结论。'],
            ['3', '确认填写', '选择模板，逐项确认内容。漏识别的位置可在原页手工框选，保存后同步更新标注图。'],
            ['4', '检查导出', '处理交付清单后下载资料包，包含检查报告、填写清单和标注图。标注图用于填写参考，原始文件不会自动改写。'],
          ].map(([number, title, text]) => <Stack key={number} direction="row" gap={1.5}><Chip label={number} color="primary" /><Box><Typography variant="subtitle2">{title}</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{text}</Typography></Box></Stack>)}
          <Divider />
          <Typography variant="subtitle2">上传时该选哪种文件？</Typography>
          <Typography variant="body2" color="text.secondary">招标文件：采购方发布的要求。投标模板：需要你填写的空表或格式文件。证明材料：用于证明资质、人员、业绩和财务情况的文件。</Typography>
          <Typography variant="subtitle2">状态怎么理解？</Typography>
          <Stack direction="row" gap={1} flexWrap="wrap"><Chip color="success" label="绿色 · 已完成 / 已确认" /><Chip color="warning" label="黄色 · 待补充 / 待复核" /><Chip color="error" label="红色 · 不符合 / 未完成" /></Stack>
          <Typography variant="body2" color="text.secondary">离线模式可以新建人工工作台、补充要求、校正扫描页文字、框选填写位置和导出资料；真实模型分析和连接测试保持关闭。</Typography>
          <Button variant="outlined" onClick={() => setHelpOpen(false)}>我知道了，继续操作</Button>
        </Stack>
      </Drawer>
    </Box>
  );
}

const navStyle = {
  borderRadius: 1, mb: 0.5, py: 1, color: 'text.secondary',
  '& .MuiListItemText-primary': { fontSize: 14 },
  '&.Mui-selected': { bgcolor: 'rgba(183,67,43,.07)', color: 'primary.main', '& .MuiListItemText-primary': { fontWeight: 600 } },
  '&.Mui-selected:hover': { bgcolor: 'rgba(183,67,43,.11)' },
};
