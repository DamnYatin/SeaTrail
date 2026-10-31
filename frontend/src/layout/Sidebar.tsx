import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Box,
  Collapse,
  Divider,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
} from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import FolderIcon from '@mui/icons-material/Folder';
import Inventory2Icon from '@mui/icons-material/Inventory2';
import PeopleIcon from '@mui/icons-material/People';
import HistoryEduIcon from '@mui/icons-material/HistoryEdu';
import GavelIcon from '@mui/icons-material/Gavel';
import ManageAccountsIcon from '@mui/icons-material/ManageAccounts';
import SettingsIcon from '@mui/icons-material/Settings';
import ExpandLess from '@mui/icons-material/ExpandLess';
import ExpandMore from '@mui/icons-material/ExpandMore';
import Brightness4Icon from '@mui/icons-material/Brightness4';
import Brightness7Icon from '@mui/icons-material/Brightness7';

import { BrandGlyph } from '../components/BrandGlyph';
import { useAuth } from '../auth/AuthContext';

interface SidebarProps {
  mode: 'dark' | 'light';
  onToggleTheme: () => void;
}

interface NavItem {
  label: string;
  path: string;
  allowedRoles?: string[];
}

interface NavGroup {
  id: string;
  label: string;
  icon: React.ReactNode;
  allowedRoles?: string[];
  children: NavItem[];
}

export const Sidebar: React.FC<SidebarProps> = ({ mode, onToggleTheme }) => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({
    dashboard: true,
    cases: true,
    evidence: true,
    people: false,
    audit: true,
    compliance: true,
    users: true,
    settings: false,
  });

  const toggleGroup = (groupId: string) => {
    setOpenGroups((prev) => ({ ...prev, [groupId]: !prev[groupId] }));
  };

  const navGroups: NavGroup[] = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: <DashboardIcon sx={{ fontSize: '18px' }} />,
      children: [{ label: 'Overview', path: '/dashboard' }],
    },
    {
      id: 'cases',
      label: 'Case Management',
      icon: <FolderIcon sx={{ fontSize: '18px' }} />,
      children: [
        { label: 'Cases', path: '/cases' },
        { label: 'Approvals', path: '/approvals', allowedRoles: ['SUPERVISOR', 'ADMIN'] },
      ],
    },
    {
      id: 'evidence',
      label: 'Evidence Management',
      icon: <Inventory2Icon sx={{ fontSize: '18px' }} />,
      children: [
        { label: 'Evidence Items', path: '/evidence' },
        { label: 'Transfers', path: '/transfers' },
        { label: 'Item Locations', path: '/locations' },
      ],
    },
    {
      id: 'people',
      label: 'People',
      icon: <PeopleIcon sx={{ fontSize: '18px' }} />,
      children: [{ label: 'People Directory', path: '/people' }],
    },
    {
      id: 'audit',
      label: 'Audit & Reporting',
      icon: <HistoryEduIcon sx={{ fontSize: '18px' }} />,
      allowedRoles: ['ADMIN', 'SUPERVISOR', 'AUDITOR'],
      children: [
        { label: 'Audit Log', path: '/audit' },
        { label: 'Integrity', path: '/integrity' },
        { label: 'Alerts', path: '/alerts', allowedRoles: ['SUPERVISOR', 'AUDITOR'] },
        { label: 'Reports', path: '/reports' },
      ],
    },
    {
      id: 'compliance',
      label: 'Compliance',
      icon: <GavelIcon sx={{ fontSize: '18px' }} />,
      children: [
        { label: 'Legal Holds', path: '/holds' },
        { label: 'Retention & Disposal', path: '/retention' },
      ],
    },
    {
      id: 'users',
      label: 'User Management',
      icon: <ManageAccountsIcon sx={{ fontSize: '18px' }} />,
      allowedRoles: ['ADMIN'],
      children: [{ label: 'Users', path: '/users' }],
    },
    {
      id: 'settings',
      label: 'Settings',
      icon: <SettingsIcon sx={{ fontSize: '18px' }} />,
      children: [{ label: 'Profile', path: '/profile' }],
    },
  ];

  return (
    <Box
      sx={{
        width: 232,
        flexShrink: 0,
        backgroundColor: mode === 'dark' ? '#1a1a1a' : '#ffffff',
        borderRight: '1px solid',
        borderColor: 'divider',
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
      }}
    >
      {/* Brand Header */}
      <Box
        sx={{
          height: 72,
          padding: '16px',
          borderBottom: '1px solid',
          borderColor: 'divider',
          display: 'flex',
          alignItems: 'center',
        }}
      >
        <BrandGlyph />
      </Box>

      {/* Navigation Groups */}
      <Box sx={{ flexGrow: 1, overflowY: 'auto', py: 1 }}>
        <List component="nav" disablePadding>
          {navGroups.map((group) => {
            if (group.allowedRoles && user && !group.allowedRoles.includes(user.role)) {
              return null;
            }

            const isOpen = openGroups[group.id] ?? false;

            return (
              <React.Fragment key={group.id}>
                <ListItemButton
                  onClick={() => toggleGroup(group.id)}
                  sx={{
                    py: 0.75,
                    px: 2,
                    '&:hover': {
                      backgroundColor: mode === 'dark' ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)',
                    },
                  }}
                >
                  <ListItemIcon sx={{ minWidth: 28, color: 'text.secondary' }}>
                    {group.icon}
                  </ListItemIcon>
                  <ListItemText
                    primary={group.label}
                    primaryTypographyProps={{
                      fontSize: '13px',
                      fontWeight: 600,
                      color: 'text.primary',
                    }}
                  />
                  {isOpen ? (
                    <ExpandLess sx={{ fontSize: '16px', color: 'text.secondary' }} />
                  ) : (
                    <ExpandMore sx={{ fontSize: '16px', color: 'text.secondary' }} />
                  )}
                </ListItemButton>

                <Collapse in={isOpen} timeout="auto" unmountOnExit>
                  <List component="div" disablePadding>
                    {group.children.map((child) => {
                      if (child.allowedRoles && user && !child.allowedRoles.includes(user.role)) {
                        return null;
                      }

                      const isActive = location.pathname === child.path;

                      return (
                        <ListItemButton
                          key={child.path}
                          onClick={() => navigate(child.path)}
                          sx={{
                            pl: 5,
                            py: 0.6,
                            backgroundColor: isActive
                              ? mode === 'dark'
                                ? 'rgba(63, 127, 224, 0.15)'
                                : 'rgba(31, 99, 201, 0.1)'
                              : 'transparent',
                            borderLeft: isActive ? '3px solid' : '3px solid transparent',
                            borderColor: 'primary.main',
                            '&:hover': {
                              backgroundColor: mode === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)',
                            },
                          }}
                        >
                          <ListItemText
                            primary={child.label}
                            primaryTypographyProps={{
                              fontSize: '12.5px',
                              fontWeight: isActive ? 600 : 400,
                              color: isActive ? 'primary.main' : 'text.secondary',
                            }}
                          />
                        </ListItemButton>
                      );
                    })}
                  </List>
                </Collapse>
              </React.Fragment>
            );
          })}
        </List>
      </Box>

      {/* Sidebar Footer */}
      <Divider />
      <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        {/* Sun / Moon Switch */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '11px' }}>
            Theme: {mode === 'dark' ? 'Dark' : 'Light'}
          </Typography>
          <IconButton size="small" onClick={onToggleTheme} sx={{ color: 'text.secondary' }}>
            {mode === 'dark' ? <Brightness7Icon sx={{ fontSize: '16px' }} /> : <Brightness4Icon sx={{ fontSize: '16px' }} />}
          </IconButton>
        </Box>

        {/* User Info Block */}
        {user && (
          <Box>
            <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '13px', lineHeight: 1.2 }}>
              {user.full_name}
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '11px', display: 'block' }}>
              {user.email} ({user.role})
            </Typography>
            <Box sx={{ mt: 0.8, display: 'flex', gap: 1.5 }}>
              <Typography
                component="span"
                onClick={() => navigate('/profile')}
                sx={{
                  color: 'primary.main',
                  fontSize: '12px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  '&:hover': { textDecoration: 'underline' },
                }}
              >
                Profile
              </Typography>
              <Typography
                component="span"
                onClick={logout}
                sx={{
                  color: 'primary.main',
                  fontSize: '12px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  '&:hover': { textDecoration: 'underline' },
                }}
              >
                Log Out
              </Typography>
            </Box>
          </Box>
        )}
      </Box>
    </Box>
  );
};

