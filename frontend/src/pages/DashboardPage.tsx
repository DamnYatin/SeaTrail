import React, { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import ShieldIcon from '@mui/icons-material/Shield';
import GppGoodIcon from '@mui/icons-material/GppGood';
import GppBadIcon from '@mui/icons-material/GppBad';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import FolderIcon from '@mui/icons-material/Folder';
import FingerprintIcon from '@mui/icons-material/Fingerprint';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';

import { apiClient } from '../api/client';
import { StatusChip } from '../components/StatusChip';

interface ChainVerifyResult {
  ok: boolean;
  checked: number;
  head_seq: number;
  head_hash: string;
  first_broken_seq?: number | null;
  reason?: string | null;
}

interface DashboardTransfer {
  id: string;
  evidence_id: string;
  evidence_number?: string | null;
  from_user_name?: string | null;
  from_user_id: string;
  ack_due_at?: string | null;
  status: string;
}

interface DashboardAlert {
  id: string;
  rule: string;
  severity: string;
  status: string;
}

interface DashboardAuditItem {
  seq: number;
  action: string;
  actor_name?: string | null;
  actor_role?: string | null;
  ts: string;
}

export const DashboardPage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [verifyingChain, setVerifyingChain] = useState(false);
  const [chainResult, setChainResult] = useState<ChainVerifyResult | null>(null);

  // Stats
  const [casesCount, setCasesCount] = useState(0);
  const [evidenceCount, setEvidenceCount] = useState(0);
  const [pendingTransfers, setPendingTransfers] = useState<DashboardTransfer[]>([]);
  const [openAlerts, setOpenAlerts] = useState<DashboardAlert[]>([]);
  const [recentAudit, setRecentAudit] = useState<DashboardAuditItem[]>([]);

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      // 1. Cases count
      try {
        const { data: casesData } = await apiClient.GET('/api/v1/cases');
        if (casesData && Array.isArray(casesData)) {
          setCasesCount(casesData.length);
        }
      } catch {
        // Ignored if forbidden
      }

      // 2. Evidence count
      try {
        const { data: evidenceData } = await apiClient.GET('/api/v1/evidence', {
          params: { query: { page_size: 1 } },
        });
        if (evidenceData && 'total' in evidenceData) {
          setEvidenceCount(evidenceData.total ?? 0);
        }
      } catch {
        // Ignored
      }

      // 3. Transfers pending for user
      try {
        const { data: transfersData } = await apiClient.GET('/api/v1/transfers', {
          params: { query: { status: 'PENDING_ACK' } },
        });
        if (transfersData && Array.isArray(transfersData)) {
          setPendingTransfers(transfersData as unknown as DashboardTransfer[]);
        }
      } catch {
        // Ignored
      }

      // 4. Open alerts
      try {
        const { data: alertsData } = await apiClient.GET('/api/v1/alerts', {
          params: { query: { status: 'OPEN' } },
        });
        if (alertsData && Array.isArray(alertsData)) {
          setOpenAlerts(alertsData as unknown as DashboardAlert[]);
        }
      } catch {
        // Ignored
      }

      // 5. Recent audit activity
      try {
        const { data: auditData } = await apiClient.GET('/api/v1/audit', {
          params: { query: { page_size: 10 } },
        });
        if (auditData && 'items' in auditData) {
          setRecentAudit(auditData.items as unknown as DashboardAuditItem[]);
        }
      } catch {
        // Ignored
      }
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyChain = async () => {
    setVerifyingChain(true);
    try {
      const { data, error } = await apiClient.POST('/api/v1/audit/verify');
      if (data && !error) {
        setChainResult(data as ChainVerifyResult);
      }
    } catch (e) {
      console.error('Chain verification failed', e);
    } finally {
      setVerifyingChain(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    handleVerifyChain();
  }, []);

  return (
    <Box sx={{ p: 3, maxWidth: 1600, mx: 'auto' }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 600, mb: 0.5 }}>
          System Overview & Oversight
        </Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          Real-time cryptographic audit status, custody queues, and active investigation metrics
        </Typography>
      </Box>

      {/* Top Stat Cards */}
      <Grid container spacing={2.5} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ border: '1px solid', borderColor: 'divider' }}>
            <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Box sx={{ p: 1.5, borderRadius: 1, backgroundColor: 'rgba(92, 184, 103, 0.1)', color: '#5cb867' }}>
                <FolderIcon sx={{ fontSize: 28 }} />
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600 }}>
                  ACTIVE CASES
                </Typography>
                <Typography variant="h5" sx={{ fontWeight: 700 }}>
                  {loading ? '...' : casesCount}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ border: '1px solid', borderColor: 'divider' }}>
            <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Box sx={{ p: 1.5, borderRadius: 1, backgroundColor: 'rgba(63, 127, 224, 0.1)', color: 'primary.main' }}>
                <FingerprintIcon sx={{ fontSize: 28 }} />
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600 }}>
                  EVIDENCE REGISTERED
                </Typography>
                <Typography variant="h5" sx={{ fontWeight: 700 }}>
                  {loading ? '...' : evidenceCount}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ border: '1px solid', borderColor: 'divider' }}>
            <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Box sx={{ p: 1.5, borderRadius: 1, backgroundColor: 'rgba(245, 166, 35, 0.1)', color: '#f5a623' }}>
                <SwapHorizIcon sx={{ fontSize: 28 }} />
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600 }}>
                  PENDING CUSTODY TRANSFERS
                </Typography>
                <Typography variant="h5" sx={{ fontWeight: 700 }}>
                  {loading ? '...' : pendingTransfers.length}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ border: '1px solid', borderColor: 'divider' }}>
            <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Box sx={{ p: 1.5, borderRadius: 1, backgroundColor: 'rgba(239, 83, 80, 0.1)', color: 'error.main' }}>
                <WarningAmberIcon sx={{ fontSize: 28 }} />
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600 }}>
                  SECURITY ANOMALIES
                </Typography>
                <Typography variant="h5" sx={{ fontWeight: 700 }}>
                  {loading ? '...' : openAlerts.length}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Cryptographic Chain Status Card */}
      <Card sx={{ mb: 3, border: '1px solid', borderColor: 'divider' }}>
        <Box
          sx={{
            p: 2.5,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 2,
            backgroundColor: (theme) =>
              chainResult?.ok === false
                ? 'rgba(239, 83, 80, 0.1)'
                : theme.palette.mode === 'dark'
                ? '#252525'
                : '#f8fafc',
            borderBottom: '1px solid',
            borderColor: 'divider',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {chainResult?.ok === false ? (
              <GppBadIcon sx={{ fontSize: 38, color: 'error.main' }} />
            ) : (
              <GppGoodIcon sx={{ fontSize: 38, color: 'success.main' }} />
            )}
            <Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                  {chainResult?.ok === false
                    ? 'AUDIT CHAIN COMPROMISED / BROKEN'
                    : 'AUDIT CHAIN CRYPTOGRAPHICALLY INTACT'}
                </Typography>
                <StatusChip status={chainResult?.ok === false ? 'CORRUPT' : 'VERIFIED'} />
              </Box>
              <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.3 }}>
                {chainResult?.ok === false
                  ? `Integrity breach detected at sequence #${chainResult.first_broken_seq}: ${chainResult.reason}`
                  : `All ${chainResult?.checked ?? 'entries'} transactions strictly hash-chained and bound with Ed25519 checkpoints`}
              </Typography>
            </Box>
          </Box>

          <Button
            variant="contained"
            color={chainResult?.ok === false ? 'error' : 'primary'}
            onClick={handleVerifyChain}
            disabled={verifyingChain}
            startIcon={verifyingChain ? <CircularProgress size={16} color="inherit" /> : <ShieldIcon />}
            sx={{ px: 2.5 }}
          >
            {verifyingChain ? 'Verifying...' : 'Verify Chain Now'}
          </Button>
        </Box>
      </Card>

      {/* Grid: Pending Acks & Recent Activity */}
      <Grid container spacing={3}>
        {/* Left: Pending Transfers for me */}
        <Grid item xs={12} md={6}>
          <Card sx={{ border: '1px solid', borderColor: 'divider', height: '100%' }}>
            <Box sx={{ p: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                MY PENDING CUSTODY ACKNOWLEDGEMENTS ({pendingTransfers.length})
              </Typography>
            </Box>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow sx={{ backgroundColor: (theme) => (theme.palette.mode === 'dark' ? '#2f2f2f' : '#eef0f3') }}>
                    <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Evidence</TableCell>
                    <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Dispatched From</TableCell>
                    <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Due Date</TableCell>
                    <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {pendingTransfers.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={4} sx={{ textAlign: 'center', py: 3, color: 'text.secondary' }}>
                        No pending custody transfers awaiting your receipt.
                      </TableCell>
                    </TableRow>
                  ) : (
                    pendingTransfers.slice(0, 5).map((t) => (
                      <TableRow key={t.id}>
                        <TableCell sx={{ fontWeight: 600, color: 'primary.main' }}>
                          {t.evidence_number || t.evidence_id.slice(0, 8)}
                        </TableCell>
                        <TableCell>{t.from_user_name || t.from_user_id.slice(0, 8)}</TableCell>
                        <TableCell>{t.ack_due_at ? t.ack_due_at.slice(0, 16).replace('T', ' ') : '-'}</TableCell>
                        <TableCell>
                          <StatusChip status={t.status} />
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Card>
        </Grid>

        {/* Right: Recent Audit Chain Activity */}
        <Grid item xs={12} md={6}>
          <Card sx={{ border: '1px solid', borderColor: 'divider', height: '100%' }}>
            <Box sx={{ p: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                RECENT AUDIT CHAIN JOURNAL
              </Typography>
            </Box>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow sx={{ backgroundColor: (theme) => (theme.palette.mode === 'dark' ? '#2f2f2f' : '#eef0f3') }}>
                    <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Seq #</TableCell>
                    <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Action</TableCell>
                    <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Actor</TableCell>
                    <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Timestamp (UTC)</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {recentAudit.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={4} sx={{ textAlign: 'center', py: 3, color: 'text.secondary' }}>
                        No journal entries available.
                      </TableCell>
                    </TableRow>
                  ) : (
                    recentAudit.slice(0, 6).map((log) => (
                      <TableRow key={log.seq}>
                        <TableCell sx={{ fontFamily: 'monospace', fontWeight: 600 }}>#{log.seq}</TableCell>
                        <TableCell>
                          <StatusChip status={log.action} />
                        </TableCell>
                        <TableCell>{log.actor_name || log.actor_role || 'SYSTEM'}</TableCell>
                        <TableCell sx={{ fontSize: '12px', color: 'text.secondary' }}>
                          {log.ts ? log.ts.slice(0, 19).replace('T', ' ') : '-'}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};
