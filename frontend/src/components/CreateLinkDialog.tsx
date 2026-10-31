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
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@mui/material';

import { apiClient } from '../api/client';

interface CreateLinkDialogProps {
  open: boolean;
  onClose: () => void;
  onLinked: () => void;
  evidenceId: string;
  evidenceNumber: string;
  caseId: string;
}

export const CreateLinkDialog: React.FC<CreateLinkDialogProps> = ({
  open,
  onClose,
  onLinked,
  evidenceId,
  evidenceNumber,
}) => {
  const [targetType, setTargetType] = useState<'PERSON' | 'EVENT' | 'NOTE' | 'EVIDENCE'>('PERSON');
  const [targetId, setTargetId] = useState('');
  const [relation, setRelation] = useState('Associated artifact');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetId.trim()) {
      setErrorMsg('Target identifier or UUID is required');
      return;
    }
    if (!relation.trim()) {
      setErrorMsg('Relation description is required');
      return;
    }

    setLoading(true);
    setErrorMsg(null);

    try {
      const { data, error } = await apiClient.POST('/api/v1/evidence/{evidence_id}/links', {
        params: { path: { evidence_id: evidenceId } },
        body: {
          target_type: targetType,
          target_id: targetId.trim(),
          relation: relation.trim(),
        },
      });

      if (error || !data) {
        const errObj = error as { error?: { message?: string } } | undefined;
        throw new Error(errObj?.error?.message || 'Failed to link entity');
      }

      onLinked();
      handleClose();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Entity link failed');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setTargetId('');
    setRelation('Associated artifact');
    setErrorMsg(null);
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <Box component="form" onSubmit={handleSubmit}>
        <DialogTitle sx={{ fontWeight: 600, fontSize: '16px', borderBottom: '1px solid', borderColor: 'divider' }}>
          Link Evidence: {evidenceNumber}
        </DialogTitle>

        <DialogContent sx={{ py: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {errorMsg && (
            <Alert severity="error" sx={{ fontSize: '13px' }}>
              {errorMsg}
            </Alert>
          )}

          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            Link this digital item to persons, timeline events, notes, or parent devices without altering the underlying evidence record.
          </Typography>

          <FormControl fullWidth size="small">
            <InputLabel>Link Target Type</InputLabel>
            <Select
              value={targetType}
              label="Link Target Type"
              onChange={(e) => setTargetType(e.target.value as 'PERSON' | 'EVENT' | 'NOTE' | 'EVIDENCE')}
            >
              <MenuItem value="PERSON">Person of Interest / Suspect / Witness</MenuItem>
              <MenuItem value="EVENT">Timeline Incident Event</MenuItem>
              <MenuItem value="NOTE">Investigative Note</MenuItem>
              <MenuItem value="EVIDENCE">Related Evidence Item</MenuItem>
            </Select>
          </FormControl>

          <TextField
            fullWidth
            required
            size="small"
            label="Target Entity ID"
            placeholder="UUID of target person, event, or evidence item"
            value={targetId}
            onChange={(e) => setTargetId(e.target.value)}
          />

          <TextField
            fullWidth
            required
            size="small"
            label="Relationship / Role"
            placeholder="e.g. Found in suspect possession, Extracted from, Victim communications"
            value={relation}
            onChange={(e) => setRelation(e.target.value)}
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
            {loading ? 'Creating...' : 'Create Link'}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
};

