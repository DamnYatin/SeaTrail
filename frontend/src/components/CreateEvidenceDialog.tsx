import React, { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  Grid,
  InputLabel,
  LinearProgress,
  MenuItem,
  Select,
  Step,
  StepLabel,
  Stepper,
  TextField,
  Typography,
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';

import { getAccessToken } from '../api/client';
import { hashFileSHA256 } from '../lib/hashing';
import { HashText } from './HashText';

interface CreateEvidenceDialogProps {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
  cases: Array<{ id: string; case_number: string; name: string }>;
}

export const CreateEvidenceDialog: React.FC<CreateEvidenceDialogProps> = ({
  open,
  onClose,
  onCreated,
  cases,
}) => {
  const [activeStep, setActiveStep] = useState(0);

  // Form State
  const [caseId, setCaseId] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [clientHash, setClientHash] = useState<string>('');
  const [isHashing, setIsHashing] = useState(false);
  const [hashProgress, setHashProgress] = useState(0);

  const [evidenceType, setEvidenceType] = useState('FILE');
  const [itemName, setItemName] = useState('');
  const [description, setDescription] = useState('');
  const [sourceDescription, setSourceDescription] = useState('');
  const [deviceMake, setDeviceMake] = useState('');
  const [deviceModel, setDeviceModel] = useState('');
  const [deviceSerial, setDeviceSerial] = useState('');
  const [acquisitionMethod, setAcquisitionMethod] = useState('');
  const [acquisitionTool, setAcquisitionTool] = useState('');
  const [currentLocation, setCurrentLocation] = useState('Evidence Locker A');

  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successInfo, setSuccessInfo] = useState<{ evidenceNumber: string; sha256: string } | null>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      if (!itemName) {
        setItemName(selectedFile.name);
      }
      setIsHashing(true);
      setHashProgress(0);
      try {
        const hash = await hashFileSHA256(selectedFile, (pct) => setHashProgress(pct));
        setClientHash(hash);
      } catch (err: unknown) {
        console.error('Hashing failed', err);
        setErrorMsg('Failed to compute client-side SHA-256 hash');
      } finally {
        setIsHashing(false);
      }
    }
  };

  const handleNext = () => {
    setErrorMsg(null);
    if (activeStep === 0) {
      if (!caseId) {
        setErrorMsg('Please select a case');
        return;
      }
      if (!file) {
        setErrorMsg('Please select a file to ingest');
        return;
      }
      if (isHashing) {
        setErrorMsg('Please wait for cryptographic hash calculation to finish');
        return;
      }
    } else if (activeStep === 1) {
      if (!itemName.trim()) {
        setErrorMsg('Item name is required');
        return;
      }
    }
    setActiveStep((prev) => prev + 1);
  };

  const handleBack = () => {
    setErrorMsg(null);
    setActiveStep((prev) => prev - 1);
  };

  const handleSubmit = async () => {
    if (!caseId || !file) return;
    setSubmitting(true);
    setErrorMsg(null);

    try {
      const metadataObj = {
        type: evidenceType,
        item_name: itemName.trim(),
        description: description.trim() || undefined,
        source_description: sourceDescription.trim() || undefined,
        device_make: deviceMake.trim() || undefined,
        device_model: deviceModel.trim() || undefined,
        device_serial: deviceSerial.trim() || undefined,
        acquisition_method: acquisitionMethod.trim() || undefined,
        acquisition_tool: acquisitionTool.trim() || undefined,
        current_location: currentLocation.trim() || undefined,
      };

      const formData = new FormData();
      formData.append('metadata', JSON.stringify(metadataObj));
      formData.append('file', file);
      if (clientHash) {
        formData.append('client_sha256', clientHash);
      }

      const res = await fetch(`/api/v1/cases/${caseId}/evidence`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${getAccessToken()}`,
        },
        body: formData,
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => null);
        throw new Error(errorData?.error?.message || `Failed to intake evidence (HTTP ${res.status})`);
      }

      const result = await res.json();
      setSuccessInfo({
        evidenceNumber: result.evidence_number,
        sha256: result.sha256,
      });
      onCreated();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Evidence intake failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleResetAndClose = () => {
    setActiveStep(0);
    setCaseId('');
    setFile(null);
    setClientHash('');
    setHashProgress(0);
    setItemName('');
    setDescription('');
    setSourceDescription('');
    setDeviceMake('');
    setDeviceModel('');
    setDeviceSerial('');
    setAcquisitionMethod('');
    setAcquisitionTool('');
    setSuccessInfo(null);
    setErrorMsg(null);
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleResetAndClose} maxWidth="md" fullWidth>
      <DialogTitle sx={{ fontWeight: 600, fontSize: '16px', borderBottom: '1px solid', borderColor: 'divider' }}>
        Register Digital Evidence
      </DialogTitle>

      <DialogContent sx={{ py: 3 }}>
        <Stepper activeStep={activeStep} sx={{ mb: 3 }}>
          <Step>
            <StepLabel>Case & File Intake</StepLabel>
          </Step>
          <Step>
            <StepLabel>Forensic Metadata</StepLabel>
          </Step>
          <Step>
            <StepLabel>Cryptographic Review</StepLabel>
          </Step>
        </Stepper>

        {errorMsg && (
          <Alert severity="error" sx={{ mb: 2, fontSize: '13px' }}>
            {errorMsg}
          </Alert>
        )}

        {successInfo ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <CheckCircleIcon sx={{ fontSize: 52, color: 'success.main', mb: 2 }} />
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 1 }}>
              Evidence Successfully Registered
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
              Assigned Evidence Identifier: <strong>{successInfo.evidenceNumber}</strong>
            </Typography>
            <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 1, p: 1.5, backgroundColor: 'background.default', borderRadius: 1 }}>
              <Typography variant="caption" sx={{ fontWeight: 700 }}>VERIFIED SHA-256:</Typography>
              <HashText hash={successInfo.sha256} />
            </Box>
          </Box>
        ) : (
          <>
            {/* Step 0: Case & File Intake */}
            {activeStep === 0 && (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
                <FormControl fullWidth size="small">
                  <InputLabel>Associated Case</InputLabel>
                  <Select
                    value={caseId}
                    label="Associated Case"
                    onChange={(e) => setCaseId(e.target.value)}
                  >
                    {cases.map((c) => (
                      <MenuItem key={c.id} value={c.id}>
                        {c.case_number} — {c.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                <Box
                  sx={{
                    border: '2px dashed',
                    borderColor: file ? 'primary.main' : 'divider',
                    borderRadius: 1,
                    p: 3,
                    textAlign: 'center',
                    backgroundColor: 'background.default',
                    cursor: 'pointer',
                  }}
                  component="label"
                >
                  <input type="file" hidden onChange={handleFileChange} />
                  <CloudUploadIcon sx={{ fontSize: 40, color: 'primary.main', mb: 1 }} />
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {file ? file.name : 'Click or drag digital extract / file to upload'}
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.5 }}>
                    {file ? `${(file.size / 1024).toFixed(1)} KB` : 'All formats supported (.dd, .raw, .csv, .json, .pcap, .png, etc.)'}
                  </Typography>
                </Box>

                {isHashing && (
                  <Box sx={{ mt: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                      <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        Computing Client SHA-256 (hash-wasm)...
                      </Typography>
                      <Typography variant="caption" sx={{ fontWeight: 700 }}>
                        {hashProgress}%
                      </Typography>
                    </Box>
                    <LinearProgress variant="determinate" value={hashProgress} />
                  </Box>
                )}

                {clientHash && !isHashing && (
                  <Box
                    sx={{
                      p: 1.5,
                      backgroundColor: 'background.default',
                      borderRadius: 1,
                      border: '1px solid',
                      borderColor: 'divider',
                    }}
                  >
                    <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5 }}>
                      Client Pre-Intake Hash (SHA-256):
                    </Typography>
                    <HashText hash={clientHash} />
                  </Box>
                )}
              </Box>
            )}

            {/* Step 1: Forensic Metadata */}
            {activeStep === 1 && (
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Evidence Type</InputLabel>
                    <Select
                      value={evidenceType}
                      label="Evidence Type"
                      onChange={(e) => setEvidenceType(e.target.value)}
                    >
                      <MenuItem value="FILE">File</MenuItem>
                      <MenuItem value="DISK_IMAGE">Disk Image (.dd, .e01, .raw)</MenuItem>
                      <MenuItem value="MOBILE_EXTRACT">Mobile Extract (UFDR/TAR)</MenuItem>
                      <MenuItem value="CLOUD_EXPORT">Cloud Export</MenuItem>
                      <MenuItem value="EMAIL">Email Archive (.eml/.msg)</MenuItem>
                      <MenuItem value="NETWORK_CAPTURE">Network Capture (.pcap)</MenuItem>
                      <MenuItem value="OTHER">Other Forensic Artifact</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>

                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    size="small"
                    required
                    label="Item Name / Title"
                    value={itemName}
                    onChange={(e) => setItemName(e.target.value)}
                  />
                </Grid>

                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    size="small"
                    multiline
                    rows={2}
                    label="Description & Context"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Details about where this artifact was located or recovered..."
                  />
                </Grid>

                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Device Make / Brand"
                    value={deviceMake}
                    onChange={(e) => setDeviceMake(e.target.value)}
                  />
                </Grid>

                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Device Model"
                    value={deviceModel}
                    onChange={(e) => setDeviceModel(e.target.value)}
                  />
                </Grid>

                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Serial Number / IMEI"
                    value={deviceSerial}
                    onChange={(e) => setDeviceSerial(e.target.value)}
                  />
                </Grid>

                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Acquisition Method"
                    value={acquisitionMethod}
                    onChange={(e) => setAcquisitionMethod(e.target.value)}
                    placeholder="Bit-stream image / logical copy"
                  />
                </Grid>

                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Acquisition Tool"
                    value={acquisitionTool}
                    onChange={(e) => setAcquisitionTool(e.target.value)}
                    placeholder="FTK Imager / dd / Cellebrite"
                  />
                </Grid>

                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Physical / Digital Location"
                    value={currentLocation}
                    onChange={(e) => setCurrentLocation(e.target.value)}
                  />
                </Grid>

                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Source Description"
                    value={sourceDescription}
                    onChange={(e) => setSourceDescription(e.target.value)}
                    placeholder="e.g. Seized from suspect's workstation desk in office 402"
                  />
                </Grid>
              </Grid>
            )}

            {/* Step 2: Cryptographic Review */}
            {activeStep === 2 && (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                  Review intake parameters before committing to the immutable evidence registry and audit chain:
                </Typography>

                <Box
                  sx={{
                    p: 2,
                    backgroundColor: 'background.default',
                    borderRadius: 1,
                    border: '1px solid',
                    borderColor: 'divider',
                    display: 'grid',
                    gridTemplateColumns: '160px 1fr',
                    rowGap: 1,
                    fontSize: '13px',
                  }}
                >
                  <Typography sx={{ color: 'text.secondary' }}>File Name:</Typography>
                  <Typography sx={{ fontWeight: 600 }}>{file?.name}</Typography>

                  <Typography sx={{ color: 'text.secondary' }}>File Size:</Typography>
                  <Typography>{file?.size.toLocaleString()} bytes</Typography>

                  <Typography sx={{ color: 'text.secondary' }}>Client SHA-256:</Typography>
                  <HashText hash={clientHash} />

                  <Typography sx={{ color: 'text.secondary' }}>Item Title:</Typography>
                  <Typography sx={{ fontWeight: 600 }}>{itemName}</Typography>

                  <Typography sx={{ color: 'text.secondary' }}>Evidence Type:</Typography>
                  <Typography>{evidenceType}</Typography>

                  <Typography sx={{ color: 'text.secondary' }}>Initial Custody:</Typography>
                  <Typography>{currentLocation}</Typography>
                </Box>

                <Alert severity="info" sx={{ fontSize: '12px' }}>
                  Upon submission, the server will stream the file into S3 object storage with bucket versioning, verify readback SHA-256 against client hash, generate a Crockford base32 evidence ID, and record an append-only transaction in the audit log.
                </Alert>
              </Box>
            )}
          </>
        )}
      </DialogContent>

      <DialogActions sx={{ p: 2, borderTop: '1px solid', borderColor: 'divider' }}>
        {successInfo ? (
          <Button variant="contained" onClick={handleResetAndClose}>
            Done
          </Button>
        ) : (
          <>
            <Button onClick={handleResetAndClose} disabled={submitting}>
              Cancel
            </Button>
            {activeStep > 0 && (
              <Button onClick={handleBack} disabled={submitting}>
                Back
              </Button>
            )}
            {activeStep < 2 ? (
              <Button variant="contained" onClick={handleNext}>
                Next
              </Button>
            ) : (
              <Button
                variant="contained"
                onClick={handleSubmit}
                disabled={submitting}
                startIcon={submitting ? <CircularProgress size={16} color="inherit" /> : null}
              >
                {submitting ? 'Registering...' : 'Commit & Register'}
              </Button>
            )}
          </>
        )}
      </DialogActions>
    </Dialog>
  );
};
