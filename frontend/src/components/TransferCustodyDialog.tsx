import React, { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@mui/material';

import { apiClient } from '../api/client';

interface TransferCustodyDialogProps {
  open: boolean;
  onClose: () => void;
  onTransferred: () => void;
  evidenceId: string;
  evidenceNumber: string;
  users: Array<{ id: string; full_name: string; email: string; role: string }>;
}

export const TransferCustodyDialog: React.FC<TransferCustodyDialogProps> = ({
  open,
  onClose,
  onTransferred,
  evidenceId,
  evidenceNumber,
  users,
}) => {
  const [isExternal, setIsExternal] = useState(false);
  const [toUserId, setToUserId] = useState('');
  const [externalParty, setExternalParty] = useState('');
  const [toLocation, setToLocation] = useState('Forensics Lab - Safe 2');
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (isExternal && !externalParty.trim()) {
      setErrorMsg('Please specify the external recipient or agency');
      return;
    }
    if (!isExternal && !toUserId) {
      setErrorMsg('Please select an internal custodian');
      return;
    }
    if (reason.trim().length < 5) {
      setErrorMsg('Please provide a reason (minimum 5 characters)');
      return;
    }

    setLoading(true);
    try {
      const { data, error } = await apiClient.POST('/api/v1/evidence/{evidence_id}/transfers', {
        params: { path: { evidence_id: evidenceId } },
        body: {
          to_user_id: isExternal ? undefined : toUserId,
          to_location: toLocation.trim() || 'Forensics Lab',
          reason: reason.trim(),
          is_external: isExternal,
          external_party: isExternal ? externalParty.trim() : undefined,
        },
      });

      if (error || !data) {
        const errObj = error as { error?: { message?: string } } | undefined;
        throw new Error(errObj?.error?.message || 'Transfer initiation failed');
      }

      onTransferred();
      handleClose();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Custody transfer failed');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setIsExternal(false);
    setToUserId('');
    setExternalParty('');
    setToLocation('Forensics Lab - Safe 2');
    setReason('');
    setErrorMsg(null);
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <Box component="form" onSubmit={handleSubmit}>
        <DialogTitle sx={{ fontWeight: 600, fontSize: '16px', borderBottom: '1px solid', borderColor: 'divider' }}>
          Transfer Custody: {evidenceNumber}
        </DialogTitle>

        <DialogContent sx={{ py: 3, display: 'flex', flexDirection: 'column', gap: 2.5 }}>
          {errorMsg && (
            <Alert severity="error" sx={{ fontSize: '13px' }}>
              {errorMsg}
            </Alert>
          )}

          <FormControlLabel
            control={
              <Checkbox
                checked={isExternal}
                onChange={(e) => setIsExternal(e.target.checked)}
              />
            }
            label={
              <Typography variant="body2" sx={{ fontWeight: 500 }}>
                Transfer to External Party / Agency (Court, Forensic Lab, Prosecutor)
              </Typography>
            }
          />

          {isExternal ? (
            <>
              <TextField
                fullWidth
                size="small"
                required
                label="External Agency / Recipient Name"
                value={externalParty}
                onChange={(e) => setExternalParty(e.target.value)}
                placeholder="e.g. Central Forensic Science Laboratory (CFSL) CBI"
              />
              <Alert severity="warning" sx={{ fontSize: '12px' }}>
                External transfers require two-person dual authorization. An approval request will be submitted to supervisors before dispatch.
              </Alert>
            </>
          ) : (
            <FormControl fullWidth size="small" required>
              <InputLabel>Recipient Custodian</InputLabel>
              <Select
                value={toUserId}
                label="Recipient Custodian"
                onChange={(e) => setToUserId(e.target.value)}
              >
                {users.map((u) => (
                  <MenuItem key={u.id} value={u.id}>
                    {u.full_name} ({u.role}) — {u.email}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}

          <TextField
            fullWidth
            size="small"
            label="Destination Location"
            value={toLocation}
            onChange={(e) => setToLocation(e.target.value)}
            placeholder="e.g. Evidence Room B - Locker 14"
          />

          <TextField
            fullWidth
            size="small"
            required
            multiline
            rows={3}
            label="Reason for Custody Transfer"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Document official operational necessity, chain purpose, court order..."
          />
        </DialogContent>

        <DialogActions sx={{ p: 2, borderTop: '1px solid', borderColor: 'divider' }}>
          <Button onClick={handleClose} disabled={loading}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={loading}
            startIcon={loading ? <CircularProgress size={16} color="inherit" /> : null}
          >
            {loading ? 'Submitting...' : isExternal ? 'Submit for Approval' : 'Dispatch Transfer'}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
};
