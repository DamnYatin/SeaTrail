import React, { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Typography,
} from '@mui/material';

import { apiClient } from '../api/client';
import { StatusChip } from '../components/StatusChip';

interface RetentionPolicy {
  id: string;
  name: string;
  retain_days: number;
  description?: string;
}

interface DueItem {
  id: string;
  evidence_number: string;
  item_name: string;
  retention_until: string;
  days_overdue: number;
  legal_hold: boolean;
  sha256: string;
}

export const RetentionPage: React.FC = () => {
  const [tab, setTab] = useState<'DUE' | 'POLICIES'>('DUE');
  const [dueItems, setDueItems] = useState<DueItem[]>([]);
  const [policies, setPolicies] = useState<RetentionPolicy[]>([]);
  const [loading, setLoading] = useState(true);

  // Disposal Request Dialog
  const [selectedDisposalItem, setSelectedDisposalItem] = useState<DueItem | null>(null);
  const [disposalReason, setDisposalReason] = useState('');
  const [requestingDisposal, setRequestingDisposal] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setMsg(null);
    try {
      const [dueRes, polRes] = await Promise.all([
        apiClient.GET('/api/v1/retention/due').catch(() => ({ data: [] })),
        apiClient.GET('/api/v1/retention/policies').catch(() => ({ data: [] })),
      ]);

      if (dueRes.data && Array.isArray(dueRes.data)) {
        setDueItems(dueRes.data as unknown as DueItem[]);
      }
      if (polRes.data && Array.isArray(polRes.data)) {
        setPolicies(polRes.data as unknown as RetentionPolicy[]);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleRequestDisposal = async () => {
    if (!selectedDisposalItem) return;
    if (disposalReason.trim().length < 10) {
      setMsg('Please provide a detailed justification (minimum 10 characters)');
      return;
    }

    setRequestingDisposal(true);
    try {
      const { data, error } = await apiClient.POST('/api/v1/evidence/{evidence_id}/disposal', {
        params: { path: { evidence_id: selectedDisposalItem.id } },
        body: { justification: disposalReason.trim() },
      });

      if (error || !data) {
        const errObj = error as { error?: { message?: string } } | undefined;
        throw new Error(errObj?.error?.message || 'Failed to submit disposal request');
      }

      setMsg('Disposal approval request submitted to supervisors.');
      setSelectedDisposalItem(null);
      setDisposalReason('');
      fetchData();
    } catch (err: unknown) {
      setMsg(err instanceof Error ? err.message : 'Disposal request failed');
    } finally {
      setRequestingDisposal(false);
    }
  };

  return (
    <Box sx={{ p: 3, maxWidth: 1600, mx: 'auto' }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 600, mb: 0.5 }}>
          Retention Lifecycle & Authorized Disposal
        </Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          Statutory retention schedule tracking, expired artifact queues, and defensible cryptographic disposal tombstones
        </Typography>
      </Box>

      {msg && (
        <Alert severity="info" sx={{ mb: 2 }}>
          {msg}
        </Alert>
      )}

      <Card sx={{ border: '1px solid', borderColor: 'divider' }}>
        <Tabs
          value={tab}
          onChange={(_, val) => setTab(val)}
          sx={{ borderBottom: '1px solid', borderColor: 'divider', px: 2 }}
        >
          <Tab label={`Retention Due / Expired Items (${dueItems.length})`} value="DUE" />
          <Tab label={`Retention Policies (${policies.length})`} value="POLICIES" />
        </Tabs>

        {tab === 'DUE' ? (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ backgroundColor: (theme) => (theme.palette.mode === 'dark' ? '#2f2f2f' : '#eef0f3') }}>
                  <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Evidence</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Item Title</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Retention Expiry</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Overdue Days</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Legal Hold</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '12px', textAlign: 'right' }}>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={6} sx={{ textAlign: 'center', py: 4 }}>
                      <CircularProgress size={24} />
                    </TableCell>
                  </TableRow>
                ) : dueItems.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} sx={{ textAlign: 'center', py: 4, color: 'text.secondary' }}>
                      No items currently past statutory retention.
                    </TableCell>
                  </TableRow>
                ) : (
                  dueItems.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell sx={{ fontWeight: 600, color: 'primary.main' }}>
                        {item.evidence_number}
                      </TableCell>
                      <TableCell>{item.item_name}</TableCell>
                      <TableCell sx={{ color: 'error.main', fontWeight: 600 }}>
                        {item.retention_until}
                      </TableCell>
                      <TableCell sx={{ fontWeight: 700, color: 'error.main' }}>
                        {item.days_overdue} days
                      </TableCell>
                      <TableCell>
                        {item.legal_hold ? (
                          <StatusChip status="LEGAL_HOLD" />
                        ) : (
                          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                            None (Eligible)
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell sx={{ textAlign: 'right' }}>
                        <Button
                          size="small"
                          variant="outlined"
                          color="error"
                          disabled={item.legal_hold}
                          onClick={() => {
                            setSelectedDisposalItem(item);
                            setDisposalReason('');
                          }}
                          sx={{ fontSize: '11px', py: 0.2 }}
                        >
                          Request Disposal
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ backgroundColor: (theme) => (theme.palette.mode === 'dark' ? '#2f2f2f' : '#eef0f3') }}>
                  <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Policy Name</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Retention Period (Days)</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Description</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {policies.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell sx={{ fontWeight: 600 }}>{p.name}</TableCell>
                    <TableCell>{p.retain_days} days ({(p.retain_days / 365).toFixed(1)} years)</TableCell>
                    <TableCell>{p.description || '-'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Card>

      {/* Disposal Dialog */}
      <Dialog open={Boolean(selectedDisposalItem)} onClose={() => setSelectedDisposalItem(null)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 600, fontSize: '16px' }}>
          Request Cryptographic Disposal: {selectedDisposalItem?.evidence_number}
        </DialogTitle>
        <DialogContent sx={{ py: 2 }}>
          <Typography variant="body2" sx={{ mb: 2 }}>
            Disposal permanently deletes object storage versions while preserving the database row and complete audit trail with an immutable cryptographic tombstone.
          </Typography>
          <Alert severity="warning" sx={{ mb: 2, fontSize: '12px' }}>
            Disposal requires dual authorization and cannot be undone.
          </Alert>
          <TextField
            fullWidth
            required
            multiline
            rows={3}
            size="small"
            label="Disposal Justification"
            placeholder="Cite statutory retention expiration, court authorization, prosecutor release..."
            value={disposalReason}
            onChange={(e) => setDisposalReason(e.target.value)}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setSelectedDisposalItem(null)} disabled={requestingDisposal}>
            Cancel
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleRequestDisposal}
            disabled={requestingDisposal}
            startIcon={requestingDisposal ? <CircularProgress size={16} color="inherit" /> : null}
          >
            {requestingDisposal ? 'Submitting...' : 'Submit Disposal Request'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
