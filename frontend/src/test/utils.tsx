import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";
import { setToken } from "../api/client";
import type { User } from "../api/types";
import { AuthProvider } from "../auth/AuthContext";

export const analyst: User = {
  id: 1,
  email: "ana@example.com",
  full_name: "Ana Analyst",
  role: "analyst",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  last_login_at: null,
};

type Handler = (url: URL, init: RequestInit) => { status?: number; body?: unknown };

/** Replace fetch with a router of fake API responses. Unknown paths answer 404. */
export function mockApi(routes: Record<string, Handler | object>, user: User | null = analyst) {
  const calls: { method: string; path: string; body: unknown }[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(input), "http://localhost");
    const path = url.pathname.replace("/api/v1", "");
    const method = init.method ?? "GET";
    calls.push({ method, path, body: init.body ? JSON.parse(String(init.body)) : undefined });
    let result: { status?: number; body?: unknown };
    if (path === "/auth/me" && user) result = { body: user };
    else {
      const route = routes[`${method} ${path}`] ?? routes[path];
      if (route === undefined) result = { status: 404, body: { error: { code: "NOT_FOUND", message: `No mock for ${method} ${path}`, details: [], request_id: "t" } } };
      else result = typeof route === "function" ? (route as Handler)(url, init) : { body: route };
    }
    return new Response(result.body === undefined ? "" : JSON.stringify(result.body), {
      status: result.status ?? 200,
      headers: { "Content-Type": "application/json", "X-Request-ID": "req-test" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return { fetchMock, calls };
}

export function renderPage(ui: ReactElement, { route = "/", signedIn = true } = {}) {
  if (signedIn) {
    sessionStorage.setItem("fintrace.token", "test-token");
  } else {
    sessionStorage.clear();
    setToken(null);
  }
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <AuthProvider>{ui}</AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
