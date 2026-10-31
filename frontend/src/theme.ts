import { createTheme } from '@mui/material/styles';

export const getTheme = (mode: 'dark' | 'light') => {
  const isDark = mode === 'dark';

  return createTheme({
    palette: {
      mode,
      background: {
        default: isDark ? '#212121' : '#f4f5f7',
        paper: isDark ? '#2a2a2a' : '#ffffff',
      },
      primary: {
        main: isDark ? '#3f7fe0' : '#1f63c9',
      },
      success: {
        main: isDark ? '#5cb867' : '#2e7d32',
      },
      warning: {
        main: isDark ? '#f5a623' : '#b36b00',
      },
      error: {
        main: isDark ? '#ef5350' : '#c62828',
      },
      text: {
        primary: isDark ? '#e6e6e6' : '#1c2430',
        secondary: isDark ? '#a0a0a0' : '#5f6b7a',
      },
      divider: isDark ? '#3b3b3b' : '#dfe3e8',
    },
    typography: {
      fontFamily: 'Roboto, sans-serif',
      fontSize: 14,
      h1: { fontSize: '24px', fontWeight: 500 },
      h2: { fontSize: '18px', fontWeight: 500 },
      h3: { fontSize: '16px', fontWeight: 500 },
      body1: { fontSize: '14px' },
      body2: { fontSize: '13px' },
      caption: { fontSize: '12px' },
    },
    shape: {
      borderRadius: 3,
    },
    components: {
      MuiButton: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            fontWeight: 500,
            borderRadius: '3px',
          },
        },
      },
      MuiTableCell: {
        styleOverrides: {
          root: {
            padding: '6px 12px',
            fontSize: '13px',
            borderColor: isDark ? '#3b3b3b' : '#dfe3e8',
          },
          head: {
            backgroundColor: isDark ? '#2f2f2f' : '#eef0f3',
            color: isDark ? '#e6e6e6' : '#1c2430',
            fontWeight: 600,
            fontSize: '12px',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
          },
        },
      },
      MuiTableRow: {
        styleOverrides: {
          root: {
            '&:hover': {
              backgroundColor: isDark ? 'rgba(255, 255, 255, 0.03)' : 'rgba(0, 0, 0, 0.02)',
            },
          },
        },
      },
    },
  });
};

