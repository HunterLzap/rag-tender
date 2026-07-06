import React, { useState, useCallback } from 'react';
import { Outlet } from 'react-router-dom';
import { Box, IconButton, Tooltip } from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import Sidebar from './Sidebar';
import ApiConfigDialog from './ApiConfigDialog';
import { getApiConfigButtonSx, getApiConfigHotspotSx } from './layoutApiConfigTrigger';

/**
 * Main layout: left Sidebar + content Outlet.
 * API config is available through a hidden top-right gear hotspot.
 */
const Layout: React.FC = () => {
  const [configOpen, setConfigOpen] = useState(false);
  const [configTriggerVisible, setConfigTriggerVisible] = useState(false);

  const handleOpenConfig = useCallback(() => setConfigOpen(true), []);
  const handleCloseConfig = useCallback(() => setConfigOpen(false), []);

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <Sidebar />
      <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
        <Box component="main" sx={{ flexGrow: 1, p: 3, backgroundColor: '#FFFFFF' }}>
          <Outlet />
        </Box>
      </Box>

      <Box
        className="api-config-hotspot"
        onMouseEnter={() => setConfigTriggerVisible(true)}
        onMouseLeave={() => setConfigTriggerVisible(false)}
        sx={getApiConfigHotspotSx()}
      >
        <Tooltip title="API 配置">
          <IconButton
            aria-label="API 配置"
            onClick={handleOpenConfig}
            onFocus={() => setConfigTriggerVisible(true)}
            onBlur={() => setConfigTriggerVisible(false)}
            size="small"
            sx={getApiConfigButtonSx(configTriggerVisible)}
          >
            <SettingsIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>

      <ApiConfigDialog open={configOpen} onClose={handleCloseConfig} />
    </Box>
  );
};

export default Layout;
