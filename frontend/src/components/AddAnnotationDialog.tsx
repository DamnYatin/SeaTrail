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

interface AddAnnotationDialogProps {
  open: boolean;
  onClose: () => void;
  onAdded: () => void;
  evidenceId: string;
  evidenceNumber: string;
}

export const AddAnnotationDialog: React.FC<AddAnnotationDialogProps> = ({
  open,
  onClose,
  onAdded,
  evidenceId,
  evidenceNumber,
}) => {
  const [body, setBody] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!body.trim()) {
      setErrorMsg('Annotation text is required');
      return;
    }

    setLoading(true);
    setErrorMsg(null);

    try {
      const { data, error } = await apiClient.POST('/api/v1/evidence/{evidence_id}/annotations', {
        params: { path: { evidence_id: evidenceId } },
        body: { body: body.trim() },
      });

      if (error || !data) {
        const errObj = error as { error?: { message?: string } } | undefined;
        throw new Error(errObj?.error?.message || 'Failed to record annotation');
      }

      onAdded();
      handleClose();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Annotation submission failed');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setBody('');
    setErrorMsg(null);
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <Box component="form" onSubmit={handleSubmit}>
        <DialogTitle sx={{ fontWeight: 600, fontSize: '16px', borderBottom: '1px solid', borderColor: 'divider' }}>
          Add Defensible Annotation: {evidenceNumber}
        </DialogTitle>

        <DialogContent sx={{ py: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {errorMsg && (
            <Alert severity="error" sx={{ fontSize: '13px' }}>
              {errorMsg}
            </Alert>
          )}

          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            Annotations are append-only and immutable. Each note is hashed and linked into the case timeline.
          </Typography>

          <TextField
            fullWidth
            required
            multiline
            rows={4}
            size="small"
            label="Annotation Content"
            placeholder="Record investigative finding, forensic observation, extraction log details..."
            value={body}
            onChange={(e) => setBody(e.target.value)}
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
            {loading ? 'Saving...' : 'Add Annotation'}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
};

