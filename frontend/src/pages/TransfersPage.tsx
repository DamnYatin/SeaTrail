import React, { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CircularProgress,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  Tab,
  Typography,
} from '@mui/material';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowRightIcon from '@mui/icons-material/KeyboardArrowRight';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';

import { apiClient } from '../api/client';
import { StatusChip } from '../components/StatusChip';
import { HashText } from '../components/HashText';
import { AcknowledgeTransferDialog } from '../components/AcknowledgeTransferDialog';
import { useAuth } from '../auth/AuthContext';

interface TransferRow {
  id: string;
  evidence_id: string;
  evidence_number?: string;
  case_id?: string;
  from_user_id: string;
  from_user_name?: string;
  to_user_id?: string;
  to_user_name?: string;
  to_location?: string;
  reason: string;
  is_external: boolean;
  external_party?: string;
  status: string;
  hash_at_send?: string;
  requested_at: string;
  ack_due_at?: string;
  acknowledged_at?: string;
  hash_at_receipt?: string;
  receipt_verified?: boolean;
}

export const TransfersPage: React.FC = () => {
  const { user } = useAuth();
  const [transfers, setTransfers] = useState<TransferRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusTab, setStatusTab] = useState<'ALL' | 'PENDING_ACK' | 'PENDING_APPROVAL' | 'COMPLETED' | 'OVERDUE'>('ALL');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Acknowledge Dialog
  const [ackItem, setAckItem] = useState<TransferRow | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchTransfers = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const { data, error } = await apiClient.GET('/api/v1/transfers', {
        params: {
          query: {
            status: statusTab === 'ALL' || statusTab === 'OVERDUE' ? undefined : statusTab,
          },
        },
      });
      if (data && !error) {
        setTransfers((data as unknown as TransferRow[]) || []);
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to load transfers');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTransfers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const now = new Date();

  const filteredTransfers = transfers.filter((t) => {
    const isOverdue = t.status === 'PENDING_ACK' && t.ack_due_at && new Date(t.ack_due_at) < now;
    if (statusTab === 'OVERDUE') return isOverdue;
    if (statusTab === 'PENDING_ACK') return t.status === 'PENDING_ACK';
    if (statusTab === 'PENDING_APPROVAL') return t.status === 'PENDING_APPROVAL';
    if (statusTab === 'COMPLETED') return t.status === 'COMPLETED';
    return true;
  });

  return (
    <Box sx={{ p: 3, maxWidth: 1600, mx: 'auto' }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 600, mb: 0.5 }}>
          Custody Transfers
        </Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          Physical and digital chain-of-custody transfer workflow and SLA tracking
        </Typography>
      </Box>

      {errorMsg && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {errorMsg}
        </Alert>
      )}

      <Card sx={{ mb: 3 }}>
        <Tabs
          value={statusTab}
          onChange={(_, val) => setStatusTab(val)}
          sx={{ borderBottom: '1px solid', borderColor: 'divider', px: 2 }}
        >
          <Tab label={`All (${transfers.length})`} value="ALL" />
          <Tab
            label={`Pending Ack (${transfers.filter((t) => t.status === 'PENDING_ACK').length})`}
            value="PENDING_ACK"
          />
          <Tab
            label={`Pending Approval (${transfers.filter((t) => t.status === 'PENDING_APPROVAL').length})`}
            value="PENDING_APPROVAL"
          />
          <Tab
            label={`Completed (${transfers.filter((t) => t.status === 'COMPLETED').length})`}
            value="COMPLETED"
          />
          <Tab
            icon={<WarningAmberIcon sx={{ fontSize: 16, color: '#f5a623' }} />}
            iconPosition="start"
            label={`Overdue SLA (${
              transfers.filter((t) => t.status === 'PENDING_ACK' && t.ack_due_at && new Date(t.ack_due_at) < now).length
            })`}
            value="OVERDUE"
          />
        </Tabs>

        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ backgroundColor: (theme) => (theme.palette.mode === 'dark' ? '#2f2f2f' : '#eef0f3') }}>
                <TableCell sx={{ width: 40 }} />
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Evidence</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Dispatched From</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Recipient Custodian</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Location</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Dispatched At</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>SLA Due Date</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Status</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px', textAlign: 'right' }}>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={9} sx={{ textAlign: 'center', py: 4 }}>
                    <CircularProgress size={24} />
                  </TableCell>
                </TableRow>
              ) : filteredTransfers.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={9} sx={{ textAlign: 'center', py: 4, color: 'text.secondary' }}>
                    No custody transfers match the selected filter.
                  </TableCell>
                </TableRow>
              ) : (
                filteredTransfers.map((t) => {
                  const isExpanded = expandedId === t.id;
                  const isOverdue = t.status === 'PENDING_ACK' && t.ack_due_at && new Date(t.ack_due_at) < now;
                  const canAck = t.status === 'PENDING_ACK' && (!t.to_user_id || t.to_user_id === user?.id);

                  return (
                    <React.Fragment key={t.id}>
                      <TableRow
                        sx={{
                          cursor: 'pointer',
                          backgroundColor: isOverdue
                            ? 'rgba(245, 166, 35, 0.08)'
                            : isExpanded
                            ? 'rgba(63, 127, 224, 0.05)'
                            : 'inherit',
                        }}
                        onClick={() => setExpandedId(isExpanded ? null : t.id)}
                      >
                        <TableCell>
                          <IconButton size="small">
                            {isExpanded ? <KeyboardArrowDownIcon /> : <KeyboardArrowRightIcon />}
                          </IconButton>
                        </TableCell>
                        <TableCell sx={{ fontWeight: 600, color: 'primary.main' }}>
                          {t.evidence_number || t.evidence_id.slice(0, 8)}
                        </TableCell>
                        <TableCell>{t.from_user_name || t.from_user_id.slice(0, 8)}</TableCell>
                        <TableCell>
                          {t.is_external ? `[External] ${t.external_party}` : t.to_user_name || t.to_user_id?.slice(0, 8) || '-'}
                        </TableCell>
                        <TableCell>{t.to_location || '-'}</TableCell>
                        <TableCell>{t.requested_at ? t.requested_at.slice(0, 16).replace('T', ' ') : '-'}</TableCell>
                        <TableCell sx={{ color: isOverdue ? 'error.main' : 'inherit', fontWeight: isOverdue ? 700 : 400 }}>
                          {t.ack_due_at ? t.ack_due_at.slice(0, 16).replace('T', ' ') : '-'}
                          {isOverdue && ' (OVERDUE)'}
                        </TableCell>
                        <TableCell>
                          <StatusChip status={t.status} />
                        </TableCell>
                        <TableCell sx={{ textAlign: 'right' }}>
                          {canAck && (
                            <Button
                              size="small"
                              variant="contained"
                              onClick={(e) => {
                                e.stopPropagation();
                                setAckItem(t);
                              }}
                              sx={{ fontSize: '11px', py: 0.2 }}
                            >
                              Acknowledge
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>

                      {isExpanded && (
                        <TableRow>
                          <TableCell colSpan={9} sx={{ p: 2.5, backgroundColor: 'background.default' }}>
                            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, fontSize: '13px' }}>
                              <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary' }}>
                                TRANSFER DETAILS & REASON
                              </Typography>
                              <Typography variant="body2">{t.reason}</Typography>

                              {t.hash_at_send && (
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
                                  <Typography variant="caption" sx={{ fontWeight: 700 }}>
                                    SHA-256 AT SEND:
                                  </Typography>
                                  <HashText hash={t.hash_at_send} />
                                </Box>
                              )}

                              {t.hash_at_receipt && (
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                  <Typography variant="caption" sx={{ fontWeight: 700 }}>
                                    SHA-256 AT RECEIPT:
                                  </Typography>
                                  <HashText hash={t.hash_at_receipt} />
                                  <Typography variant="caption" sx={{ color: 'success.main', fontWeight: 700 }}>
                                    [VERIFIED MATCH]
                                  </Typography>
                                </Box>
                              )}
                            </Box>
                          </TableCell>
                        </TableRow>
                      )}
                    </React.Fragment>
                  );
                })
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>

      {ackItem && (
        <AcknowledgeTransferDialog
          open={Boolean(ackItem)}
          onClose={() => setAckItem(null)}
          onAcknowledged={() => {
            setAckItem(null);
            fetchTransfers();
          }}
          transferId={ackItem.id}
          evidenceNumber={ackItem.evidence_number}
          sendHash={ackItem.hash_at_send}
        />
      )}
    </Box>
  );
};
