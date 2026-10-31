import React, { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Typography,
} from '@mui/material';

import { apiClient } from '../api/client';
import { HashText } from './HashText';

interface AcknowledgeTransferDialogProps {
  open: boolean;
  onClose: () => void;
  onAcknowledged: () => void;
  transferId: string;
  evidenceNumber?: string;
  sendHash?: string;
}

export const AcknowledgeTransferDialog: React.FC<AcknowledgeTransferDialogProps> = ({
  open,
  onClose,
  onAcknowledged,
  transferId,
  evidenceNumber,
  sendHash,
}) => {
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleConfirm = async () => {
    setLoading(true);
    setErrorMsg(null);

    try {
      const { data, error } = await apiClient.POST('/api/v1/transfers/{transfer_id}/acknowledge', {
        params: { path: { transfer_id: transferId } },
      });

      if (error || !data) {
        const errObj = error as { error?: { message?: string } } | undefined;
        throw new Error(errObj?.error?.message || 'Acknowledgement failed');
      }

      onAcknowledged();
      onClose();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Receipt acknowledgement failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 600, fontSize: '16px', borderBottom: '1px solid', borderColor: 'divider' }}>
        Acknowledge Custody Receipt
      </DialogTitle>

      <DialogContent sx={{ py: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {errorMsg && (
          <Alert severity="error" sx={{ fontSize: '13px' }}>
            {errorMsg}
          </Alert>
        )}

        <Typography variant="body2">
          You are confirming physical and digital custody transfer of evidence{' '}
          <strong>{evidenceNumber || 'item'}</strong> into your possession.
        </Typography>

        {sendHash && (
          <Box
            sx={{
              p: 2,
              backgroundColor: 'background.default',
              borderRadius: 1,
              border: '1px solid',
              borderColor: 'divider',
            }}
          >
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5 }}>
              Dispatched Cryptographic Hash (SHA-256):
            </Typography>
            <HashText hash={sendHash} />
          </Box>
        )}

        <Alert severity="info" sx={{ fontSize: '12px' }}>
          By acknowledging, you attest that you have received this digital item unaltered, and your confirmation will be cryptographically bound into the append-only audit chain.
        </Alert>
      </DialogContent>

      <DialogActions sx={{ p: 2, borderTop: '1px solid', borderColor: 'divider' }}>
        <Button onClick={onClose} disabled={loading}>
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={handleConfirm}
          disabled={loading}
          startIcon={loading ? <CircularProgress size={16} color="inherit" /> : null}
        >
          {loading ? 'Confirming...' : 'Acknowledge & Accept Custody'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
