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
  FormControlLabel,
  TextField,
  Typography,
} from '@mui/material';

import { apiClient } from '../api/client';

interface ExportPackageDialogProps {
  open: boolean;
  onClose: () => void;
  onRequested: () => void;
  evidenceId: string;
  evidenceNumber: string;
}

export const ExportPackageDialog: React.FC<ExportPackageDialogProps> = ({
  open,
  onClose,
  onRequested,
  evidenceId,
  evidenceNumber,
}) => {
  const [justification, setJustification] = useState('');
  const [encrypted, setEncrypted] = useState(false);
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (justification.trim().length < 10) {
      setErrorMsg('Please provide a justification (minimum 10 characters)');
      return;
    }
    if (encrypted && password.trim().length < 8) {
      setErrorMsg('Password for encrypted export must be at least 8 characters');
      return;
    }

    setLoading(true);
    setErrorMsg(null);

    try {
      const { data, error } = await apiClient.POST('/api/v1/evidence/{evidence_id}/exports', {
        params: { path: { evidence_id: evidenceId } },
        body: {
          justification: justification.trim(),
          encrypt: encrypted,
          include_bsa_certificate: true,
        },
      });

      if (error || !data) {
        const errObj = error as { error?: { message?: string } } | undefined;
        throw new Error(errObj?.error?.message || 'Failed to request export package');
      }

      onRequested();
      handleClose();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Export request failed');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setJustification('');
    setEncrypted(false);
    setPassword('');
    setErrorMsg(null);
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <Box component="form" onSubmit={handleSubmit}>
        <DialogTitle sx={{ fontWeight: 600, fontSize: '16px', borderBottom: '1px solid', borderColor: 'divider' }}>
          Request Cryptographic Export Package: {evidenceNumber}
        </DialogTitle>

        <DialogContent sx={{ py: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {errorMsg && (
            <Alert severity="error" sx={{ fontSize: '13px' }}>
              {errorMsg}
            </Alert>
          )}

          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            Export packages are court-defensible forensic bundles containing the original bitstream, signed custody report, standalone offline verifier (`verify.py`), SHA256SUMS.txt, and Ed25519 manifest signature.
          </Typography>

          <Alert severity="info" sx={{ fontSize: '12px' }}>
            Export requests require supervisor dual-authorization prior to bundle generation.
          </Alert>

          <TextField
            fullWidth
            required
            multiline
            rows={3}
            size="small"
            label="Operational Justification"
            placeholder="Specify legal proceeding, defense disclosure, court subpoena, or lab analysis..."
            value={justification}
            onChange={(e) => setJustification(e.target.value)}
          />

          <FormControlLabel
            control={
              <Checkbox
                checked={encrypted}
                onChange={(e) => setEncrypted(e.target.checked)}
              />
            }
            label={
              <Typography variant="body2">
                Encrypt ZIP bundle with AES-256 (pyzipper)
              </Typography>
            }
          />

          {encrypted && (
            <TextField
              fullWidth
              size="small"
              required
              type="password"
              label="ZIP Decryption Password (min 8 chars)"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          )}
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
            {loading ? 'Submitting...' : 'Submit Export Request'}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
};
