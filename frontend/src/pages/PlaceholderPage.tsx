import React from 'react';
import { Box, Card, Typography } from '@mui/material';

interface PlaceholderPageProps {
  title: string;
  subtitle?: string;
}

export const PlaceholderPage: React.FC<PlaceholderPageProps> = ({ title, subtitle }) => {
  return (
    <Box>
      <Box sx={{ mb: 2 }}>
        <Typography variant="h1" sx={{ color: 'text.primary', fontWeight: 500 }}>
          {title}
        </Typography>
        {subtitle && (
          <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '13px' }}>
            {subtitle}
          </Typography>
        )}
      </Box>

      <Card sx={{ p: 4, textAlign: 'center', border: '1px solid', borderColor: 'divider' }}>
        <Typography variant="h6" sx={{ color: 'text.primary', mb: 1 }}>
          {title} Workspace View
        </Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          Authorized forensic records module connected to live append-only audit trail.
        </Typography>
      </Card>
    </Box>
  );
};

