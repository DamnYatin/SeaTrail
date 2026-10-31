import React from 'react';
import { Box, Typography } from '@mui/material';

export const BrandGlyph: React.FC = () => {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
      <svg width="28" height="32" viewBox="0 0 28 32" fill="none" xmlns="http://www.w3.org/2000/svg">
        <polygon points="14,2 26,8 26,24 14,30 2,24 2,8" stroke="#3f7fe0" strokeWidth="2.5" fill="none" />
        <circle cx="14" cy="16" r="5" fill="#3f7fe0" />
      </svg>
      <Box>
        <Typography
          variant="h6"
          sx={{
            fontWeight: 800,
            fontSize: '17px',
            letterSpacing: '1px',
            lineHeight: 1.1,
            color: 'text.primary',
          }}
        >
          SEALTRAIL
        </Typography>
        <Typography
          variant="caption"
          sx={{
            fontSize: '10px',
            color: 'text.secondary',
            letterSpacing: '0.3px',
            display: 'block',
          }}
        >
          Prove it hasn't changed
        </Typography>
      </Box>
    </Box>
  );
};

