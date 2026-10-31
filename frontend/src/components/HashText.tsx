import React, { useState } from 'react';
import { Box, IconButton, Tooltip, Typography } from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import CheckIcon from '@mui/icons-material/Check';

interface HashTextProps {
  hash: string;
  truncate?: boolean;
}

export const HashText: React.FC<HashTextProps> = ({ hash, truncate = false }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(hash);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const displayText = truncate && hash.length > 16 ? `${hash.slice(0, 8)}...${hash.slice(-8)}` : hash;

  return (
    <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
      <Typography
        component="span"
        sx={{
          fontFamily: 'Courier, monospace',
          fontSize: '12px',
          color: 'text.primary',
          wordBreak: 'break-all',
        }}
      >
        {displayText}
      </Typography>
      <Tooltip title={copied ? 'Copied!' : 'Copy Hash'}>
        <IconButton size="small" onClick={handleCopy} sx={{ padding: '2px' }}>
          {copied ? <CheckIcon sx={{ fontSize: '13px', color: 'success.main' }} /> : <ContentCopyIcon sx={{ fontSize: '13px' }} />}
        </IconButton>
      </Tooltip>
    </Box>
  );
};

