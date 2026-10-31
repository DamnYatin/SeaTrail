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
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';

import { apiClient } from '../api/client';
import { useAuth } from '../auth/AuthContext';

interface UserRow {
  id: string;
  email: string;
  full_name: string;
  role: 'ADMIN' | 'SUPERVISOR' | 'INVESTIGATOR' | 'CUSTODIAN' | 'AUDITOR';
  is_active: boolean;
  failed_login_count: number;
  last_login_at?: string;
  created_at: string;
}

export const UsersPage: React.FC = () => {
  const { user } = useAuth();
  const [users, setUsers] = useState<UserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Create User Dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [newName, setNewName] = useState('');
  const [newRole, setNewRole] = useState<'ADMIN' | 'SUPERVISOR' | 'INVESTIGATOR' | 'CUSTODIAN' | 'AUDITOR'>('INVESTIGATOR');
  const [newPassword, setNewPassword] = useState('');
  const [creating, setCreating] = useState(false);

  const fetchUsers = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const { data, error } = await apiClient.GET('/api/v1/users');
      if (data && !error) {
        setUsers(data as unknown as UserRow[]);
      } else {
        const errObj = error as { error?: { message?: string } } | undefined;
        setErrorMsg(errObj?.error?.message || 'Failed to load user directory (Admin privileges required)');
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleToggleActive = async (u: UserRow) => {
    try {
      await apiClient.PATCH('/api/v1/users/{user_id}', {
        params: { path: { user_id: u.id } },
        body: { is_active: !u.is_active },
      });
      fetchUsers();
    } catch (e) {
      console.error('Failed to update user', e);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      const { data, error } = await apiClient.POST('/api/v1/users', {
        body: {
          email: newEmail.trim(),
          full_name: newName.trim(),
          role: newRole,
          password: newPassword,
        },
      });

      if (error || !data) {
        const errObj = error as { error?: { message?: string } } | undefined;
        throw new Error(errObj?.error?.message || 'Failed to create user account');
      }

      setCreateOpen(false);
      setNewEmail('');
      setNewName('');
      setNewPassword('');
      fetchUsers();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'User creation failed');
    } finally {
      setCreating(false);
    }
  };

  return (
    <Box sx={{ p: 3, maxWidth: 1600, mx: 'auto' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 600, mb: 0.5 }}>
            User Account Management
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            Role-based access control administration and personnel directory
          </Typography>
        </Box>

        {user?.role === 'ADMIN' && (
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setCreateOpen(true)}
            sx={{ fontWeight: 600, fontSize: '13px' }}
          >
            Create User
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
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Full Name</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Email Address</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Role</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Status</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px' }}>Last Login (UTC)</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '12px', textAlign: 'right' }}>Active Toggle</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={6} sx={{ textAlign: 'center', py: 4 }}>
                    <CircularProgress size={24} />
                  </TableCell>
                </TableRow>
              ) : users.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} sx={{ textAlign: 'center', py: 4, color: 'text.secondary' }}>
                    No users accessible or unauthorized.
                  </TableCell>
                </TableRow>
              ) : (
                users.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell sx={{ fontWeight: 600 }}>{u.full_name}</TableCell>
                    <TableCell>{u.email}</TableCell>
                    <TableCell>
                      <Chip label={u.role} size="small" sx={{ fontSize: '11px', fontWeight: 600 }} />
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={u.is_active ? 'ACTIVE' : 'DEACTIVATED'}
                        size="small"
                        color={u.is_active ? 'success' : 'default'}
                        sx={{ fontSize: '10px', height: 20 }}
                      />
                    </TableCell>
                    <TableCell sx={{ color: 'text.secondary', fontSize: '12px' }}>
                      {u.last_login_at ? u.last_login_at.slice(0, 16).replace('T', ' ') : 'Never'}
                    </TableCell>
                    <TableCell sx={{ textAlign: 'right' }}>
                      {user?.role === 'ADMIN' && u.id !== user.id && (
                        <Switch
                          size="small"
                          checked={u.is_active}
                          onChange={() => handleToggleActive(u)}
                        />
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>

      {/* Create User Dialog */}
      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
        <Box component="form" onSubmit={handleCreateUser}>
          <DialogTitle sx={{ fontWeight: 600, fontSize: '16px' }}>
            Register Personnel Account
          </DialogTitle>
          <DialogContent sx={{ py: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <TextField
              fullWidth
              required
              size="small"
              label="Full Name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
            <TextField
              fullWidth
              required
              type="email"
              size="small"
              label="Email Address"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
            />
            <FormControl fullWidth size="small">
              <InputLabel>System Role</InputLabel>
              <Select
                value={newRole}
                label="System Role"
                onChange={(e) => setNewRole(e.target.value as 'ADMIN' | 'SUPERVISOR' | 'INVESTIGATOR' | 'CUSTODIAN' | 'AUDITOR')}
              >
                <MenuItem value="ADMIN">ADMIN (System Administrator)</MenuItem>
                <MenuItem value="SUPERVISOR">SUPERVISOR (Case Supervisor)</MenuItem>
                <MenuItem value="INVESTIGATOR">INVESTIGATOR (Lead / Assigned Detective)</MenuItem>
                <MenuItem value="CUSTODIAN">CUSTODIAN (Evidence Vault Officer)</MenuItem>
                <MenuItem value="AUDITOR">AUDITOR (Independent Inspector)</MenuItem>
              </Select>
            </FormControl>
            <TextField
              fullWidth
              required
              type="password"
              size="small"
              label="Initial Password (min 12 chars)"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
          </DialogContent>
          <DialogActions sx={{ p: 2 }}>
            <Button onClick={() => setCreateOpen(false)} disabled={creating}>
              Cancel
            </Button>
            <Button type="submit" variant="contained" disabled={creating}>
              {creating ? 'Creating...' : 'Create Account'}
            </Button>
          </DialogActions>
        </Box>
      </Dialog>
    </Box>
  );
};
