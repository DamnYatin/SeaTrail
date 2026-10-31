import React from 'react';
import { Chip } from '@mui/material';

interface StatusChipProps {
  status: string;
  size?: 'small' | 'medium';
}

export const StatusChip: React.FC<StatusChipProps> = ({ status, size = 'small' }) => {
  let color: 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' = 'default';
  const label = status.replace(/_/g, ' ');

  switch (status.toUpperCase()) {
    case 'OK':
    case 'VERIFIED':
    case 'IN_CUSTODY':
    case 'APPROVED':
    case 'COMPLETED':
      color = 'success';
      break;
    case 'PENDING':
    case 'TRANSFER_PENDING':
    case 'PENDING_APPROVAL':
    case 'PENDING_ACK':
    case 'OPEN':
      color = 'warning';
      break;
    case 'CORRUPT':
    case 'OBJECT_REPLACED':
    case 'CHAIN_BROKEN':
    case 'REJECTED':
    case 'DISPUTED':
    case 'FAILED':
      color = 'error';
      break;
    case 'REGISTERED':
    case 'LEGAL_HOLD':
      color = 'primary';
      break;
    default:
      color = 'default';
  }

  return (
    <Chip
      label={label}
      size={size}
      color={color}
      sx={{
        fontSize: '11px',
        fontWeight: 600,
        height: '20px',
        borderRadius: '3px',
      }}
    />
  );
};

