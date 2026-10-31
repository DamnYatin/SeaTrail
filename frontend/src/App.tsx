import { useMemo, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { CssBaseline, ThemeProvider } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { getTheme } from './theme';
import { AuthProvider } from './auth/AuthContext';
import { ProtectedRoute } from './auth/ProtectedRoute';
import { AppShell } from './layout/AppShell';

import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { CasesPage } from './pages/CasesPage';
import { EvidencePage } from './pages/EvidencePage';
import { TransfersPage } from './pages/TransfersPage';
import { ApprovalsPage } from './pages/ApprovalsPage';
import { AuditLogPage } from './pages/AuditLogPage';
import { IntegrityPage } from './pages/IntegrityPage';
import { AlertsPage } from './pages/AlertsPage';
import { ReportsPage } from './pages/ReportsPage';
import { RetentionPage } from './pages/RetentionPage';
import { UsersPage } from './pages/UsersPage';
import { EvidenceLookupPage } from './pages/EvidenceLookupPage';
import { PlaceholderPage } from './pages/PlaceholderPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

export default function App() {
  const [mode, setMode] = useState<'dark' | 'light'>(() => {
    const saved = localStorage.getItem('sealtrail_theme');
    return (saved as 'dark' | 'light') || 'dark';
  });

  const toggleTheme = () => {
    const next = mode === 'dark' ? 'light' : 'dark';
    setMode(next);
    localStorage.setItem('sealtrail_theme', next);
  };

  const theme = useMemo(() => getTheme(mode), [mode]);

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<LoginPage />} />

              <Route element={<ProtectedRoute />}>
                <Route element={<AppShell mode={mode} onToggleTheme={toggleTheme} />}>
                  <Route index element={<Navigate to="/evidence" replace />} />
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/cases" element={<CasesPage />} />
                  <Route path="/evidence" element={<EvidencePage />} />
                  <Route path="/approvals" element={<ApprovalsPage />} />
                  <Route path="/transfers" element={<TransfersPage />} />
                  <Route path="/audit" element={<AuditLogPage />} />
                  <Route path="/integrity" element={<IntegrityPage />} />
                  <Route path="/alerts" element={<AlertsPage />} />
                  <Route path="/reports" element={<ReportsPage />} />
                  <Route path="/holds" element={<RetentionPage />} />
                  <Route path="/retention" element={<RetentionPage />} />
                  <Route path="/users" element={<UsersPage />} />

                  {/* QR Code lookup route */}
                  <Route path="/e/:evidenceNumber" element={<EvidenceLookupPage />} />

                  {/* Additional directories */}
                  <Route path="/locations" element={<PlaceholderPage title="Item Locations" subtitle="Physical & Digital Custody Overview" />} />
                  <Route path="/people" element={<PlaceholderPage title="People Directory" subtitle="Persons of Interest & Contacts" />} />
                  <Route path="/profile" element={<PlaceholderPage title="User Profile" subtitle="Account Settings" />} />
                </Route>
              </Route>

              <Route path="*" element={<Navigate to="/evidence" replace />} />
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
