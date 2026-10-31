import React, { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  Drawer,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  Typography,
} from '@mui/material';
import ShieldIcon from '@mui/icons-material/Shield';
import GppGoodIcon from '@mui/icons-material/GppGood';
import GppBadIcon from '@mui/icons-material/GppBad';
import CloseIcon from '@mui/icons-material/Close';
import BookmarkBorderIcon from '@mui/icons-material/BookmarkBorder';

import { apiClient } from '../api/client';
import { StatusChip } from '../components/StatusChip';
import { HashText } from '../components/HashText';

interface AuditEntry {
  seq: number;
  ts: string;
  actor_id?: string;
  actor_name?: string;
  actor_role?: string;
  action: string;
  case_id?: string;
  evidence_id?: string;
  evidence_number?: string;
  payload: Record<string, unknown>;
  ip?: string;
  prev_hash: string;
  entry_hash: string;
}

interface CheckpointItem {
  id: string;
  seq_to: number;
  head_hash: string;
  signature_b64: string;
  public_key_id: string;
  created_at: string;
}

export const AuditLogPage: React.FC = () => {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [loading, setLoading] = useState(true);

  // Chain Verification State
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<{
    ok: boolean;
    checked: number;
    head_seq: number;
    head_hash: string;
    first_broken_seq?: number | null;
    reason?: string | null;
  } | null>(null);

  // Selected Row Drawer
  const [selectedEntry, setSelectedEntry] = useState<AuditEntry | null>(null);

  // Checkpoints
  const [checkpoints, setCheckpoints] = useState<CheckpointItem[]>([]);
  const [creatingCheckpoint, setCreatingCheckpoint] = useState(false);

  const fetchAuditEntries = async () => {
    setLoading(true);
    try {
      const { data, error } = await apiClient.GET('/api/v1/audit', {
        params: {
          query: {
            page: page + 1,
            page_size: pageSize,
          },
        },
      });
      if (data && !error) {
        setEntries((data.items as unknown as AuditEntry[]) || []);
        setTotal(data.total || 0);
      }
    } catch (e) {
      console.error('Failed to load audit entries', e);
    } finally {
      setLoading(false);
    }
  };

  const fetchCheckpoints = async () => {
    try {
      const { data } = await apiClient.GET('/api/v1/audit/checkpoints');
      if (data && Array.isArray(data)) {
        setCheckpoints(data as unknown as CheckpointItem[]);
      }
    } catch {
      // Ignored
    }
  };

  const handleVerifyChain = async () => {
    setVerifying(true);
    try {
      const { data } = await apiClient.POST('/api/v1/audit/verify');
      if (data) {
        setVerifyResult(data);
      }
    } catch (e) {
      console.error('Chain verification failed', e);
    } finally {
      setVerifying(false);
    }
  };

  const handleCreateCheckpoint = async () => {
    setCreatingCheckpoint(true);
    try {
      await apiClient.POST('/api/v1/audit/checkpoints');
      fetchCheckpoints();
      handleVerifyChain();
    } catch (e) {
      console.error('Failed to create checkpoint', e);
    } finally {
      setCreatingCheckpoint(false);
    }
  };

  useEffect(() => {
    fetchAuditEntries();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize]);

  useEffect(() => {
    handleVerifyChain();
    fetchCheckpoints();
  }, []);

  return (
    <Box sx={{ p: 3, maxWidth: 1600, mx: 'auto' }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 600, mb: 0.5 }}>
          Append-Only Audit Log
        </Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          Cryptographic SHA-256 hash-chained ledger bound by Ed25519-signed checkpoints
        </Typography>
      </Box>

      {/* Verification Status Banner */}
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
              verifyResult?.ok === false
                ? 'rgba(239, 83, 80, 0.1)'
                : theme.palette.mode === 'dark'
                ? '#252525'
                : '#f8fafc',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {verifyResult?.ok === false ? (
              <GppBadIcon sx={{ fontSize: 36, color: 'error.main' }} />
            ) : (
              <GppGoodIcon sx={{ fontSize: 36, color: 'success.main' }} />
            )}
            <Box>
              <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                {verifyResult?.ok === false
                  ? `CHAIN BREACH DETECTED AT ENTRY #${verifyResult.first_broken_seq}`
                  : `HASH CHAIN VERIFIED INTACT (${verifyResult?.checked ?? total} ENTRIES)`}
              </Typography>
              <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '13px' }}>
                {verifyResult?.ok === false
                  ? `Tamper anomaly reason: ${verifyResult.reason}`
                  : 'Every sequential entry strictly matches SHA256(prev_hash || canonical_bytes). No gaps or mutations detected.'}
              </Typography>
            </Box>
          </Box>

          <Button
            variant="contained"
            color={verifyResult?.ok === false ? 'error' : 'primary'}
            onClick={handleVerifyChain}
            disabled={verifying}
            startIcon={verifying ? <CircularProgress size={16} color="inherit" /> : <ShieldIcon />}
          >
            {verifying ? 'Verifying...' : 'Verify Chain'}
          </Button>
        </Box>
      </Card>

      {/* Audit Log Table */}
      <Card sx={{ mb: 3, border: '1px solid', borderColor: 'divider' }}>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ backgroundColor: (theme) => (theme.palette.mode === 'dark' ? '#2f2f2f' : '#eef0f3') }}>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Seq</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Timestamp (UTC)</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Action</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Actor</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Role</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Evidence</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Prev Hash</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Entry Hash</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={8} sx={{ textAlign: 'center', py: 4 }}>
                    <CircularProgress size={24} />
                  </TableCell>
                </TableRow>
              ) : entries.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} sx={{ textAlign: 'center', py: 4, color: 'text.secondary' }}>
                    No audit records logged.
                  </TableCell>
                </TableRow>
              ) : (
                entries.map((log) => (
                  <TableRow
                    key={log.seq}
                    hover
                    onClick={() => setSelectedEntry(log)}
                    sx={{ cursor: 'pointer' }}
                  >
                    <TableCell sx={{ fontFamily: 'monospace', fontWeight: 700, color: 'primary.main' }}>
                      #{log.seq}
                    </TableCell>
                    <TableCell sx={{ fontSize: '12px', color: 'text.secondary' }}>
                      {log.ts ? log.ts.slice(0, 19).replace('T', ' ') : '-'}
                    </TableCell>
                    <TableCell>
                      <StatusChip status={log.action} />
                    </TableCell>
                    <TableCell>{log.actor_name || log.actor_id?.slice(0, 8) || 'SYSTEM'}</TableCell>
                    <TableCell>
                      <Chip label={log.actor_role || 'SYSTEM'} size="small" sx={{ fontSize: '10px' }} />
                    </TableCell>
                    <TableCell sx={{ fontWeight: 600, color: 'primary.main' }}>
                      {log.evidence_number || '-'}
                    </TableCell>
                    <TableCell>
                      <HashText hash={log.prev_hash} truncate />
                    </TableCell>
                    <TableCell>
                      <HashText hash={log.entry_hash} truncate />
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>

        <TablePagination
          component="div"
          count={total}
          page={page}
          onPageChange={(_, p) => setPage(p)}
          rowsPerPage={pageSize}
          onRowsPerPageChange={(e) => {
            setPageSize(parseInt(e.target.value, 10));
            setPage(0);
          }}
          rowsPerPageOptions={[25, 50, 100]}
        />
      </Card>

      {/* Signed Checkpoints Section */}
      <Card sx={{ border: '1px solid', borderColor: 'divider' }}>
        <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid', borderColor: 'divider' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <BookmarkBorderIcon sx={{ color: 'primary.main' }} />
            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
              ED25519-SIGNED AUDIT CHECKPOINTS
            </Typography>
          </Box>
          <Button
            size="small"
            variant="outlined"
            onClick={handleCreateCheckpoint}
            disabled={creatingCheckpoint}
            startIcon={creatingCheckpoint ? <CircularProgress size={14} /> : null}
            sx={{ fontSize: '12px' }}
          >
            {creatingCheckpoint ? 'Signing...' : 'Create Checkpoint'}
          </Button>
        </Box>

        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ backgroundColor: (theme) => (theme.palette.mode === 'dark' ? '#2f2f2f' : '#eef0f3') }}>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Coverage (Seq To)</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Head Hash</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Ed25519 Signature (b64)</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Key ID</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Created (UTC)</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {checkpoints.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} sx={{ textAlign: 'center', py: 3, color: 'text.secondary' }}>
                    No signed checkpoints created yet.
                  </TableCell>
                </TableRow>
              ) : (
                checkpoints.map((cp) => (
                  <TableRow key={cp.id}>
                    <TableCell sx={{ fontWeight: 700 }}>1 .. #{cp.seq_to}</TableCell>
                    <TableCell>
                      <HashText hash={cp.head_hash} truncate />
                    </TableCell>
                    <TableCell sx={{ fontFamily: 'monospace', fontSize: '11px' }}>
                      {cp.signature_b64.slice(0, 24)}...
                    </TableCell>
                    <TableCell>{cp.public_key_id}</TableCell>
                    <TableCell sx={{ fontSize: '12px', color: 'text.secondary' }}>
                      {cp.created_at ? cp.created_at.slice(0, 19).replace('T', ' ') : '-'}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>

      {/* Entry Detail Side Drawer */}
      <Drawer
        anchor="right"
        open={Boolean(selectedEntry)}
        onClose={() => setSelectedEntry(null)}
        PaperProps={{ sx: { width: { xs: '100%', md: 650 }, p: 3 } }}
      >
        {selectedEntry && (
          <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                Audit Transaction #{selectedEntry.seq}
              </Typography>
              <IconButton size="small" onClick={() => setSelectedEntry(null)}>
                <CloseIcon />
              </IconButton>
            </Box>

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, flex: 1, overflowY: 'auto' }}>
              <Box sx={{ p: 2, backgroundColor: 'background.default', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
                <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', display: 'block', mb: 0.5 }}>
                  ENTRY HASH
                </Typography>
                <HashText hash={selectedEntry.entry_hash} />
                <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', display: 'block', mt: 1.5, mb: 0.5 }}>
                  PREVIOUS HASH
                </Typography>
                <HashText hash={selectedEntry.prev_hash} />
              </Box>

              <Box sx={{ display: 'grid', gridTemplateColumns: '120px 1fr', rowGap: 1, fontSize: '13px' }}>
                <Typography sx={{ color: 'text.secondary' }}>Action:</Typography>
                <Typography sx={{ fontWeight: 600 }}>{selectedEntry.action}</Typography>

                <Typography sx={{ color: 'text.secondary' }}>Actor:</Typography>
                <Typography>{selectedEntry.actor_name || selectedEntry.actor_id || 'SYSTEM'}</Typography>

                <Typography sx={{ color: 'text.secondary' }}>Role:</Typography>
                <Typography>{selectedEntry.actor_role || 'SYSTEM'}</Typography>

                <Typography sx={{ color: 'text.secondary' }}>IP Address:</Typography>
                <Typography sx={{ fontFamily: 'monospace' }}>{selectedEntry.ip || '127.0.0.1'}</Typography>

                <Typography sx={{ color: 'text.secondary' }}>Timestamp:</Typography>
                <Typography sx={{ fontFamily: 'monospace' }}>{selectedEntry.ts}</Typography>
              </Box>

              <Box sx={{ mt: 1 }}>
                <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', display: 'block', mb: 1 }}>
                  CANONICAL TRANSACTION PAYLOAD (JSON)
                </Typography>
                <Box
                  component="pre"
                  sx={{
                    p: 2,
                    backgroundColor: 'background.default',
                    borderRadius: 1,
                    border: '1px solid',
                    borderColor: 'divider',
                    fontFamily: 'monospace',
                    fontSize: '12px',
                    overflowX: 'auto',
                  }}
                >
                  {JSON.stringify(selectedEntry.payload, null, 2)}
                </Box>
              </Box>
            </Box>
          </Box>
        )}
      </Drawer>
    </Box>
  );
};
