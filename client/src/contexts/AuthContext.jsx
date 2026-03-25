import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiFetch } from '../utils/api';
import { trackEvent } from '../utils/analytics';

const AuthContext = createContext(null);

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check for existing session on mount
  useEffect(() => {
    apiFetch('/api/auth/me')
      .then((resp) => (resp.ok ? resp.json() : null))
      .then((data) => {
        if (data) setUser(data);
      })
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, []);

  const sendCode = useCallback(async (email) => {
    const resp = await apiFetch('/api/auth/send-code', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || 'Failed to send code');
    return data;
  }, []);

  const verifyCode = useCallback(async (email, code) => {
    const resp = await apiFetch('/api/auth/verify-code', {
      method: 'POST',
      body: JSON.stringify({ email, code }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || 'Verification failed');
    setUser(data.user);
    trackEvent('user_login');
    return data.user;
  }, []);

  const logout = useCallback(async () => {
    await apiFetch('/api/auth/logout', { method: 'POST' });
    setUser(null);
  }, []);

  const updateProfile = useCallback(async (updates) => {
    const resp = await apiFetch('/api/auth/me', {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || 'Update failed');
    setUser(data);
    if (updates.vehicle_type) {
      trackEvent('vehicle_type_changed', { vehicle_type: updates.vehicle_type });
    }
    return data;
  }, []);

  const value = {
    user,
    isAuthenticated: !!user,
    isLoading,
    sendCode,
    verifyCode,
    logout,
    updateProfile,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
