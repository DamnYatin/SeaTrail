import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Typography,
} from '@mui/material';
import QrCodeScannerIcon from '@mui/icons-material/QrCodeScanner';
import GppBadIcon from '@mui/icons-material/GppBad';

import { apiClient } from '../api/client';

export const EvidenceLookupPage: React.FC = () => {
  const { evidenceNumber } = useParams<{ evidenceNumber: string }>();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    const lookup = async () => {
      if (!evidenceNumber) {
        setErrorMsg('No evidence identifier provided.');
        setLoading(false);
        return;
      }

      try {
        const { data, error } = await apiClient.GET('/api/v1/evidence/by-number/{evidence_number}', {
          params: { path: { evidence_number: evidenceNumber.toUpperCase().trim() } },
        });

        if (data && !error) {
          // Resolved successfully, navigate to Evidence page with search prefilled
          navigate(`/evidence?q=${encodeURIComponent(data.evidence_number)}`, { replace: true });
        } else {
          const errObj = error as { error?: { message?: string } } | undefined;
          setErrorMsg(errObj?.error?.message || 'Invalid or unverified evidence check character');
        }
      } catch (err: unknown) {
        setErrorMsg(err instanceof Error ? err.message : 'Evidence resolution failed');
      } finally {
        setLoading(false);
      }
    };

    lookup();
  }, [evidenceNumber, navigate]);

  return (
    <Box
      sx={{
        minHeight: '70vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        p: 3,
      }}
    >
      <Card sx={{ maxWidth: 480, width: '100%', p: 2, textAlign: 'center' }}>
        <CardContent>
          <Box sx={{ mb: 2 }}>
            <QrCodeScannerIcon sx={{ fontSize: 48, color: 'primary.main' }} />
          </Box>

          <Typography variant="h6" sx={{ fontWeight: 600, mb: 1 }}>
            Resolving Controlled QR Code
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', mb: 3 }}>
            Target Identifier: <strong>{evidenceNumber}</strong>
          </Typography>

          {loading && (
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1.5 }}>
              <CircularProgress size={28} />
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                Validating Crockford Base32 Modulo-37 Check Character...
              </Typography>
            </Box>
          )}

          {errorMsg && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Alert severity="error" icon={<GppBadIcon />} sx={{ textAlign: 'left' }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                  FORGED OR CORRUPTED LABEL IDENTIFIER
                </Typography>
                <Typography variant="body2" sx={{ fontSize: '13px' }}>
                  {errorMsg}
                </Typography>
              </Alert>

              <Button variant="outlined" onClick={() => navigate('/evidence')}>
                Go to Evidence Items
              </Button>
            </Box>
          )}
        </CardContent>
      </Card>
    </Box>
  );
};
