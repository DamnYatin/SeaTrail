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
  TextField,
  Typography,
} from '@mui/material';

import { apiClient } from '../api/client';

interface LegalHoldDialogProps {
  open: boolean;
  onClose: () => void;
  onCompleted: () => void;
  evidenceId: string;
  evidenceNumber: string;
  isHeld: boolean;
}

export const LegalHoldDialog: React.FC<LegalHoldDialogProps> = ({
  open,
  onClose,
  onCompleted,
  evidenceId,
  evidenceNumber,
  isHeld,
}) => {
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (reason.trim().length < 5) {
      setErrorMsg('Please provide a reason / justification (minimum 5 characters)');
      return;
    }

    setLoading(true);
    setErrorMsg(null);

    try {
      if (!isHeld) {
        // Place Hold
        const { data, error } = await apiClient.POST('/api/v1/evidence/{evidence_id}/legal-hold', {
          params: { path: { evidence_id: evidenceId } },
          body: { reason: reason.trim() },
        });
        if (error || !data) {
          const errObj = error as { error?: { message?: string } } | undefined;
          throw new Error(errObj?.error?.message || 'Failed to place legal hold');
        }
      } else {
        // Request Release (Dual Authorization)
        const { data, error } = await apiClient.POST('/api/v1/legal-hold/release-request', {
          params: { query: { target_type: 'EVIDENCE', target_id: evidenceId } },
          body: {
            justification: reason.trim(),
          },
        });
        if (error || !data) {
          const errObj = error as { error?: { message?: string } } | undefined;
          throw new Error(errObj?.error?.message || 'Failed to submit legal hold release request');
        }
      }

      onCompleted();
      handleClose();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Legal hold operation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setReason('');
    setErrorMsg(null);
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <Box component="form" onSubmit={handleSubmit}>
        <DialogTitle sx={{ fontWeight: 600, fontSize: '16px', borderBottom: '1px solid', borderColor: 'divider' }}>
          {isHeld ? `Request Release of Legal Hold: ${evidenceNumber}` : `Place Statutory Legal Hold: ${evidenceNumber}`}
        </DialogTitle>

        <DialogContent sx={{ py: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {errorMsg && (
            <Alert severity="error" sx={{ fontSize: '13px' }}>
              {errorMsg}
            </Alert>
          )}

          {isHeld ? (
            <Alert severity="warning" sx={{ fontSize: '12px' }}>
              Releasing a legal hold is a sensitive operation governed by dual-authorization. Submitting this request creates an approval request requiring another authorized supervisor to sign off.
            </Alert>
          ) : (
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              Placing a legal hold locks this evidence item indefinitely, preventing automatic retention purge or disposal until officially released.
            </Typography>
          )}

          <TextField
            fullWidth
            required
            multiline
            rows={3}
            size="small"
            label={isHeld ? 'Release Justification & Court Order' : 'Statutory Preservation Basis / Case Order'}
            placeholder={isHeld ? 'Specify why the preservation order has lapsed or court order number...' : 'Cite case order, subpoena, or statutory preservation requirement...'}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </DialogContent>

        <DialogActions sx={{ p: 2, borderTop: '1px solid', borderColor: 'divider' }}>
          <Button onClick={handleClose} disabled={loading}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="contained"
            color={isHeld ? 'warning' : 'primary'}
            disabled={loading}
            startIcon={loading ? <CircularProgress size={16} color="inherit" /> : null}
          >
            {loading ? 'Submitting...' : isHeld ? 'Submit Release Request' : 'Place Legal Hold'}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
};
