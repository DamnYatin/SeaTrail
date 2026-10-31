import React, { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CircularProgress,
  Grid,
  LinearProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import ShieldIcon from '@mui/icons-material/Shield';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import GppGoodIcon from '@mui/icons-material/GppGood';
import GppBadIcon from '@mui/icons-material/GppBad';

import { apiClient } from '../api/client';
import { StatusChip } from '../components/StatusChip';

interface SweepIssue {
  evidence_id: string;
  evidence_number?: string;
  item_name?: string;
  reason: string;
  integrity_state: string;
}

export const IntegrityPage: React.FC = () => {
  // Chain Verification
  const [verifyingChain, setVerifyingChain] = useState(false);
  const [chainResult, setChainResult] = useState<{
    ok: boolean;
    checked: number;
    head_seq: number;
    head_hash: string;
    first_broken_seq?: number | null;
    reason?: string | null;
  } | null>(null);

  // Evidence Sweep
  const [sweeping, setSweeping] = useState(false);
  const [sweepResult, setSweepResult] = useState<{
    total: number;
    checked: number;
    failed: number;
    status: string;
    issues?: SweepIssue[];
  } | null>(null);

  const handleVerifyChain = async () => {
    setVerifyingChain(true);
    try {
      const { data } = await apiClient.POST('/api/v1/audit/verify');
      if (data) {
        setChainResult(data);
      }
    } catch (e) {
      console.error('Audit chain verify failed', e);
    } finally {
      setVerifyingChain(false);
    }
  };

  const handleRunSweep = async () => {
    setSweeping(true);
    try {
      const { data, error } = await apiClient.POST('/api/v1/integrity/evidence-sweep');
      if (data && !error) {
        setSweepResult(
          data as unknown as {
            total: number;
            checked: number;
            failed: number;
            status: string;
            issues?: SweepIssue[];
          }
        );
      }
    } catch (e) {
      console.error('Evidence sweep failed', e);
    } finally {
      setSweeping(false);
    }
  };

  return (
    <Box sx={{ p: 3, maxWidth: 1600, mx: 'auto' }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 600, mb: 0.5 }}>
          Cryptographic Integrity & Verification Sweep
        </Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          Continuous three-way binding checks: S3 storage object ↔ database metadata ↔ append-only audit chain
        </Typography>
      </Box>

      {/* Two Action Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        {/* Card 1: Audit Chain Verification */}
        <Grid item xs={12} md={6}>
          <Card sx={{ p: 3, border: '1px solid', borderColor: 'divider', height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.5 }}>
                <ShieldIcon sx={{ color: 'primary.main', fontSize: 28 }} />
                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                  Audit Chain Hash Check
                </Typography>
              </Box>
              <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
                Sequentially re-computes SHA-256 hash chains across all ledger rows from genesis (`seq=1`) to the head entry and checks against signed checkpoints.
              </Typography>

              {chainResult && (
                <Alert
                  severity={chainResult.ok ? 'success' : 'error'}
                  icon={chainResult.ok ? <GppGoodIcon /> : <GppBadIcon />}
                  sx={{ mb: 2 }}
                >
                  <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                    {chainResult.ok ? 'CHAIN INTEGRITY VERIFIED' : 'CHAIN TAMPER DETECTED'}
                  </Typography>
                  <Typography variant="body2" sx={{ fontSize: '13px' }}>
                    {chainResult.ok
                      ? `Checked ${chainResult.checked} consecutive blocks. Strict linkage confirmed.`
                      : `Breach detected at entry #${chainResult.first_broken_seq}: ${chainResult.reason}`}
                  </Typography>
                </Alert>
              )}
            </Box>

            <Button
              variant="contained"
              onClick={handleVerifyChain}
              disabled={verifyingChain}
              startIcon={verifyingChain ? <CircularProgress size={16} color="inherit" /> : <ShieldIcon />}
              sx={{ alignSelf: 'flex-start' }}
            >
              {verifyingChain ? 'Verifying Chain...' : 'Verify Audit Chain'}
            </Button>
          </Card>
        </Grid>

        {/* Card 2: Full Evidence Storage Sweep */}
        <Grid item xs={12} md={6}>
          <Card sx={{ p: 3, border: '1px solid', borderColor: 'divider', height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.5 }}>
                <FactCheckIcon sx={{ color: '#5cb867', fontSize: 28 }} />
                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                  Three-Way Evidence Sweep
                </Typography>
              </Box>
              <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
                Downloads and streams all stored digital artifacts from S3/MinIO, re-computes SHA-256 digests, and verifies match against database row and audit intake event.
              </Typography>

              {sweeping && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5 }}>
                    Streaming objects and verifying SHA-256 digests...
                  </Typography>
                  <LinearProgress />
                </Box>
              )}

              {sweepResult && !sweeping && (
                <Alert
                  severity={sweepResult.failed > 0 ? 'error' : 'success'}
                  sx={{ mb: 2 }}
                >
                  <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                    {sweepResult.failed > 0
                      ? `SWEEP COMPLETED: ${sweepResult.failed} ISSUES DETECTED`
                      : 'ALL EVIDENCE ITEMS VERIFIED OK'}
                  </Typography>
                  <Typography variant="body2" sx={{ fontSize: '13px' }}>
                    Checked {sweepResult.checked} of {sweepResult.total} items. Failed count: {sweepResult.failed}.
                  </Typography>
                </Alert>
              )}
            </Box>

            <Button
              variant="contained"
              color="success"
              onClick={handleRunSweep}
              disabled={sweeping}
              startIcon={sweeping ? <CircularProgress size={16} color="inherit" /> : <FactCheckIcon />}
              sx={{ alignSelf: 'flex-start' }}
            >
              {sweeping ? 'Running Sweep...' : 'Run Evidence Sweep'}
            </Button>
          </Card>
        </Grid>
      </Grid>

      {/* Sweep Issues Table */}
      {sweepResult?.issues && sweepResult.issues.length > 0 && (
        <Card sx={{ border: '1px solid', borderColor: 'error.main' }}>
          <Box sx={{ p: 2, backgroundColor: 'rgba(239, 83, 80, 0.1)', borderBottom: '1px solid', borderColor: 'error.main' }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'error.main' }}>
              INTEGRITY SWEEP ANOMALIES & BREACHES
            </Typography>
          </Box>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600 }}>Evidence Identifier</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Item Name</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Integrity State</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Failure Reason</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {sweepResult.issues.map((issue) => (
                  <TableRow key={issue.evidence_id}>
                    <TableCell sx={{ fontWeight: 700, color: 'error.main' }}>
                      {issue.evidence_number || issue.evidence_id.slice(0, 8)}
                    </TableCell>
                    <TableCell>{issue.item_name || 'Evidence Item'}</TableCell>
                    <TableCell>
                      <StatusChip status={issue.integrity_state} />
                    </TableCell>
                    <TableCell>{issue.reason}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Card>
      )}
    </Box>
  );
};
