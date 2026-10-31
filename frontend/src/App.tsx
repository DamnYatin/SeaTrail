import { useMemo, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { CssBaseline, ThemeProvider } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { getTheme } from './theme';
import { AuthProvider } from './auth/AuthContext';
import { ProtectedRoute } from './auth/ProtectedRoute';
import { AppShell } from './layout/AppShell';
import { LoginPage } from './pages/LoginPage';
import { EvidencePage } from './pages/EvidencePage';
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
                  <Route path="/evidence" element={<EvidencePage />} />
                  <Route path="/dashboard" element={<PlaceholderPage title="Dashboard" subtitle="System Status and Oversight" />} />
                  <Route path="/cases" element={<PlaceholderPage title="Cases" subtitle="Active Investigations" />} />
                  <Route path="/approvals" element={<PlaceholderPage title="Approvals" subtitle="Dual Authorization Queue" />} />
                  <Route path="/transfers" element={<PlaceholderPage title="Transfers" subtitle="Custody Transfers" />} />
                  <Route path="/locations" element={<PlaceholderPage title="Item Locations" subtitle="Physical & Digital Custody" />} />
                  <Route path="/people" element={<PlaceholderPage title="People Directory" subtitle="Persons of Interest & Contacts" />} />
                  <Route path="/audit" element={<PlaceholderPage title="Audit Log" subtitle="Append-only Hash Chained Journal" />} />
                  <Route path="/integrity" element={<PlaceholderPage title="Integrity Sweep" subtitle="Continuous Three-Way Verification" />} />
                  <Route path="/alerts" element={<PlaceholderPage title="Security Alerts" subtitle="Rule-based Anomaly Flags" />} />
                  <Route path="/reports" element={<PlaceholderPage title="Reports" subtitle="Signed Defensible Custody Reports" />} />
                  <Route path="/holds" element={<PlaceholderPage title="Legal Holds" subtitle="Active Statutory Preservation Orders" />} />
                  <Route path="/retention" element={<PlaceholderPage title="Retention & Disposal" subtitle="Lifecycle Policies & Tombstones" />} />
                  <Route path="/users" element={<PlaceholderPage title="User Management" subtitle="Access Control & Personnel" />} />
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
