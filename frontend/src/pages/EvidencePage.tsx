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

export const EvidencePage: React.FC = () => {
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
    <Box>
      {/* Page Title & Stats */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="h1" sx={{ color: 'text.primary', fontWeight: 500 }}>
          Evidence Items
        </Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '13px' }}>
          Total {total} items registered across active workspace
        </Typography>
      </Box>

      {/* Main Table Card */}
      <Card sx={{ border: '1px solid', borderColor: 'divider', boxShadow: 'none' }}>
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
              placeholder="Search Evidence"
              variant="standard"
              size="small"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setPage(0);
              }}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon sx={{ fontSize: '16px', color: 'text.secondary' }} />
                  </InputAdornment>
                ),
                sx: { fontSize: '13px', pb: 0.3 },
              }}
              sx={{ width: 180, ml: 1 }}
            />
          </Box>
        </Box>

        {/* Data Table */}
        <TableContainer>
          <Table size="small" sx={{ minWidth: 1000 }}>
            <TableHead>
              <TableRow>
                <TableCell sx={{ width: 40 }} />
                <TableCell>Evidence Number</TableCell>
                <TableCell>Case Number</TableCell>
                <TableCell>Case Name</TableCell>
                <TableCell>Intake Date</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Brand</TableCell>
                <TableCell>Item Name</TableCell>
                <TableCell>Progress</TableCell>
                <TableCell>Current Location</TableCell>
                {visibleColumns.sha256 && <TableCell>SHA-256</TableCell>}
                {visibleColumns.integrity && <TableCell>Integrity</TableCell>}
                {visibleColumns.collectedBy && <TableCell>Collected By</TableCell>}
                {visibleColumns.retentionUntil && <TableCell>Retention Until</TableCell>}
              </TableRow>
            </TableHead>

            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={14} sx={{ textAlign: 'center', py: 4 }}>
                    <CircularProgress size={28} />
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
                                onChange={(_, val) => setActiveTab((prev) => ({ ...prev, [item.id]: val }))}
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
                                <Tab label="Annotations" />
                                <Tab label="Links" />
                                <Tab label="Transfers" />
                              </Tabs>

                              <Box sx={{ pt: 1.5 }}>
                                {(activeTab[item.id] || 0) === 0 && (
                                  <Typography variant="body2" sx={{ fontSize: '12px', color: 'text.secondary' }}>
                                    Chronological chain-of-custody recorded and signed. Download custody report from Actions menu.
                                  </Typography>
                                )}
                                {(activeTab[item.id] || 0) === 1 && (
                                  <Typography variant="body2" sx={{ fontSize: '12px', color: 'text.secondary' }}>
                                    Append-only annotations linked to this evidence record.
                                  </Typography>
                                )}
                                {(activeTab[item.id] || 0) === 2 && (
                                  <Typography variant="body2" sx={{ fontSize: '12px', color: 'text.secondary' }}>
                                    Defensible links to persons, events, and timeline notes.
                                  </Typography>
                                )}
                                {(activeTab[item.id] || 0) === 3 && (
                                  <Typography variant="body2" sx={{ fontSize: '12px', color: 'text.secondary' }}>
                                    Past and pending custody transfer history.
                                  </Typography>
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
        PaperProps={{ sx: { minWidth: 220, fontSize: '13px' } }}
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
    </Box>
  );
};

