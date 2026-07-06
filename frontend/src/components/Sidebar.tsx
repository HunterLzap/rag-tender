import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Box,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
  Divider,
} from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import DescriptionIcon from '@mui/icons-material/Description';
import LibraryBooksIcon from '@mui/icons-material/LibraryBooks';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import RuleIcon from '@mui/icons-material/Rule';
import SettingsIcon from '@mui/icons-material/Settings';
import appIcon from '../assets/icon.svg';

interface NavItem {
  label: string;
  path: string;
  icon: React.ReactNode;
}

const NAV_ITEMS: NavItem[] = [
  { label: '仪表盘', path: '/', icon: <DashboardIcon /> },
  { label: '标书解析', path: '/tenders', icon: <DescriptionIcon /> },
  { label: '资质库', path: '/knowledge', icon: <LibraryBooksIcon /> },
  { label: '匹配结果', path: '/match', icon: <CompareArrowsIcon /> },
  { label: '错例库', path: '/corrections', icon: <RuleIcon /> },
  { label: '规则库', path: '/rules', icon: <RuleIcon /> },
  { label: '设置', path: '/settings', icon: <SettingsIcon /> },
];

/**
 * Left navigation sidebar.
 * Active item highlighted with primary purple background.
 */
const Sidebar: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();

  const isActive = (path: string): boolean => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  return (
    <Box
      sx={{
        width: 220,
        flexShrink: 0,
        backgroundColor: '#FFFFFF',
        borderRight: '1px solid #EDE7F6',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Logo area */}
      <Box sx={{ px: 2, py: 1.5, textAlign: 'center' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1.25 }}>
          <Box
            component="img"
            src={appIcon}
            alt=""
            sx={{
              width: 76,
              height: 76,
              objectFit: 'cover',
              flexShrink: 0,
            }}
          />
          <Typography
            variant="h6"
            sx={{
              fontWeight: 700,
              color: '#7C4DFF',
              fontSize: 28,
              lineHeight: 1.15,
              whiteSpace: 'nowrap',
              flexShrink: 0,
            }}
          >
            资质通
          </Typography>
        </Box>
      </Box>

      <Divider sx={{ borderColor: '#EDE7F6' }} />

      {/* Navigation */}
      <List sx={{ pt: 1.5, px: 1 }}>
        {NAV_ITEMS.map((item) => {
          const active = isActive(item.path);
          return (
            <ListItemButton
              key={item.path}
              onClick={() => navigate(item.path)}
              sx={{
                mb: 0.5,
                borderRadius: 2,
                backgroundColor: active ? '#EDE7F6' : 'transparent',
                '&:hover': {
                  backgroundColor: active ? '#EDE7F6' : '#F9F7FF',
                },
              }}
            >
              <ListItemIcon
                sx={{
                  minWidth: 36,
                  color: active ? '#7C4DFF' : '#666',
                }}
              >
                {item.icon}
              </ListItemIcon>
              <ListItemText
                primary={item.label}
                primaryTypographyProps={{
                  fontSize: 14,
                  fontWeight: active ? 600 : 400,
                  color: active ? '#7C4DFF' : '#333',
                }}
              />
            </ListItemButton>
          );
        })}
      </List>

      <Box sx={{ flexGrow: 1 }} />

      {/* Bottom status */}
      <Box sx={{ p: 2, borderTop: '1px solid #EDE7F6' }}>
        <Typography variant="caption" sx={{ color: '#999', display: 'block' }}>
          v1.0.0 · 本地部署
        </Typography>
      </Box>
    </Box>
  );
};

export default Sidebar;
