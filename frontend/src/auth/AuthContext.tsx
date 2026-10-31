import React, { createContext, useContext, useEffect, useState } from 'react';
import { apiClient, setAccessToken } from '../api/client';

export interface UserInfo {
  id: string;
  email: string;
  full_name: string;
  role: 'ADMIN' | 'SUPERVISOR' | 'INVESTIGATOR' | 'CUSTODIAN' | 'AUDITOR';
  is_active: boolean;
}

interface AuthContextType {
  user: UserInfo | null;
  loading: boolean;
  login: (email: string, pass: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchMe = async () => {
    try {
      const { data, error } = await apiClient.GET('/api/v1/auth/me');
      if (data && !error) {
        setUser(data as UserInfo);
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    }
  };

  const refresh = async () => {
    try {
      const { data, error } = await apiClient.POST('/api/v1/auth/refresh');
      if (data && !error) {
        setAccessToken(data.access_token);
        await fetchMe();
      } else {
        setAccessToken(null);
        setUser(null);
      }
    } catch {
      setAccessToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const login = async (email: string, password: string) => {
    const { data, error } = await apiClient.POST('/api/v1/auth/login', {
      body: { email, password },
    });
    if (error || !data) {
      const errObj = error as { error?: { message?: string } } | undefined;
      throw new Error(errObj?.error?.message || 'Login failed');
    }
    setAccessToken(data.access_token);
    setUser({
      id: data.user_id,
      email: data.email,
      full_name: data.full_name,
      role: data.role,
      is_active: true,
    });
  };

  const logout = async () => {
    try {
      await apiClient.POST('/api/v1/auth/logout');
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

