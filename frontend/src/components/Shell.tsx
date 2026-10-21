import { AppBar, Box, Button, Container, Toolbar, Typography } from '@mui/material';
import { Link, Outlet, useLocation } from 'react-router-dom';

export default function Shell() {
  const location = useLocation();
  return (
    <Box minHeight="100vh">
      <AppBar
        position="sticky"
        elevation={0}
        sx={{
          bgcolor: 'rgba(244, 241, 232, 0.93)',
          color: 'text.primary',
          borderBottom: '1px solid #d8d0bf',
          backdropFilter: 'blur(14px)',
        }}
      >
        <Container maxWidth="xl">
          <Toolbar disableGutters sx={{ gap: 3 }}>
            <Typography
              component={Link}
              to="/"
              variant="h6"
              sx={{ fontWeight: 800, letterSpacing: '-0.04em', flexGrow: 1 }}
            >
              投标响应工作台
            </Typography>
            <Button component={Link} to="/" color={location.pathname === '/' ? 'primary' : 'inherit'}>
              项目
            </Button>
            <Button component={Link} to="/settings" color={location.pathname === '/settings' ? 'primary' : 'inherit'}>
              模型配置
            </Button>
          </Toolbar>
        </Container>
      </AppBar>
      <Container maxWidth="xl" sx={{ py: { xs: 3, md: 5 } }}>
        <Outlet />
      </Container>
    </Box>
  );
}
