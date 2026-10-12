import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, setToken, setUnauthorizedHandler } from "../api/client";
import type { TokenResponse, User } from "../api/types";

const STORAGE_KEY = "fintrace.token";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

// The token lives in sessionStorage: it survives a reload but not closing the tab.
function readStored(): string | null {
  try {
    return sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function store(value: string | null): void {
  try {
    if (value) sessionStorage.setItem(STORAGE_KEY, value);
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Storage blocked: the session simply ends on reload.
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(() => readStored() !== null);

  const logout = useCallback(() => {
    setToken(null);
    store(null);
    setUser(null);
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    const saved = readStored();
    if (!saved) return;
    setToken(saved);
    api<User>("/auth/me")
      .then(setUser)
      .catch(() => logout())
      .finally(() => setLoading(false));
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  const login = useCallback(async (email: string, password: string) => {
    const result = await api<TokenResponse>("/auth/login", { method: "POST", body: { email, password } });
    setToken(result.access_token);
    try {
      const me = await api<User>("/auth/me");
      store(result.access_token);
      setUser(me);
    } catch (err) {
      setToken(null);
      throw err;
    }
  }, []);

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

/** The signed-in user. Only call inside pages behind the login guard. */
export function useUser(): User {
  const { user } = useAuth();
  if (!user) throw new Error("No signed-in user");
  return user;
}
