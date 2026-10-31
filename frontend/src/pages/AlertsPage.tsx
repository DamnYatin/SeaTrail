import React, { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
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

interface AlertItem {
  id: string;
  rule: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  case_id?: string;
  evidence_id?: string;
  evidence_number?: string;
  explanation: string;
  status: 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED';
  created_at: string;
  resolution_note?: string;
}

export const AlertsPage: React.FC = () => {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusTab, setStatusTab] = useState<'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED' | 'ALL'>('OPEN');

  // Resolve Dialog
  const [selectedAlert, setSelectedAlert] = useState<AlertItem | null>(null);
  const [resolutionNote, setResolutionNote] = useState('');
  const [resolving, setResolving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchAlerts = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const queryParams: { status?: 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED' } = {};
      if (statusTab !== 'ALL') queryParams.status = statusTab;

      const { data, error } = await apiClient.GET('/api/v1/alerts', {
        params: { query: queryParams },
      });

      if (data && !error) {
        setAlerts((data as unknown as AlertItem[]) || []);
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to fetch alerts');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusTab]);

  const handleAcknowledge = async (alertId: string) => {
    try {
      await apiClient.POST('/api/v1/alerts/{alert_id}/acknowledge', {
        params: { path: { alert_id: alertId } },
      });
      fetchAlerts();
    } catch (e) {
      console.error('Failed to acknowledge alert', e);
    }
  };

  const handleResolve = async () => {
    if (!selectedAlert) return;
    if (resolutionNote.trim().length < 5) {
      setErrorMsg('Resolution note must be at least 5 characters');
      return;
    }

    setResolving(true);
    try {
      const { data, error } = await apiClient.POST('/api/v1/alerts/{alert_id}/resolve', {
        params: { path: { alert_id: selectedAlert.id } },
        body: { resolution_note: resolutionNote.trim() },
      });

      if (error || !data) {
        const errObj = error as { error?: { message?: string } } | undefined;
        throw new Error(errObj?.error?.message || 'Failed to resolve alert');
      }

      setSelectedAlert(null);
      setResolutionNote('');
      fetchAlerts();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Resolution failed');
    } finally {
      setResolving(false);
    }
  };

  const getSeverityColor = (sev: string) => {
    switch (sev) {
      case 'CRITICAL':
        return '#ef5350';
      case 'HIGH':
        return '#f5a623';
      case 'MEDIUM':
        return '#3f7fe0';
      default:
        return '#9e9e9e';
    }
  };

  return (
    <Box sx={{ p: 3, maxWidth: 1600, mx: 'auto' }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 600, mb: 0.5 }}>
          Security Anomaly Alerts
        </Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          Real-time forensic rule violations, hash mismatches, and access pattern warnings
        </Typography>
      </Box>

      {errorMsg && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {errorMsg}
        </Alert>
      )}

      <Card sx={{ border: '1px solid', borderColor: 'divider' }}>
        <Tabs
          value={statusTab}
          onChange={(_, val) => setStatusTab(val)}
          sx={{ borderBottom: '1px solid', borderColor: 'divider', px: 2 }}
        >
          <Tab label="Open Alerts" value="OPEN" />
          <Tab label="Acknowledged" value="ACKNOWLEDGED" />
          <Tab label="Resolved" value="RESOLVED" />
          <Tab label="All Alerts" value="ALL" />
        </Tabs>

        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ backgroundColor: (theme) => (theme.palette.mode === 'dark' ? '#2f2f2f' : '#eef0f3') }}>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Severity</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Anomaly Rule</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Evidence / Target</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Explanation & Context</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Raised At (UTC)</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Status</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px', textAlign: 'right' }}>Action</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={7} sx={{ textAlign: 'center', py: 4 }}>
                    <CircularProgress size={24} />
                  </TableCell>
                </TableRow>
              ) : alerts.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} sx={{ textAlign: 'center', py: 4, color: 'text.secondary' }}>
                    No security alerts found in this view.
                  </TableCell>
                </TableRow>
              ) : (
                alerts.map((al) => (
                  <TableRow key={al.id}>
                    <TableCell>
                      <Chip
                        label={al.severity}
                        size="small"
                        sx={{
                          backgroundColor: getSeverityColor(al.severity),
                          color: '#fff',
                          fontWeight: 700,
                          fontSize: '10px',
                          height: 20,
                        }}
                      />
                    </TableCell>
                    <TableCell sx={{ fontWeight: 600, fontFamily: 'monospace', fontSize: '12px' }}>
                      {al.rule}
                    </TableCell>
                    <TableCell sx={{ color: 'primary.main', fontWeight: 600 }}>
                      {al.evidence_number || al.evidence_id?.slice(0, 8) || '-'}
                    </TableCell>
                    <TableCell sx={{ maxWidth: 360 }}>{al.explanation}</TableCell>
                    <TableCell sx={{ color: 'text.secondary', fontSize: '12px' }}>
                      {al.created_at ? al.created_at.slice(0, 16).replace('T', ' ') : '-'}
                    </TableCell>
                    <TableCell>
                      <StatusChip status={al.status} />
                    </TableCell>
                    <TableCell sx={{ textAlign: 'right' }}>
                      <Box sx={{ display: 'inline-flex', gap: 1 }}>
                        {al.status === 'OPEN' && (
                          <Button
                            size="small"
                            variant="outlined"
                            onClick={() => handleAcknowledge(al.id)}
                            sx={{ fontSize: '11px', py: 0.2 }}
                          >
                            Acknowledge
                          </Button>
                        )}
                        {al.status !== 'RESOLVED' && (
                          <Button
                            size="small"
                            variant="contained"
                            color="success"
                            onClick={() => {
                              setSelectedAlert(al);
                              setResolutionNote('');
                            }}
                            sx={{ fontSize: '11px', py: 0.2 }}
                          >
                            Resolve
                          </Button>
                        )}
                      </Box>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>

      {/* Resolve Dialog */}
      <Dialog open={Boolean(selectedAlert)} onClose={() => setSelectedAlert(null)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 600, fontSize: '16px' }}>
          Resolve Security Alert: {selectedAlert?.rule}
        </DialogTitle>
        <DialogContent sx={{ py: 2 }}>
          <Typography variant="body2" sx={{ mb: 2 }}>
            Record an explanation and operational justification to close this anomaly.
          </Typography>
          <TextField
            fullWidth
            required
            multiline
            rows={3}
            size="small"
            label="Resolution Note (Audited)"
            placeholder="Document remediation steps taken or reason for dismiss..."
            value={resolutionNote}
            onChange={(e) => setResolutionNote(e.target.value)}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setSelectedAlert(null)} disabled={resolving}>
            Cancel
          </Button>
          <Button
            variant="contained"
            color="success"
            onClick={handleResolve}
            disabled={resolving}
            startIcon={resolving ? <CircularProgress size={16} color="inherit" /> : null}
          >
            {resolving ? 'Resolving...' : 'Confirm Resolution'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
