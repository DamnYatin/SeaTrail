import React, { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Card,
  Checkbox,
  Chip,
  CircularProgress,
  FormControl,
  Grid,
  IconButton,
  InputAdornment,
  Menu,
  MenuItem,
  Popover,
  Select,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowRightIcon from '@mui/icons-material/KeyboardArrowRight';
import FileDownloadIcon from '@mui/icons-material/FileDownload';
import FilterAltOffIcon from '@mui/icons-material/FilterAltOff';
import FilterListIcon from '@mui/icons-material/FilterList';
import RefreshIcon from '@mui/icons-material/Refresh';
import ViewColumnIcon from '@mui/icons-material/ViewColumn';
import SearchIcon from '@mui/icons-material/Search';
import PrintIcon from '@mui/icons-material/Print';

import { apiClient, getAccessToken } from '../api/client';
import { HashText } from '../components/HashText';
import { StatusChip } from '../components/StatusChip';
import { useAuth } from '../auth/AuthContext';

import { CreateEvidenceDialog } from '../components/CreateEvidenceDialog';
import { TransferCustodyDialog } from '../components/TransferCustodyDialog';
import { AcknowledgeTransferDialog } from '../components/AcknowledgeTransferDialog';
import { AddAnnotationDialog } from '../components/AddAnnotationDialog';
import { CreateLinkDialog } from '../components/CreateLinkDialog';
import { LegalHoldDialog } from '../components/LegalHoldDialog';
import { ExportPackageDialog } from '../components/ExportPackageDialog';

interface EvidenceItemRow {
  id: string;
  evidence_number: string;
  case_id: string;
  case_number: string;
  case_name?: string;
  type: string;
  item_name: string;
  description?: string;
  source_description?: string;
  device_make?: string;
  device_model?: string;
  device_serial?: string;
  original_filename?: string;
  size_bytes: number;
  sha256: string;
  intake_at: string;
  current_custodian_id?: string;
  current_custodian_name?: string;
  current_location?: string;
  status: string;
  integrity_state: string;
  last_verified_at?: string;
  legal_hold: boolean;
  retention_until?: string;
  collected_by_name?: string;
  collected_at?: string;
  acquisition_method?: string;
  acquisition_tool?: string;
}

interface AnnotationItem {
  id: string;
  body: string;
  body_sha256: string;
  author_name?: string;
  created_at: string;
}

interface EvidenceLinkItem {
  id: string;
  target_type: string;
  target_id: string;
  relation: string;
  created_at: string;
}

interface TransferItem {
  id: string;
  from_user_name?: string;
  to_user_id?: string;
  to_user_name?: string;
  to_location?: string;
  reason: string;
  status: string;
  hash_at_send?: string;
  requested_at: string;
}

export const EvidencePage: React.FC = () => {
  const { user } = useAuth();

  // State
  const [items, setItems] = useState<EvidenceItemRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [expandedDetails, setExpandedDetails] = useState<Record<string, unknown>>({});
  const [activeTab, setActiveTab] = useState<Record<string, number>>({});

  // Sub-tab cached data
  const [tabAnnotations, setTabAnnotations] = useState<Record<string, AnnotationItem[]>>({});
  const [tabLinks, setTabLinks] = useState<Record<string, EvidenceLinkItem[]>>({});
  const [tabTransfers, setTabTransfers] = useState<Record<string, TransferItem[]>>({});

  // Cases and Users for selectors
  const [cases, setCases] = useState<Array<{ id: string; case_number: string; name: string }>>([]);
  const [users, setUsers] = useState<Array<{ id: string; full_name: string; email: string; role: string }>>([]);

  // Column visibility
  const [visibleColumns, setVisibleColumns] = useState<Record<string, boolean>>({
    sha256: false,
    integrity: false,
    collectedBy: false,
    retentionUntil: false,
  });

  // Action Menu
  const [actionAnchor, setActionAnchor] = useState<null | HTMLElement>(null);
  const [selectedActionItem, setSelectedActionItem] = useState<EvidenceItemRow | null>(null);

  // Print Label Menu
  const [printAnchor, setPrintAnchor] = useState<null | HTMLElement>(null);
  const [selectedPrintItem, setSelectedPrintItem] = useState<EvidenceItemRow | null>(null);

  // Column Chooser Menu
  const [columnMenuAnchor, setColumnMenuAnchor] = useState<null | HTMLElement>(null);

  // Filter Popover state
  const [filterAnchor, setFilterAnchor] = useState<null | HTMLElement>(null);
  const [typeFilter, setTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // Workflow Dialog States
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [transferDialogOpen, setTransferDialogOpen] = useState(false);
  const [activeTransferItem, setActiveTransferItem] = useState<EvidenceItemRow | null>(null);
  const [ackDialogOpen, setAckDialogOpen] = useState(false);
  const [activeAckTransfer, setActiveAckTransfer] = useState<{ id: string; evidenceNumber?: string; sendHash?: string } | null>(null);
  const [annotationDialogOpen, setAnnotationDialogOpen] = useState(false);
  const [activeAnnotationItem, setActiveAnnotationItem] = useState<EvidenceItemRow | null>(null);
  const [linkDialogOpen, setLinkDialogOpen] = useState(false);
  const [activeLinkItem, setActiveLinkItem] = useState<EvidenceItemRow | null>(null);
  const [legalHoldDialogOpen, setLegalHoldDialogOpen] = useState(false);
  const [activeLegalHoldItem, setActiveLegalHoldItem] = useState<EvidenceItemRow | null>(null);
  const [exportDialogOpen, setExportDialogOpen] = useState(false);
  const [activeExportItem, setActiveExportItem] = useState<EvidenceItemRow | null>(null);

  // Fetch Cases and Users
  useEffect(() => {
    const fetchCasesAndUsers = async () => {
      try {
        const { data: casesData } = await apiClient.GET('/api/v1/cases');
        if (casesData && Array.isArray(casesData)) {
          setCases(
            casesData.map((c) => ({
              id: c.id,
              case_number: c.case_number,
              name: c.name,
            }))
          );
        }
      } catch {
        // Ignored if forbidden
      }
    };
    fetchCasesAndUsers();
  }, []);

  // Fetch Evidence List
  const fetchEvidence = React.useCallback(async () => {
    setLoading(true);
    try {
      const queryParams: {
        page?: number;
        page_size?: number;
        q?: string | null;
        type?: string | null;
        status?: string | null;
      } = {
        page: page + 1,
        page_size: pageSize,
      };
      if (searchQuery.trim()) queryParams.q = searchQuery.trim();
      if (typeFilter) queryParams.type = typeFilter;
      if (statusFilter) queryParams.status = statusFilter;

      const { data, error } = await apiClient.GET('/api/v1/evidence', {
        params: { query: queryParams },
      });

      if (data && !error) {
        setItems((data.items as unknown as EvidenceItemRow[]) || []);
        setTotal(data.total || 0);
      }
    } catch (e) {
      console.error('Failed to load evidence', e);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, searchQuery, typeFilter, statusFilter]);

  useEffect(() => {
    fetchEvidence();
  }, [fetchEvidence]);

  // Load Sub-Tab Data
  const loadSubTabData = async (item: EvidenceItemRow, tabIdx: number) => {
    if (tabIdx === 1 && !tabAnnotations[item.id]) {
      try {
        const { data } = await apiClient.GET('/api/v1/evidence/{evidence_id}/annotations', {
          params: { path: { evidence_id: item.id } },
        });
        if (data && Array.isArray(data)) {
          setTabAnnotations((prev) => ({ ...prev, [item.id]: data as unknown as AnnotationItem[] }));
        }
      } catch {
        // Ignored
      }
    } else if (tabIdx === 2 && !tabLinks[item.id]) {
      try {
        const { data } = await apiClient.GET('/api/v1/evidence/{evidence_id}/links', {
          params: { path: { evidence_id: item.id } },
        });
        if (data && Array.isArray(data)) {
          setTabLinks((prev) => ({ ...prev, [item.id]: data as unknown as EvidenceLinkItem[] }));
        }
      } catch {
        // Ignored
      }
    } else if (tabIdx === 3 && !tabTransfers[item.id]) {
      try {
        const { data } = await apiClient.GET('/api/v1/transfers');
        if (data && Array.isArray(data)) {
          const itemTransfers = data.filter((t) => t.evidence_id === item.id);
          setTabTransfers((prev) => ({ ...prev, [item.id]: itemTransfers as unknown as TransferItem[] }));
        }
      } catch {
        // Ignored
      }
    }
  };

  // Handle expand row & cache detail
  const handleToggleExpand = async (item: EvidenceItemRow) => {
    if (expandedId === item.id) {
      setExpandedId(null);
      return;
    }

    setExpandedId(item.id);
    if (!expandedDetails[item.id]) {
      try {
        const { data } = await apiClient.GET('/api/v1/evidence/{evidence_id}', {
          params: { path: { evidence_id: item.id } },
        });
        if (data) {
          setExpandedDetails((prev) => ({ ...prev, [item.id]: data }));
        }
      } catch (e) {
        console.error('Failed to load item detail', e);
      }
    }

    // Preload tab 0 data or current tab data
    const currentTabIdx = activeTab[item.id] || 0;
    loadSubTabData(item, currentTabIdx);
  };

  // Open Transfer Dialog & Load Case Members
  const handleOpenTransfer = async (item: EvidenceItemRow) => {
    setActiveTransferItem(item);
    try {
      const { data } = await apiClient.GET('/api/v1/cases/{case_id}/members', {
        params: { path: { case_id: item.case_id } },
      });
      if (data && Array.isArray(data)) {
        setUsers(
          data.map((m: { user_id: string; user_name?: string | null; user_email?: string | null; case_role?: string }) => ({
            id: m.user_id,
            full_name: m.user_name || m.user_id.slice(0, 8),
            email: m.user_email || '',
            role: m.case_role || 'MEMBER',
          }))
        );
      }
    } catch {
      // Ignored
    }
    setTransferDialogOpen(true);
  };

  // CSV Export
  const handleExportCsv = () => {
    const token = getAccessToken();
    window.open(`/api/v1/evidence/export.csv?token=${token}`, '_blank');
  };

  // Clear filters
  const handleClearFilters = () => {
    setSearchQuery('');
    setTypeFilter('');
    setStatusFilter('');
    setPage(0);
  };

  // Label printing
  const handlePrintLabel = (size: 'standard' | 'small') => {
    if (!selectedPrintItem) return;
    const token = getAccessToken();
    window.open(`/api/v1/evidence/${selectedPrintItem.id}/label?size=${size}&token=${token}`, '_blank');
    setPrintAnchor(null);
  };

  // Verification action
  const handleVerifyItem = async (item: EvidenceItemRow) => {
    try {
      const { data } = await apiClient.POST('/api/v1/evidence/{evidence_id}/verify', {
        params: { path: { evidence_id: item.id } },
      });
      if (data) {
        fetchEvidence();
        if (expandedId === item.id) {
          const updated = await apiClient.GET('/api/v1/evidence/{evidence_id}', {
            params: { path: { evidence_id: item.id } },
          });
          if (updated.data) {
            setExpandedDetails((prev) => ({ ...prev, [item.id]: updated.data }));
          }
        }
      }
    } catch (e) {
      console.error('Verification failed', e);
    }
  };

  return (
    <Box sx={{ p: 3, maxWidth: 1600, mx: 'auto' }}>
      {/* Page Title & Subtitle */}
      <Box sx={{ mb: 2.5 }}>
        <Typography variant="h5" sx={{ fontWeight: 600, mb: 0.5 }}>
          Evidence Items
        </Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          Total {total} items registered across active and archived investigations
        </Typography>
      </Box>

      {/* Main Table Card */}
      <Card sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '4px' }}>
        {/* Toolbar */}
        <Box
          sx={{
            p: 1.5,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 1.5,
            borderBottom: '1px solid',
            borderColor: 'divider',
          }}
        >
          {/* Left: Create Evidence & Page Size */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Button
              variant="contained"
              size="small"
              startIcon={<AddIcon />}
              onClick={() => setCreateDialogOpen(true)}
              sx={{
                backgroundColor: 'primary.main',
                px: 2,
                py: 0.6,
                fontWeight: 600,
                fontSize: '13px',
              }}
            >
              Create Evidence
            </Button>

            <FormControl size="small">
              <Select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setPage(0);
                }}
                sx={{
                  height: 32,
                  fontSize: '12px',
                  borderColor: 'divider',
                }}
              >
                <MenuItem value={25}>25 Items ▾</MenuItem>
                <MenuItem value={50}>50 Items ▾</MenuItem>
                <MenuItem value={100}>100 Items ▾</MenuItem>
                <MenuItem value={500}>500 Items ▾</MenuItem>
              </Select>
            </FormControl>
          </Box>

          {/* Right: Actions, Filters, Search */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Tooltip title="Download CSV Metadata">
              <IconButton size="small" onClick={handleExportCsv}>
                <FileDownloadIcon sx={{ fontSize: '18px' }} />
              </IconButton>
            </Tooltip>

            <Tooltip title="Clear Filters">
              <IconButton size="small" onClick={handleClearFilters}>
                <FilterAltOffIcon sx={{ fontSize: '18px' }} />
              </IconButton>
            </Tooltip>

            <Tooltip title="Filter by Type or Status">
              <IconButton
                size="small"
                onClick={(e) => setFilterAnchor(e.currentTarget)}
              >
                <FilterListIcon sx={{ fontSize: '18px' }} />
              </IconButton>
            </Tooltip>

            <Tooltip title="Refresh Table">
              <IconButton size="small" onClick={fetchEvidence}>
                <RefreshIcon sx={{ fontSize: '18px' }} />
              </IconButton>
            </Tooltip>

            <Tooltip title="Choose Visible Columns">
              <IconButton size="small" onClick={(e) => setColumnMenuAnchor(e.currentTarget)}>
                <ViewColumnIcon sx={{ fontSize: '18px' }} />
              </IconButton>
            </Tooltip>

            <TextField
              size="small"
              placeholder="Search Evidence..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setPage(0);
              }}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon sx={{ fontSize: '18px', color: 'text.secondary' }} />
                  </InputAdornment>
                ),
                sx: { height: 32, fontSize: '12.5px' },
              }}
              sx={{ width: 220 }}
            />
          </Box>
        </Box>

        {/* Table */}
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ backgroundColor: (theme) => (theme.palette.mode === 'dark' ? '#2f2f2f' : '#eef0f3') }}>
                <TableCell sx={{ width: 40 }} />
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Evidence Number</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Case Number</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Case Name</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Intake Date</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Type</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Brand</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Item Name</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Progress</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Current Location</TableCell>

                {visibleColumns.sha256 && (
                  <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>SHA-256</TableCell>
                )}
                {visibleColumns.integrity && (
                  <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Integrity</TableCell>
                )}
                {visibleColumns.collectedBy && (
                  <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Collected By</TableCell>
                )}
                {visibleColumns.retentionUntil && (
                  <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Retention Until</TableCell>
                )}
              </TableRow>
            </TableHead>

            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={14} sx={{ textAlign: 'center', py: 4 }}>
                    <CircularProgress size={24} />
                  </TableCell>
                </TableRow>
              ) : items.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={14} sx={{ textAlign: 'center', py: 4, color: 'text.secondary' }}>
                    No evidence items found.
                  </TableCell>
                </TableRow>
              ) : (
                items.map((item) => {
                  const isExpanded = expandedId === item.id;

                  // Evidence Number Color Logic
                  let evColor = 'primary.main';
                  if (item.integrity_state !== 'OK' && item.integrity_state !== 'UNVERIFIED') {
                    evColor = 'error.main';
                  } else if (item.status === 'TRANSFER_PENDING' || item.status === 'PENDING_APPROVAL') {
                    evColor = 'warning.main';
                  }

                  return (
                    <React.Fragment key={item.id}>
                      <TableRow
                        sx={{
                          cursor: 'pointer',
                          backgroundColor: isExpanded ? 'rgba(63, 127, 224, 0.05)' : 'inherit',
                        }}
                        onClick={() => handleToggleExpand(item)}
                      >
                        <TableCell>
                          <IconButton size="small" sx={{ p: 0.2 }}>
                            {isExpanded ? (
                              <KeyboardArrowDownIcon sx={{ fontSize: '18px' }} />
                            ) : (
                              <KeyboardArrowRightIcon sx={{ fontSize: '18px' }} />
                            )}
                          </IconButton>
                        </TableCell>

                        <TableCell>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8 }}>
                            <Typography
                              component="span"
                              sx={{
                                color: evColor,
                                fontWeight: 600,
                                fontSize: '13px',
                                textDecoration: 'none',
                                '&:hover': { textDecoration: 'underline' },
                              }}
                            >
                              {item.evidence_number}
                            </Typography>
                            {item.legal_hold && (
                              <Chip
                                label="LEGAL HOLD"
                                size="small"
                                sx={{
                                  backgroundColor: '#d32f2f',
                                  color: '#fff',
                                  fontSize: '9px',
                                  fontWeight: 700,
                                  height: '16px',
                                }}
                              />
                            )}
                          </Box>
                        </TableCell>

                        <TableCell>
                          <Typography
                            component="span"
                            sx={{
                              color: '#5cb867',
                              fontWeight: 600,
                              fontSize: '13px',
                            }}
                          >
                            {item.case_number}
                          </Typography>
                        </TableCell>

                        <TableCell>{item.case_name || 'Case File'}</TableCell>
                        <TableCell>{item.intake_at ? item.intake_at.slice(0, 10) : 'N/A'}</TableCell>
                        <TableCell>{item.type}</TableCell>
                        <TableCell>{item.device_make || '-'}</TableCell>
                        <TableCell sx={{ fontWeight: 500 }}>{item.item_name}</TableCell>
                        <TableCell>
                          <StatusChip status={item.status} />
                        </TableCell>
                        <TableCell>{item.current_custodian_name || item.current_location || '-'}</TableCell>

                        {visibleColumns.sha256 && (
                          <TableCell>
                            <HashText hash={item.sha256} truncate />
                          </TableCell>
                        )}
                        {visibleColumns.integrity && (
                          <TableCell>
                            <StatusChip status={item.integrity_state} />
                          </TableCell>
                        )}
                        {visibleColumns.collectedBy && <TableCell>{item.collected_by_name || '-'}</TableCell>}
                        {visibleColumns.retentionUntil && <TableCell>{item.retention_until || '-'}</TableCell>}
                      </TableRow>

                      {/* Expanded Details Panel */}
                      {isExpanded && (
                        <TableRow>
                          <TableCell
                            colSpan={14}
                            sx={{
                              backgroundColor: (theme) =>
                                theme.palette.mode === 'dark' ? '#252525' : '#f8fafc',
                              p: 2.5,
                              borderBottom: '2px solid',
                              borderColor: 'primary.main',
                            }}
                          >
                            <Box sx={{ width: '100%' }}>
                              {/* Details Header */}
                              <Box
                                sx={{
                                  display: 'flex',
                                  justifyContent: 'space-between',
                                  alignItems: 'center',
                                  mb: 2,
                                  pb: 1,
                                  borderBottom: '1px solid',
                                  borderColor: 'divider',
                                }}
                              >
                                <Typography variant="h6" sx={{ fontSize: '14px', fontWeight: 700, letterSpacing: '0.5px' }}>
                                  EVIDENCE DETAILS: {item.evidence_number}
                                </Typography>

                                <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                                  <Typography
                                    component="span"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setSelectedPrintItem(item);
                                      setPrintAnchor(e.currentTarget);
                                    }}
                                    sx={{
                                      color: 'primary.main',
                                      fontSize: '13px',
                                      fontWeight: 600,
                                      cursor: 'pointer',
                                      display: 'flex',
                                      alignItems: 'center',
                                      gap: 0.5,
                                      '&:hover': { textDecoration: 'underline' },
                                    }}
                                  >
                                    <PrintIcon sx={{ fontSize: '16px' }} /> Print Label ▾
                                  </Typography>

                                  <Typography
                                    component="span"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setSelectedActionItem(item);
                                      setActionAnchor(e.currentTarget);
                                    }}
                                    sx={{
                                      color: 'primary.main',
                                      fontSize: '13px',
                                      fontWeight: 600,
                                      cursor: 'pointer',
                                      display: 'flex',
                                      alignItems: 'center',
                                      gap: 0.5,
                                      '&:hover': { textDecoration: 'underline' },
                                    }}
                                  >
                                    Actions ▾
                                  </Typography>
                                </Box>
                              </Box>

                              {/* Two Column Grid */}
                              <Grid container spacing={2} sx={{ mb: 2 }}>
                                <Grid item xs={12} md={6}>
                                  <Box sx={{ display: 'grid', gridTemplateColumns: '140px 1fr', rowGap: 1, fontSize: '13px' }}>
                                    <Typography sx={{ color: 'text.secondary', fontSize: '12px' }}>Evidence Number:</Typography>
                                    <Typography sx={{ fontWeight: 600, fontSize: '12.5px' }}>{item.evidence_number}</Typography>

                                    <Typography sx={{ color: 'text.secondary', fontSize: '12px' }}>Item Name:</Typography>
                                    <Typography sx={{ fontSize: '12.5px' }}>{item.item_name}</Typography>

                                    <Typography sx={{ color: 'text.secondary', fontSize: '12px' }}>Type:</Typography>
                                    <Typography sx={{ fontSize: '12.5px' }}>{item.type}</Typography>

                                    <Typography sx={{ color: 'text.secondary', fontSize: '12px' }}>Brand / Model:</Typography>
                                    <Typography sx={{ fontSize: '12.5px' }}>{item.device_make || '-'} / {item.device_model || '-'}</Typography>

                                    <Typography sx={{ color: 'text.secondary', fontSize: '12px' }}>Serial Number:</Typography>
                                    <Typography sx={{ fontSize: '12.5px' }}>{item.device_serial || '-'}</Typography>

                                    <Typography sx={{ color: 'text.secondary', fontSize: '12px' }}>File Size:</Typography>
                                    <Typography sx={{ fontSize: '12.5px' }}>{item.size_bytes ? `${item.size_bytes.toLocaleString()} bytes` : '-'}</Typography>

                                    <Typography sx={{ color: 'text.secondary', fontSize: '12px' }}>Acquisition Tool:</Typography>
                                    <Typography sx={{ fontSize: '12.5px' }}>{item.acquisition_tool || '-'}</Typography>
                                  </Box>
                                </Grid>

                                <Grid item xs={12} md={6}>
                                  <Box sx={{ display: 'grid', gridTemplateColumns: '140px 1fr', rowGap: 1, fontSize: '13px' }}>
                                    <Typography sx={{ color: 'text.secondary', fontSize: '12px' }}>Case Number:</Typography>
                                    <Typography sx={{ color: '#5cb867', fontWeight: 600, fontSize: '12.5px' }}>{item.case_number}</Typography>

                                    <Typography sx={{ color: 'text.secondary', fontSize: '12px' }}>Current Custodian:</Typography>
                                    <Typography sx={{ fontSize: '12.5px' }}>{item.current_custodian_name || '-'}</Typography>

                                    <Typography sx={{ color: 'text.secondary', fontSize: '12px' }}>Current Location:</Typography>
                                    <Typography sx={{ fontSize: '12.5px' }}>{item.current_location || '-'}</Typography>

                                    <Typography sx={{ color: 'text.secondary', fontSize: '12px' }}>Collected By:</Typography>
                                    <Typography sx={{ fontSize: '12.5px' }}>{item.collected_by_name || '-'}</Typography>

                                    <Typography sx={{ color: 'text.secondary', fontSize: '12px' }}>Intake Date:</Typography>
                                    <Typography sx={{ fontSize: '12.5px' }}>{item.intake_at ? item.intake_at.slice(0, 19).replace('T', ' ') : '-'}</Typography>

                                    <Typography sx={{ color: 'text.secondary', fontSize: '12px' }}>Retention Until:</Typography>
                                    <Typography sx={{ fontSize: '12.5px' }}>{item.retention_until || 'Indefinite'}</Typography>

                                    <Typography sx={{ color: 'text.secondary', fontSize: '12px' }}>Legal Hold:</Typography>
                                    <Typography sx={{ fontSize: '12.5px', fontWeight: 600, color: item.legal_hold ? 'error.main' : 'text.primary' }}>
                                      {item.legal_hold ? 'ACTIVE LEGAL HOLD' : 'None'}
                                    </Typography>
                                  </Box>
                                </Grid>
                              </Grid>

                              {/* Cryptographic SHA-256 and Integrity Block */}
                              <Box
                                sx={{
                                  p: 1.5,
                                  mb: 2,
                                  borderRadius: '3px',
                                  backgroundColor: (theme) => (theme.palette.mode === 'dark' ? '#1e1e1e' : '#f1f5f9'),
                                  border: '1px solid',
                                  borderColor: 'divider',
                                  display: 'flex',
                                  flexWrap: 'wrap',
                                  alignItems: 'center',
                                  justifyContent: 'space-between',
                                  gap: 1.5,
                                }}
                              >
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                  <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary' }}>
                                    SHA-256:
                                  </Typography>
                                  <HashText hash={item.sha256} />
                                </Box>

                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                                    Integrity:
                                  </Typography>
                                  <StatusChip status={item.integrity_state} />
                                  <Button
                                    size="small"
                                    variant="outlined"
                                    onClick={() => handleVerifyItem(item)}
                                    sx={{ fontSize: '11px', py: 0.2, px: 1 }}
                                  >
                                    Verify Now
                                  </Button>
                                </Box>
                              </Box>

                              {/* Description Block */}
                              {item.description && (
                                <Box sx={{ mb: 2 }}>
                                  <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', display: 'block', mb: 0.5 }}>
                                    DESCRIPTION
                                  </Typography>
                                  <Typography variant="body2" sx={{ fontSize: '12.5px', color: 'text.primary' }}>
                                    {item.description}
                                  </Typography>
                                </Box>
                              )}

                              {/* Compact Tabs */}
                              <Tabs
                                value={activeTab[item.id] || 0}
                                onChange={(_, val) => {
                                  setActiveTab((prev) => ({ ...prev, [item.id]: val }));
                                  loadSubTabData(item, val);
                                }}
                                sx={{
                                  minHeight: 32,
                                  borderBottom: '1px solid',
                                  borderColor: 'divider',
                                  '& .MuiTab-root': {
                                    minHeight: 32,
                                    fontSize: '12px',
                                    fontWeight: 600,
                                    py: 0.5,
                                    px: 2,
                                  },
                                }}
                              >
                                <Tab label="Custody Trail" />
                                <Tab label={`Annotations (${tabAnnotations[item.id]?.length ?? '•'})`} />
                                <Tab label={`Links (${tabLinks[item.id]?.length ?? '•'})`} />
                                <Tab label={`Transfers (${tabTransfers[item.id]?.length ?? '•'})`} />
                              </Tabs>

                              <Box sx={{ pt: 1.5 }}>
                                {/* Tab 0: Custody Trail */}
                                {(activeTab[item.id] || 0) === 0 && (
                                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                                      <Typography variant="body2" sx={{ fontSize: '12px', color: 'text.secondary' }}>
                                        Chronological chain-of-custody recorded and signed. Download complete certified report below:
                                      </Typography>
                                      <Box sx={{ display: 'flex', gap: 1 }}>
                                        <Button
                                          size="small"
                                          variant="outlined"
                                          onClick={() => {
                                            const token = getAccessToken();
                                            window.open(`/api/v1/evidence/${item.id}/custody-report?format=pdf&token=${token}`, '_blank');
                                          }}
                                          sx={{ fontSize: '11px', py: 0.2 }}
                                        >
                                          Custody Report (PDF)
                                        </Button>
                                        <Button
                                          size="small"
                                          variant="outlined"
                                          onClick={() => {
                                            const token = getAccessToken();
                                            window.open(`/api/v1/evidence/${item.id}/custody-report?format=json&token=${token}`, '_blank');
                                          }}
                                          sx={{ fontSize: '11px', py: 0.2 }}
                                        >
                                          Signed JSON
                                        </Button>
                                      </Box>
                                    </Box>
                                  </Box>
                                )}

                                {/* Tab 1: Annotations */}
                                {(activeTab[item.id] || 0) === 1 && (
                                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                                      <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary' }}>
                                        APPEND-ONLY FORENSIC ANNOTATIONS
                                      </Typography>
                                      <Button
                                        size="small"
                                        variant="outlined"
                                        startIcon={<AddIcon sx={{ fontSize: 14 }} />}
                                        onClick={() => {
                                          setActiveAnnotationItem(item);
                                          setAnnotationDialogOpen(true);
                                        }}
                                        sx={{ fontSize: '11px', py: 0.2 }}
                                      >
                                        Add Annotation
                                      </Button>
                                    </Box>

                                    {tabAnnotations[item.id] && tabAnnotations[item.id].length > 0 ? (
                                      tabAnnotations[item.id].map((ann) => (
                                        <Box
                                          key={ann.id}
                                          sx={{
                                            p: 1.5,
                                            backgroundColor: 'background.default',
                                            borderRadius: 1,
                                            border: '1px solid',
                                            borderColor: 'divider',
                                          }}
                                        >
                                          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                                            <Typography variant="caption" sx={{ fontWeight: 600 }}>
                                              {ann.author_name || 'Investigator'}
                                            </Typography>
                                            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                                              {ann.created_at ? ann.created_at.slice(0, 16).replace('T', ' ') : ''}
                                            </Typography>
                                          </Box>
                                          <Typography variant="body2" sx={{ fontSize: '12.5px', mb: 1 }}>
                                            {ann.body}
                                          </Typography>
                                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                                              Body SHA-256:
                                            </Typography>
                                            <HashText hash={ann.body_sha256} truncate />
                                          </Box>
                                        </Box>
                                      ))
                                    ) : (
                                      <Typography variant="body2" sx={{ fontSize: '12px', color: 'text.secondary' }}>
                                        No annotations recorded yet for this evidence item.
                                      </Typography>
                                    )}
                                  </Box>
                                )}

                                {/* Tab 2: Links */}
                                {(activeTab[item.id] || 0) === 2 && (
                                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                                      <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary' }}>
                                        DEFENSIBLE ENTITY LINKS
                                      </Typography>
                                      <Button
                                        size="small"
                                        variant="outlined"
                                        startIcon={<AddIcon sx={{ fontSize: 14 }} />}
                                        onClick={() => {
                                          setActiveLinkItem(item);
                                          setLinkDialogOpen(true);
                                        }}
                                        sx={{ fontSize: '11px', py: 0.2 }}
                                      >
                                        Create Link
                                      </Button>
                                    </Box>

                                    {tabLinks[item.id] && tabLinks[item.id].length > 0 ? (
                                      tabLinks[item.id].map((link) => (
                                        <Box
                                          key={link.id}
                                          sx={{
                                            p: 1.5,
                                            backgroundColor: 'background.default',
                                            borderRadius: 1,
                                            border: '1px solid',
                                            borderColor: 'divider',
                                            display: 'flex',
                                            justifyContent: 'space-between',
                                            alignItems: 'center',
                                          }}
                                        >
                                          <Box>
                                            <Chip label={link.target_type} size="small" sx={{ mr: 1, fontSize: '10px' }} />
                                            <Typography component="span" variant="body2" sx={{ fontWeight: 500, fontSize: '12.5px' }}>
                                              {link.relation}
                                            </Typography>
                                            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.3 }}>
                                              Target ID: {link.target_id}
                                            </Typography>
                                          </Box>
                                          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                                            {link.created_at ? link.created_at.slice(0, 10) : ''}
                                          </Typography>
                                        </Box>
                                      ))
                                    ) : (
                                      <Typography variant="body2" sx={{ fontSize: '12px', color: 'text.secondary' }}>
                                        No linked entities found.
                                      </Typography>
                                    )}
                                  </Box>
                                )}

                                {/* Tab 3: Transfers */}
                                {(activeTab[item.id] || 0) === 3 && (
                                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                                      <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary' }}>
                                        CUSTODY TRANSFER HISTORY
                                      </Typography>
                                      <Button
                                        size="small"
                                        variant="outlined"
                                        onClick={() => handleOpenTransfer(item)}
                                        sx={{ fontSize: '11px', py: 0.2 }}
                                      >
                                        Transfer Custody
                                      </Button>
                                    </Box>

                                    {tabTransfers[item.id] && tabTransfers[item.id].length > 0 ? (
                                      tabTransfers[item.id].map((tr) => (
                                        <Box
                                          key={tr.id}
                                          sx={{
                                            p: 1.5,
                                            backgroundColor: 'background.default',
                                            borderRadius: 1,
                                            border: '1px solid',
                                            borderColor: 'divider',
                                            display: 'flex',
                                            justifyContent: 'space-between',
                                            alignItems: 'center',
                                          }}
                                        >
                                          <Box>
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                                              <StatusChip status={tr.status} />
                                              <Typography variant="body2" sx={{ fontWeight: 500, fontSize: '12.5px' }}>
                                                From: {tr.from_user_name || 'Custodian'} ➔ To: {tr.to_user_name || tr.to_location || 'Recipient'}
                                              </Typography>
                                            </Box>
                                            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                                              Reason: {tr.reason} • Dispatched: {tr.requested_at ? tr.requested_at.slice(0, 16).replace('T', ' ') : ''}
                                            </Typography>
                                          </Box>

                                          {tr.status === 'PENDING_ACK' && (!tr.to_user_id || tr.to_user_id === user?.id) && (
                                            <Button
                                              size="small"
                                              variant="contained"
                                              onClick={() => {
                                                setActiveAckTransfer({
                                                  id: tr.id,
                                                  evidenceNumber: item.evidence_number,
                                                  sendHash: tr.hash_at_send,
                                                });
                                                setAckDialogOpen(true);
                                              }}
                                              sx={{ fontSize: '11px', py: 0.2 }}
                                            >
                                              Acknowledge
                                            </Button>
                                          )}
                                        </Box>
                                      ))
                                    ) : (
                                      <Typography variant="body2" sx={{ fontSize: '12px', color: 'text.secondary' }}>
                                        No transfer records found for this evidence item.
                                      </Typography>
                                    )}
                                  </Box>
                                )}
                              </Box>
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

        {/* Pagination */}
        <TablePagination
          component="div"
          count={total}
          page={page}
          onPageChange={(_, newPage) => setPage(newPage)}
          rowsPerPage={pageSize}
          onRowsPerPageChange={(e) => {
            setPageSize(parseInt(e.target.value, 10));
            setPage(0);
          }}
          rowsPerPageOptions={[25, 50, 100, 500]}
          sx={{ borderTop: '1px solid', borderColor: 'divider' }}
        />
      </Card>

      {/* Print Label Dropdown Menu */}
      <Menu
        anchorEl={printAnchor}
        open={Boolean(printAnchor)}
        onClose={() => setPrintAnchor(null)}
        PaperProps={{ sx: { minWidth: 180, fontSize: '13px' } }}
      >
        <MenuItem onClick={() => handlePrintLabel('standard')} sx={{ fontSize: '13px' }}>
          Standard Label (90×50 mm)
        </MenuItem>
        <MenuItem onClick={() => handlePrintLabel('small')} sx={{ fontSize: '13px' }}>
          Small Tag (50×25 mm)
        </MenuItem>
      </Menu>

      {/* Actions Dropdown Menu */}
      <Menu
        anchorEl={actionAnchor}
        open={Boolean(actionAnchor)}
        onClose={() => setActionAnchor(null)}
        PaperProps={{ sx: { minWidth: 230, fontSize: '13px' } }}
      >
        <MenuItem
          onClick={() => {
            if (selectedActionItem) handleVerifyItem(selectedActionItem);
            setActionAnchor(null);
          }}
          sx={{ fontSize: '13px' }}
        >
          Verify Cryptographic Hash
        </MenuItem>
        <MenuItem
          onClick={() => {
            if (selectedActionItem) handleOpenTransfer(selectedActionItem);
            setActionAnchor(null);
          }}
          sx={{ fontSize: '13px' }}
        >
          Transfer Custody
        </MenuItem>
        <MenuItem
          onClick={() => {
            if (selectedActionItem) {
              setActiveAnnotationItem(selectedActionItem);
              setAnnotationDialogOpen(true);
            }
            setActionAnchor(null);
          }}
          sx={{ fontSize: '13px' }}
        >
          Add Annotation
        </MenuItem>
        <MenuItem
          onClick={() => {
            if (selectedActionItem) {
              setActiveLinkItem(selectedActionItem);
              setLinkDialogOpen(true);
            }
            setActionAnchor(null);
          }}
          sx={{ fontSize: '13px' }}
        >
          Create Defensible Link
        </MenuItem>
        <MenuItem
          onClick={() => {
            if (selectedActionItem) {
              setActiveLegalHoldItem(selectedActionItem);
              setLegalHoldDialogOpen(true);
            }
            setActionAnchor(null);
          }}
          sx={{ fontSize: '13px' }}
        >
          {selectedActionItem?.legal_hold ? 'Release Legal Hold' : 'Place Legal Hold'}
        </MenuItem>
        <MenuItem
          onClick={() => {
            if (selectedActionItem) {
              setActiveExportItem(selectedActionItem);
              setExportDialogOpen(true);
            }
            setActionAnchor(null);
          }}
          sx={{ fontSize: '13px' }}
        >
          Request Export Package
        </MenuItem>
        <MenuItem
          onClick={() => {
            if (selectedActionItem) {
              const token = getAccessToken();
              window.open(`/api/v1/evidence/${selectedActionItem.id}/custody-report?format=pdf&token=${token}`, '_blank');
            }
            setActionAnchor(null);
          }}
          sx={{ fontSize: '13px' }}
        >
          Custody Report (PDF)
        </MenuItem>
        <MenuItem
          onClick={() => {
            if (selectedActionItem) {
              const token = getAccessToken();
              window.open(`/api/v1/evidence/${selectedActionItem.id}/custody-report?format=json&token=${token}`, '_blank');
            }
            setActionAnchor(null);
          }}
          sx={{ fontSize: '13px' }}
        >
          Custody Report (JSON)
        </MenuItem>
        <MenuItem
          onClick={() => {
            if (selectedActionItem) {
              const token = getAccessToken();
              window.open(`/api/v1/evidence/${selectedActionItem.id}/download?token=${token}`, '_blank');
            }
            setActionAnchor(null);
          }}
          sx={{ fontSize: '13px' }}
        >
          Download Working Copy
        </MenuItem>
      </Menu>

      {/* Column Chooser Popover */}
      <Menu
        anchorEl={columnMenuAnchor}
        open={Boolean(columnMenuAnchor)}
        onClose={() => setColumnMenuAnchor(null)}
        PaperProps={{ sx: { p: 1, minWidth: 180 } }}
      >
        <MenuItem
          onClick={() => setVisibleColumns((p) => ({ ...p, sha256: !p.sha256 }))}
          sx={{ fontSize: '13px' }}
        >
          <Checkbox checked={visibleColumns.sha256} size="small" /> SHA-256
        </MenuItem>
        <MenuItem
          onClick={() => setVisibleColumns((p) => ({ ...p, integrity: !p.integrity }))}
          sx={{ fontSize: '13px' }}
        >
          <Checkbox checked={visibleColumns.integrity} size="small" /> Integrity Status
        </MenuItem>
        <MenuItem
          onClick={() => setVisibleColumns((p) => ({ ...p, collectedBy: !p.collectedBy }))}
          sx={{ fontSize: '13px' }}
        >
          <Checkbox checked={visibleColumns.collectedBy} size="small" /> Collected By
        </MenuItem>
        <MenuItem
          onClick={() => setVisibleColumns((p) => ({ ...p, retentionUntil: !p.retentionUntil }))}
          sx={{ fontSize: '13px' }}
        >
          <Checkbox checked={visibleColumns.retentionUntil} size="small" /> Retention Until
        </MenuItem>
      </Menu>

      {/* Filter Popover */}
      <Popover
        anchorEl={filterAnchor}
        open={Boolean(filterAnchor)}
        onClose={() => setFilterAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        PaperProps={{ sx: { p: 2, minWidth: 220 } }}
      >
        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700 }}>
          Filter Evidence
        </Typography>
        <FormControl fullWidth size="small" sx={{ mb: 1.5 }}>
          <Select
            displayEmpty
            value={typeFilter}
            onChange={(e) => {
              setTypeFilter(e.target.value);
              setPage(0);
            }}
          >
            <MenuItem value="">All Types</MenuItem>
            <MenuItem value="FILE">FILE</MenuItem>
            <MenuItem value="DISK_IMAGE">DISK_IMAGE</MenuItem>
            <MenuItem value="MOBILE_EXTRACT">MOBILE_EXTRACT</MenuItem>
            <MenuItem value="CLOUD_EXPORT">CLOUD_EXPORT</MenuItem>
            <MenuItem value="EMAIL">EMAIL</MenuItem>
            <MenuItem value="NETWORK_CAPTURE">NETWORK_CAPTURE</MenuItem>
          </Select>
        </FormControl>

        <FormControl fullWidth size="small" sx={{ mb: 1.5 }}>
          <Select
            displayEmpty
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(0);
            }}
          >
            <MenuItem value="">All Statuses</MenuItem>
            <MenuItem value="REGISTERED">REGISTERED</MenuItem>
            <MenuItem value="IN_CUSTODY">IN_CUSTODY</MenuItem>
            <MenuItem value="TRANSFER_PENDING">TRANSFER_PENDING</MenuItem>
            <MenuItem value="DISPOSED">DISPOSED</MenuItem>
          </Select>
        </FormControl>

        <Button
          fullWidth
          size="small"
          variant="outlined"
          onClick={() => {
            setTypeFilter('');
            setStatusFilter('');
            setFilterAnchor(null);
          }}
        >
          Reset Filters
        </Button>
      </Popover>

      {/* Workflow Dialogs */}
      <CreateEvidenceDialog
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        onCreated={() => {
          fetchEvidence();
        }}
        cases={cases}
      />

      {activeTransferItem && (
        <TransferCustodyDialog
          open={transferDialogOpen}
          onClose={() => {
            setTransferDialogOpen(false);
            setActiveTransferItem(null);
          }}
          onTransferred={() => {
            fetchEvidence();
            if (activeTransferItem) {
              loadSubTabData(activeTransferItem, 3);
            }
          }}
          evidenceId={activeTransferItem.id}
          evidenceNumber={activeTransferItem.evidence_number}
          users={users}
        />
      )}

      {activeAckTransfer && (
        <AcknowledgeTransferDialog
          open={ackDialogOpen}
          onClose={() => {
            setAckDialogOpen(false);
            setActiveAckTransfer(null);
          }}
          onAcknowledged={() => {
            fetchEvidence();
            if (expandedId) {
              const it = items.find((x) => x.id === expandedId);
              if (it) loadSubTabData(it, 3);
            }
          }}
          transferId={activeAckTransfer.id}
          evidenceNumber={activeAckTransfer.evidenceNumber}
          sendHash={activeAckTransfer.sendHash}
        />
      )}

      {activeAnnotationItem && (
        <AddAnnotationDialog
          open={annotationDialogOpen}
          onClose={() => {
            setAnnotationDialogOpen(false);
            setActiveAnnotationItem(null);
          }}
          onAdded={() => {
            if (activeAnnotationItem) {
              setTabAnnotations((prev) => {
                const next = { ...prev };
                delete next[activeAnnotationItem.id];
                return next;
              });
              loadSubTabData(activeAnnotationItem, 1);
            }
          }}
          evidenceId={activeAnnotationItem.id}
          evidenceNumber={activeAnnotationItem.evidence_number}
        />
      )}

      {activeLinkItem && (
        <CreateLinkDialog
          open={linkDialogOpen}
          onClose={() => {
            setLinkDialogOpen(false);
            setActiveLinkItem(null);
          }}
          onLinked={() => {
            if (activeLinkItem) {
              setTabLinks((prev) => {
                const next = { ...prev };
                delete next[activeLinkItem.id];
                return next;
              });
              loadSubTabData(activeLinkItem, 2);
            }
          }}
          evidenceId={activeLinkItem.id}
          evidenceNumber={activeLinkItem.evidence_number}
          caseId={activeLinkItem.case_id}
        />
      )}

      {activeLegalHoldItem && (
        <LegalHoldDialog
          open={legalHoldDialogOpen}
          onClose={() => {
            setLegalHoldDialogOpen(false);
            setActiveLegalHoldItem(null);
          }}
          onCompleted={() => {
            fetchEvidence();
          }}
          evidenceId={activeLegalHoldItem.id}
          evidenceNumber={activeLegalHoldItem.evidence_number}
          isHeld={activeLegalHoldItem.legal_hold}
        />
      )}

      {activeExportItem && (
        <ExportPackageDialog
          open={exportDialogOpen}
          onClose={() => {
            setExportDialogOpen(false);
            setActiveExportItem(null);
          }}
          onRequested={() => {
            fetchEvidence();
          }}
          evidenceId={activeExportItem.id}
          evidenceNumber={activeExportItem.evidence_number}
        />
      )}
    </Box>
  );
};
