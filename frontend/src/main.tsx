import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { CssBaseline, ThemeProvider, createTheme } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import './styles.css';

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: '#B7432B' },
    secondary: { main: '#1D5C56' },
    background: { default: '#F4F1E8', paper: '#FFFDF7' },
    text: { primary: '#24201A', secondary: '#685F52' },
  },
  typography: {
    fontFamily: '"Songti SC", "Noto Serif CJK SC", Georgia, serif',
    h1: { fontFamily: '"PingFang SC", "Hiragino Sans GB", sans-serif', fontWeight: 700 },
    h2: { fontFamily: '"PingFang SC", "Hiragino Sans GB", sans-serif', fontWeight: 700 },
    h3: { fontFamily: '"PingFang SC", "Hiragino Sans GB", sans-serif', fontWeight: 700 },
    button: { fontFamily: '"PingFang SC", "Hiragino Sans GB", sans-serif', textTransform: 'none' },
  },
  shape: { borderRadius: 4 },
});

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
