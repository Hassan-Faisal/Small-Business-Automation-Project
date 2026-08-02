import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import axios from "axios";

import { api } from "../api/client";
import type { AdminProfile, AuthResponse } from "../types/admin";
import { isAdminProfile, isAuthResponse } from "../utils/validation";

interface AuthContextValue {
  user: AdminProfile | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  clearSession: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AdminProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    api.get<AdminProfile>("/admin/auth/me")
      .then((response) => {
        if (!isAdminProfile(response.data)) throw new Error("Unexpected session response");
        if (mounted) setUser(response.data);
      })
      .catch(() => {
        if (mounted) setUser(null);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => { mounted = false; };
  }, []);

  const value = useMemo<AuthContextValue>(() => ({
    user,
    loading,
    login: async (email, password) => {
      const response = await api.post<AuthResponse>("/admin/auth/login", { email, password });
      if (!isAuthResponse(response.data)) throw new Error("Unexpected login response");
      setUser(response.data.admin);
    },
    logout: async () => {
      try {
        await api.post("/admin/auth/logout");
      } finally {
        setUser(null);
      }
    },
    clearSession: () => setUser(null),
  }), [loading, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}

export function isUnauthorized(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 401;
}