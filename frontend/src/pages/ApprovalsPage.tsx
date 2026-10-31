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
  Tooltip,
  Typography,
} from '@mui/material';

import { apiClient } from '../api/client';
import { StatusChip } from '../components/StatusChip';
import { useAuth } from '../auth/AuthContext';

interface ApprovalRow {
  id: string;
  kind: 'EXTERNAL_TRANSFER' | 'EXPORT_PACKAGE' | 'LEGAL_HOLD_RELEASE' | 'DISPOSAL';
  case_id?: string;
  evidence_id?: string;
  evidence_number?: string;
  requested_by: string;
  requester_name?: string;
  justification: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'CANCELLED' | 'EXECUTED' | 'EXPIRED';
  decided_by?: string;
  decider_name?: string;
  decided_at?: string;
  decision_note?: string;
  expires_at?: string;
  executed_at?: string;
  created_at?: string;
}

export const ApprovalsPage: React.FC = () => {
  const { user } = useAuth();
  const [approvals, setApprovals] = useState<ApprovalRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'FOR_DECISION' | 'MY_REQUESTS'>('FOR_DECISION');

  // Decision Modal
  const [selectedApproval, setSelectedApproval] = useState<ApprovalRow | null>(null);
  const [decisionType, setDecisionType] = useState<'APPROVED' | 'REJECTED'>('APPROVED');
  const [decisionNote, setDecisionNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchApprovals = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const queryParams: { status?: string; mine?: boolean } = {};
      if (tab === 'MY_REQUESTS') queryParams.mine = true;

      const { data, error } = await apiClient.GET('/api/v1/approvals', {
        params: { query: queryParams },
      });

      if (data && !error) {
        setApprovals((data as unknown as ApprovalRow[]) || []);
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to fetch approval queue');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApprovals();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const handleOpenDecision = (item: ApprovalRow, type: 'APPROVED' | 'REJECTED') => {
    setSelectedApproval(item);
    setDecisionType(type);
    setDecisionNote('');
  };

  const handleCloseDecision = () => {
    setSelectedApproval(null);
    setDecisionNote('');
  };

  const handleSubmitDecision = async () => {
    if (!selectedApproval) return;
    if (decisionNote.trim().length < 5) {
      setErrorMsg('Decision note must be at least 5 characters');
      return;
    }

    setSubmitting(true);
    setErrorMsg(null);

    try {
      let res;
      if (decisionType === 'APPROVED') {
        res = await apiClient.POST('/api/v1/approvals/{approval_id}/approve', {
          params: { path: { approval_id: selectedApproval.id } },
          body: { decision_note: decisionNote.trim() },
        });
      } else {
        res = await apiClient.POST('/api/v1/approvals/{approval_id}/reject', {
          params: { path: { approval_id: selectedApproval.id } },
          body: { decision_note: decisionNote.trim() },
        });
      }

      if (res.error || !res.data) {
        const errObj = res.error as { error?: { message?: string } } | undefined;
        throw new Error(errObj?.error?.message || 'Failed to submit decision');
      }

      handleCloseDecision();
      fetchApprovals();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Decision execution failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box sx={{ p: 3, maxWidth: 1600, mx: 'auto' }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 600, mb: 0.5 }}>
          Dual Authorization Queue
        </Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          Two-person authorization for external transfers, forensic export packages, legal hold releases, and disposal
        </Typography>
      </Box>

      {errorMsg && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {errorMsg}
        </Alert>
      )}

      <Card sx={{ mb: 3 }}>
        <Tabs
          value={tab}
          onChange={(_, val) => setTab(val)}
          sx={{ borderBottom: '1px solid', borderColor: 'divider', px: 2 }}
        >
          <Tab label="For My Decision" value="FOR_DECISION" />
          <Tab label="My Requests" value="MY_REQUESTS" />
        </Tabs>

        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ backgroundColor: (theme) => (theme.palette.mode === 'dark' ? '#2f2f2f' : '#eef0f3') }}>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Request Type</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Evidence / Target</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Requester</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Operational Justification</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Expires At</TableCell>
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
              ) : approvals.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} sx={{ textAlign: 'center', py: 4, color: 'text.secondary' }}>
                    No approvals currently found in this queue.
                  </TableCell>
                </TableRow>
              ) : (
                approvals.map((item) => {
                  const isSelfRequest = item.requested_by === user?.id;
                  const canDecide = item.status === 'PENDING' && !isSelfRequest;

                  return (
                    <TableRow key={item.id}>
                      <TableCell>
                        <StatusChip status={item.kind} />
                      </TableCell>
                      <TableCell sx={{ fontWeight: 600, color: 'primary.main' }}>
                        {item.evidence_number || item.evidence_id?.slice(0, 8) || '-'}
                      </TableCell>
                      <TableCell>{item.requester_name || item.requested_by.slice(0, 8)}</TableCell>
                      <TableCell sx={{ maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {item.justification}
                      </TableCell>
                      <TableCell>{item.expires_at ? item.expires_at.slice(0, 16).replace('T', ' ') : '-'}</TableCell>
                      <TableCell>
                        <StatusChip status={item.status} />
                      </TableCell>
                      <TableCell sx={{ textAlign: 'right' }}>
                        {item.status === 'PENDING' ? (
                          isSelfRequest ? (
                            <Tooltip title="Two-person rule: You cannot approve your own request">
                              <span>
                                <Button size="small" disabled sx={{ fontSize: '11px' }}>
                                  Self Request
                                </Button>
                              </span>
                            </Tooltip>
                          ) : (
                            <Box sx={{ display: 'inline-flex', gap: 1 }}>
                              <Button
                                size="small"
                                variant="contained"
                                color="success"
                                disabled={!canDecide}
                                onClick={() => handleOpenDecision(item, 'APPROVED')}
                                sx={{ fontSize: '11px', py: 0.2 }}
                              >
                                Approve
                              </Button>
                              <Button
                                size="small"
                                variant="outlined"
                                color="error"
                                disabled={!canDecide}
                                onClick={() => handleOpenDecision(item, 'REJECTED')}
                                sx={{ fontSize: '11px', py: 0.2 }}
                              >
                                Reject
                              </Button>
                            </Box>
                          )
                        ) : (
                          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                            Decided by {item.decider_name || item.decided_by?.slice(0, 8) || 'System'}
                          </Typography>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>

      {/* Decision Dialog */}
      <Dialog open={Boolean(selectedApproval)} onClose={handleCloseDecision} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 600, fontSize: '16px' }}>
          {decisionType === 'APPROVED' ? 'Approve Sensitive Action' : 'Reject Request'}
        </DialogTitle>
        <DialogContent sx={{ py: 2 }}>
          <Typography variant="body2" sx={{ mb: 2 }}>
            You are recording a formal decision on approval request{' '}
            <strong>{selectedApproval?.id.slice(0, 8)}</strong> ({selectedApproval?.kind}).
          </Typography>
          <TextField
            fullWidth
            required
            multiline
            rows={3}
            size="small"
            label="Decision Note (Audit Justification)"
            placeholder="Document official reason, conditions, court verification..."
            value={decisionNote}
            onChange={(e) => setDecisionNote(e.target.value)}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={handleCloseDecision} disabled={submitting}>
            Cancel
          </Button>
          <Button
            variant="contained"
            color={decisionType === 'APPROVED' ? 'success' : 'error'}
            onClick={handleSubmitDecision}
            disabled={submitting}
            startIcon={submitting ? <CircularProgress size={16} color="inherit" /> : null}
          >
            {submitting ? 'Recording...' : `Confirm ${decisionType}`}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
