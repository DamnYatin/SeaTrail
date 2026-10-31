import React, { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CircularProgress,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Typography,
} from '@mui/material';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import CodeIcon from '@mui/icons-material/Code';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import VerifiedIcon from '@mui/icons-material/Verified';
import GppBadIcon from '@mui/icons-material/GppBad';
import AssignmentTurnedInIcon from '@mui/icons-material/AssignmentTurnedIn';

import { apiClient, getAccessToken } from '../api/client';

interface EvidenceItemOption {
  id: string;
  evidence_number: string;
  item_name: string;
  case_number: string;
}

export const ReportsPage: React.FC = () => {
  const [evidenceList, setEvidenceList] = useState<EvidenceItemOption[]>([]);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState('');
  const [loading, setLoading] = useState(true);

  // Verification state
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<{
    verified: boolean;
    evidence_number?: string;
    verified_at?: string;
    error?: string;
    computed_hash?: string;
    report_hash?: string;
  } | null>(null);

  useEffect(() => {
    const fetchEvidence = async () => {
      try {
        const { data } = await apiClient.GET('/api/v1/evidence', {
          params: { query: { page_size: 100 } },
        });
        if (data && 'items' in data) {
          setEvidenceList(
            (data.items as unknown as Array<{ id: string; evidence_number: string; item_name: string; case_number: string }>).map((it) => ({
              id: it.id,
              evidence_number: it.evidence_number,
              item_name: it.item_name,
              case_number: it.case_number,
            }))
          );
        }
      } catch (e) {
        console.error('Failed to load evidence items', e);
      } finally {
        setLoading(false);
      }
    };
    fetchEvidence();
  }, []);

  const handleDownloadPdf = () => {
    if (!selectedEvidenceId) return;
    const token = getAccessToken();
    window.open(`/api/v1/evidence/${selectedEvidenceId}/custody-report?format=pdf&token=${token}`, '_blank');
  };

  const handleDownloadJson = () => {
    if (!selectedEvidenceId) return;
    const token = getAccessToken();
    window.open(`/api/v1/evidence/${selectedEvidenceId}/custody-report?format=json&token=${token}`, '_blank');
  };

  const handleUploadReportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setVerifying(true);
      setVerifyResult(null);
      try {
        const text = await file.text();
        const reportJson = JSON.parse(text);

        const { data, error } = await apiClient.POST('/api/v1/reports/verify', {
          body: { report: reportJson },
        });

        if (data && !error) {
          setVerifyResult(data as unknown as { verified: boolean; evidence_number?: string; verified_at?: string; error?: string });
        } else {
          const errObj = error as { error?: { message?: string } } | undefined;
          setVerifyResult({
            verified: false,
            error: errObj?.error?.message || 'Report verification failed',
          });
        }
      } catch (err: unknown) {
        setVerifyResult({
          verified: false,
          error: err instanceof Error ? err.message : 'Invalid JSON file format',
        });
      } finally {
        setVerifying(false);
      }
    }
  };

  return (
    <Box sx={{ p: 3, maxWidth: 1600, mx: 'auto' }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 600, mb: 0.5 }}>
          Chain-of-Custody Reports & Verification
        </Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          Generate court-defensible certified custody logs and independently verify previously issued report packages
        </Typography>
      </Box>

      <Grid container spacing={3}>
        {/* Card 1: Generate Report */}
        <Grid item xs={12} md={6}>
          <Card sx={{ p: 3, border: '1px solid', borderColor: 'divider', height: '100%' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
              <AssignmentTurnedInIcon sx={{ color: 'primary.main', fontSize: 28 }} />
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                Generate Defensible Custody Report
              </Typography>
            </Box>

            <Typography variant="body2" sx={{ color: 'text.secondary', mb: 3 }}>
              Produces a chronological custody audit statement with complete chain events, QR verification code, SHA-256 digests, and statutory Section 63 BSA compliance markings.
            </Typography>

            <FormControl fullWidth size="small" sx={{ mb: 3 }}>
              <InputLabel>Select Evidence Item</InputLabel>
              <Select
                value={selectedEvidenceId}
                label="Select Evidence Item"
                onChange={(e) => setSelectedEvidenceId(e.target.value)}
              >
                {loading ? (
                  <MenuItem value="">Loading evidence...</MenuItem>
                ) : (
                  evidenceList.map((ev) => (
                    <MenuItem key={ev.id} value={ev.id}>
                      {ev.evidence_number} — {ev.item_name} ({ev.case_number})
                    </MenuItem>
                  ))
                )}
              </Select>
            </FormControl>

            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              <Button
                variant="contained"
                startIcon={<PictureAsPdfIcon />}
                disabled={!selectedEvidenceId}
                onClick={handleDownloadPdf}
                sx={{ px: 2.5 }}
              >
                Download PDF Report
              </Button>
              <Button
                variant="outlined"
                startIcon={<CodeIcon />}
                disabled={!selectedEvidenceId}
                onClick={handleDownloadJson}
              >
                Signed JSON Package
              </Button>
            </Box>
          </Card>
        </Grid>

        {/* Card 2: Offline / Independent Report Verifier */}
        <Grid item xs={12} md={6}>
          <Card sx={{ p: 3, border: '1px solid', borderColor: 'divider', height: '100%' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
              <VerifiedIcon sx={{ color: '#5cb867', fontSize: 28 }} />
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                Cryptographic Report Verifier
              </Typography>
            </Box>

            <Typography variant="body2" sx={{ color: 'text.secondary', mb: 3 }}>
              Upload any previously issued JSON custody report to verify its cryptographic digital seal, check for retroactive database tampering, and inspect hash continuity.
            </Typography>

            <Box
              sx={{
                border: '2px dashed',
                borderColor: 'divider',
                borderRadius: 1,
                p: 3,
                textAlign: 'center',
                backgroundColor: 'background.default',
                cursor: 'pointer',
                mb: 3,
              }}
              component="label"
            >
              <input type="file" accept=".json" hidden onChange={handleUploadReportFile} />
              <CloudUploadIcon sx={{ fontSize: 36, color: 'primary.main', mb: 1 }} />
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {verifying ? 'Verifying report signature...' : 'Select or drop custody_report.json'}
              </Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                Instant offline cryptographic verification
              </Typography>
            </Box>

            {verifying && <CircularProgress size={24} sx={{ display: 'block', mx: 'auto' }} />}

            {verifyResult && (
              <Alert
                severity={verifyResult.verified ? 'success' : 'error'}
                icon={verifyResult.verified ? <VerifiedIcon /> : <GppBadIcon />}
              >
                <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                  {verifyResult.verified
                    ? `AUTHENTIC SEALTRAIL REPORT: ${verifyResult.evidence_number}`
                    : 'INVALID OR TAMPERED REPORT'}
                </Typography>
                <Typography variant="body2" sx={{ fontSize: '13px', mt: 0.5 }}>
                  {verifyResult.verified
                    ? 'Cryptographic signature verified against Ed25519 public checkpoint. The hash chain is authentic and untampered.'
                    : verifyResult.error || 'The cryptographic digest in this report does not match the ledger contents.'}
                </Typography>
              </Alert>
            )}
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};
