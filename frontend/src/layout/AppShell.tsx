import React from 'react';
import { Outlet } from 'react-router-dom';
import { Box, Typography } from '@mui/material';
import { Sidebar } from './Sidebar';

interface AppShellProps {
  mode: 'dark' | 'light';
  onToggleTheme: () => void;
}

export const AppShell: React.FC<AppShellProps> = ({ mode, onToggleTheme }) => {
  return (
    <Box sx={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden' }}>
      <Sidebar mode={mode} onToggleTheme={onToggleTheme} />
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          height: '100vh',
          overflowY: 'auto',
          backgroundColor: 'background.default',
          display: 'flex',
          flexDirection: 'column',
          p: 3,
        }}
      >
        <Box sx={{ flexGrow: 1 }}>
          <Outlet />
        </Box>
        <Box sx={{ mt: 4, pt: 2, borderTop: '1px solid', borderColor: 'divider', textAlign: 'right' }}>
          <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '11px' }}>
            © 2026 SealTrail &nbsp;|&nbsp; Prove it hasn't changed.
          </Typography>
        </Box>
      </Box>
    </Box>
  );
};

