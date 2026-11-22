import { jwtDecode } from "jwt-decode";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, setAccessToken, setUnauthorizedHandler } from "../api/client";
import type { CurrentUser } from "./roles";

interface LoginResponse {
  access_token: string;
  expires_in: number;
  user: CurrentUser;
}

interface AuthState {
  token: string | null;
  user: CurrentUser | null;
  login: (email: string, password: string) => Promise<CurrentUser>;
  logout: () => void;
}

const STORAGE_KEY = "retail.session";
const AuthContext = createContext<AuthState | null>(null);

function loadSession(): { token: string; user: CurrentUser } | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw) as { token: string; user: CurrentUser };
    const { exp } = jwtDecode<{ exp: number }>(session.token);
    if (exp * 1000 <= Date.now()) return null;
    return session;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState(() => {
    const s = loadSession();
    setAccessToken(s?.token ?? null);
    return s;
  });

  const logout = useCallback(() => {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      /* storage unavailable */
    }
    setAccessToken(null);
    setSession(null);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api<LoginResponse>("/admin/auth/login", { method: "POST", json: { email, password } });
    const next = { token: res.access_token, user: res.user };
    setAccessToken(next.token);
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      /* storage unavailable: session lasts until reload */
    }
    setSession(next);
    return res.user;
  }, []);

  // Any 401 from the API (expired or invalid token) logs the user out.
  useEffect(() => {
    setUnauthorizedHandler(logout);
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  // Log out when the token expires.
  useEffect(() => {
    if (!session) return;
    const { exp } = jwtDecode<{ exp: number }>(session.token);
    const timer = window.setTimeout(logout, Math.max(0, exp * 1000 - Date.now()));
    return () => window.clearTimeout(timer);
  }, [session, logout]);

  const value = useMemo<AuthState>(
    () => ({ token: session?.token ?? null, user: session?.user ?? null, login, logout }),
    [session, login, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
