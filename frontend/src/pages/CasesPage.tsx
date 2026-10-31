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
  Drawer,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
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
import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';

import { apiClient } from '../api/client';
import { StatusChip } from '../components/StatusChip';
import { HashText } from '../components/HashText';
import { useAuth } from '../auth/AuthContext';

interface CaseItem {
  id: string;
  case_number: string;
  name: string;
  description?: string;
  status: 'OPEN' | 'CLOSED';
  classification: 'RESTRICTED' | 'CONFIDENTIAL' | 'INTERNAL';
  lead_user_id?: string;
  lead_name?: string;
  legal_hold: boolean;
  legal_hold_reason?: string;
  evidence_counter: number;
  opened_at: string;
  closed_at?: string;
}

interface TimelineEntry {
  ts: string;
  source: 'EVENT' | 'REGISTERED' | 'TRANSFER' | 'ACKNOWLEDGED' | 'ANNOTATION' | 'APPROVAL';
  title: string;
  detail: string;
  actor_name?: string;
  evidence_number?: string;
}

interface CaseMemberItem {
  user_id: string;
  user_name?: string | null;
  user_email?: string | null;
  case_role: string;
}

interface CaseEvidenceItem {
  id: string;
  evidence_number: string;
  item_name: string;
  sha256: string;
  status: string;
}

export const CasesPage: React.FC = () => {
  const { user } = useAuth();

  const [cases, setCases] = useState<CaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Selected Case & Detail
  const [selectedCase, setSelectedCase] = useState<CaseItem | null>(null);
  const [activeTab, setActiveTab] = useState(0);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [caseEvidence, setCaseEvidence] = useState<CaseEvidenceItem[]>([]);
  const [caseMembers, setCaseMembers] = useState<CaseMemberItem[]>([]);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Create Case Dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newClassification, setNewClassification] = useState<'CONFIDENTIAL' | 'RESTRICTED' | 'INTERNAL'>('CONFIDENTIAL');
  const [creating, setCreating] = useState(false);

  const fetchCases = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const { data, error } = await apiClient.GET('/api/v1/cases');
      if (data && !error) {
        setCases(data as unknown as CaseItem[]);
      } else if (error) {
        const errObj = error as { error?: { message?: string } } | undefined;
        setErrorMsg(errObj?.error?.message || 'Access restricted');
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to load cases');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCases();
  }, []);

  const handleSelectCase = async (c: CaseItem) => {
    setSelectedCase(c);
    setActiveTab(0);
    setLoadingDetail(true);
    try {
      // Preload timeline and evidence
      const [tlRes, evRes, memRes] = await Promise.all([
        apiClient.GET('/api/v1/cases/{case_id}/timeline', { params: { path: { case_id: c.id } } }).catch(() => ({ data: [] })),
        apiClient.GET('/api/v1/evidence', { params: { query: { case_id: c.id } } }).catch(() => ({ data: { items: [] } })),
        apiClient.GET('/api/v1/cases/{case_id}/members', { params: { path: { case_id: c.id } } }).catch(() => ({ data: [] })),
      ]);

      if (tlRes.data) setTimeline(tlRes.data as unknown as TimelineEntry[]);
      if (evRes.data && 'items' in evRes.data) {
        setCaseEvidence(evRes.data.items as unknown as CaseEvidenceItem[]);
      }
      if (memRes.data && Array.isArray(memRes.data)) {
        setCaseMembers(memRes.data as unknown as CaseMemberItem[]);
      }
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleCreateCase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const { data, error } = await apiClient.POST('/api/v1/cases', {
        body: {
          name: newName.trim(),
          description: newDesc.trim() || undefined,
          classification: newClassification,
        },
      });

      if (error || !data) {
        const errObj = error as { error?: { message?: string } } | undefined;
        throw new Error(errObj?.error?.message || 'Failed to initialize case');
      }

      setCreateOpen(false);
      setNewName('');
      setNewDesc('');
      fetchCases();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Case creation failed');
    } finally {
      setCreating(false);
    }
  };

  return (
    <Box sx={{ p: 3, maxWidth: 1600, mx: 'auto' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 600, mb: 0.5 }}>
            Case Management
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            Authorized investigation workspaces, entity directories, and merged incident timelines
          </Typography>
        </Box>

        {(user?.role === 'SUPERVISOR' || user?.role === 'INVESTIGATOR') && (
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setCreateOpen(true)}
            sx={{ fontWeight: 600, fontSize: '13px' }}
          >
            Create Case
          </Button>
        )}
      </Box>

      {errorMsg && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {errorMsg}
        </Alert>
      )}

      <Card sx={{ border: '1px solid', borderColor: 'divider' }}>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ backgroundColor: (theme) => (theme.palette.mode === 'dark' ? '#2f2f2f' : '#eef0f3') }}>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Case Number</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Case Title</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Classification</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Status</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Lead Investigator</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Evidence Count</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Opened Date</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={7} sx={{ textAlign: 'center', py: 4 }}>
                    <CircularProgress size={24} />
                  </TableCell>
                </TableRow>
              ) : cases.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} sx={{ textAlign: 'center', py: 4, color: 'text.secondary' }}>
                    No assigned cases found for your credentials.
                  </TableCell>
                </TableRow>
              ) : (
                cases.map((c) => (
                  <TableRow
                    key={c.id}
                    hover
                    onClick={() => handleSelectCase(c)}
                    sx={{ cursor: 'pointer' }}
                  >
                    <TableCell sx={{ color: '#5cb867', fontWeight: 600, fontSize: '13px' }}>
                      {c.case_number}
                      {c.legal_hold && (
                        <Chip
                          label="HOLD"
                          size="small"
                          sx={{ ml: 1, backgroundColor: '#d32f2f', color: '#fff', fontSize: '9px', height: 16 }}
                        />
                      )}
                    </TableCell>
                    <TableCell sx={{ fontWeight: 500 }}>{c.name}</TableCell>
                    <TableCell>
                      <Chip label={c.classification} size="small" sx={{ fontSize: '10px' }} />
                    </TableCell>
                    <TableCell>
                      <StatusChip status={c.status} />
                    </TableCell>
                    <TableCell>{c.lead_name || 'Assigned Lead'}</TableCell>
                    <TableCell>{c.evidence_counter} items</TableCell>
                    <TableCell sx={{ color: 'text.secondary' }}>
                      {c.opened_at ? c.opened_at.slice(0, 10) : '-'}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>

      {/* Case Detail Drawer */}
      <Drawer
        anchor="right"
        open={Boolean(selectedCase)}
        onClose={() => setSelectedCase(null)}
        PaperProps={{ sx: { width: { xs: '100%', md: 720 }, p: 3 } }}
      >
        {selectedCase && (
          <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
              <Box>
                <Typography variant="caption" sx={{ color: '#5cb867', fontWeight: 700, fontSize: '14px' }}>
                  {selectedCase.case_number}
                </Typography>
                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                  {selectedCase.name}
                </Typography>
              </Box>
              <Button size="small" onClick={() => setSelectedCase(null)}>
                <CloseIcon />
              </Button>
            </Box>

            <Tabs
              value={activeTab}
              onChange={(_, val) => setActiveTab(val)}
              sx={{ borderBottom: '1px solid', borderColor: 'divider', mb: 2 }}
            >
              <Tab label="Overview" />
              <Tab label={`Evidence (${caseEvidence.length})`} />
              <Tab label="Timeline" />
              <Tab label={`Members (${caseMembers.length})`} />
            </Tabs>

            {loadingDetail ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                <CircularProgress size={30} />
              </Box>
            ) : (
              <Box sx={{ flex: 1, overflowY: 'auto' }}>
                {/* Tab 0: Overview */}
                {activeTab === 0 && (
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <Box sx={{ p: 2, backgroundColor: 'background.default', borderRadius: 1 }}>
                      <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 700, display: 'block', mb: 0.5 }}>
                        CASE SCOPE & DESCRIPTION
                      </Typography>
                      <Typography variant="body2">{selectedCase.description || 'No description provided.'}</Typography>
                    </Box>

                    <Box sx={{ display: 'grid', gridTemplateColumns: '140px 1fr', rowGap: 1.5, fontSize: '13px' }}>
                      <Typography sx={{ color: 'text.secondary' }}>Classification:</Typography>
                      <Typography sx={{ fontWeight: 600 }}>{selectedCase.classification}</Typography>

                      <Typography sx={{ color: 'text.secondary' }}>Status:</Typography>
                      <StatusChip status={selectedCase.status} />

                      <Typography sx={{ color: 'text.secondary' }}>Opened At:</Typography>
                      <Typography>{selectedCase.opened_at ? selectedCase.opened_at.slice(0, 19).replace('T', ' ') : '-'}</Typography>

                      <Typography sx={{ color: 'text.secondary' }}>Legal Hold:</Typography>
                      <Typography sx={{ color: selectedCase.legal_hold ? 'error.main' : 'inherit', fontWeight: 600 }}>
                        {selectedCase.legal_hold ? `ACTIVE HOLD: ${selectedCase.legal_hold_reason}` : 'None'}
                      </Typography>
                    </Box>
                  </Box>
                )}

                {/* Tab 1: Evidence */}
                {activeTab === 1 && (
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                    {caseEvidence.map((ev) => (
                      <Box
                        key={ev.id}
                        sx={{
                          p: 1.5,
                          backgroundColor: 'background.default',
                          borderRadius: 1,
                          border: '1px solid',
                          borderColor: 'divider',
                        }}
                      >
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                          <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'primary.main' }}>
                            {ev.evidence_number} — {ev.item_name}
                          </Typography>
                          <StatusChip status={ev.status} />
                        </Box>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                            SHA-256:
                          </Typography>
                          <HashText hash={ev.sha256} truncate />
                        </Box>
                      </Box>
                    ))}
                  </Box>
                )}

                {/* Tab 2: Merged Timeline */}
                {activeTab === 2 && (
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, position: 'relative', pl: 3 }}>
                    <Box
                      sx={{
                        position: 'absolute',
                        left: 10,
                        top: 0,
                        bottom: 0,
                        width: 2,
                        backgroundColor: 'divider',
                      }}
                    />
                    {timeline.length === 0 ? (
                      <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                        No recorded incident events yet.
                      </Typography>
                    ) : (
                      timeline.map((entry, idx) => (
                        <Box key={idx} sx={{ position: 'relative' }}>
                          <Box
                            sx={{
                              position: 'absolute',
                              left: -28,
                              top: 4,
                              width: 10,
                              height: 10,
                              borderRadius: '50%',
                              backgroundColor: 'primary.main',
                            }}
                          />
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                            <Chip label={entry.source} size="small" sx={{ fontSize: '9px', height: 18 }} />
                            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                              {entry.ts ? entry.ts.slice(0, 16).replace('T', ' ') : ''}
                            </Typography>
                          </Box>
                          <Typography variant="body2" sx={{ fontWeight: 600 }}>
                            {entry.title}
                          </Typography>
                          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                            {entry.detail} {entry.actor_name ? `• by ${entry.actor_name}` : ''}
                          </Typography>
                        </Box>
                      ))
                    )}
                  </Box>
                )}

                {/* Tab 3: Members */}
                {activeTab === 3 && (
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                    {caseMembers.map((m) => (
                      <Box
                        key={m.user_id}
                        sx={{
                          p: 1.5,
                          backgroundColor: 'background.default',
                          borderRadius: 1,
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <Box>
                          <Typography variant="body2" sx={{ fontWeight: 600 }}>
                            {m.user_name || m.user_id.slice(0, 8)}
                          </Typography>
                          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                            {m.user_email}
                          </Typography>
                        </Box>
                        <Chip label={m.case_role} size="small" color={m.case_role === 'LEAD' ? 'primary' : 'default'} />
                      </Box>
                    ))}
                  </Box>
                )}
              </Box>
            )}
          </Box>
        )}
      </Drawer>

      {/* Create Case Dialog */}
      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
        <Box component="form" onSubmit={handleCreateCase}>
          <DialogTitle sx={{ fontWeight: 600, fontSize: '16px' }}>
            Open New Investigation Case
          </DialogTitle>
          <DialogContent sx={{ py: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <TextField
              fullWidth
              required
              size="small"
              label="Case Name / Operation Title"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="e.g. Operation Blue Shield — Mule Accounts"
            />
            <TextField
              fullWidth
              size="small"
              multiline
              rows={3}
              label="Incident Background & Scope"
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
            />
            <FormControl fullWidth size="small">
              <InputLabel>Classification</InputLabel>
              <Select
                value={newClassification}
                label="Classification"
                onChange={(e) => setNewClassification(e.target.value as 'CONFIDENTIAL' | 'RESTRICTED' | 'INTERNAL')}
              >
                <MenuItem value="CONFIDENTIAL">CONFIDENTIAL</MenuItem>
                <MenuItem value="RESTRICTED">RESTRICTED</MenuItem>
                <MenuItem value="INTERNAL">INTERNAL</MenuItem>
              </Select>
            </FormControl>
          </DialogContent>
          <DialogActions sx={{ p: 2 }}>
            <Button onClick={() => setCreateOpen(false)} disabled={creating}>
              Cancel
            </Button>
            <Button type="submit" variant="contained" disabled={creating}>
              {creating ? 'Creating...' : 'Open Case'}
            </Button>
          </DialogActions>
        </Box>
      </Dialog>
    </Box>
  );
};
