// Small fetch wrapper. Every API error has the shape
// {"error": {"code", "message", "details", "request_id"}}; it is surfaced as ApiError.

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown[];
  readonly requestId: string | null;

  constructor(status: number, code: string, message: string, details: unknown[] = [], requestId: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

type QueryValue = string | number | boolean | null | undefined | Array<string | number>;
export type Query = Record<string, QueryValue>;

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Query;
}

let token: string | null = null;
let onUnauthorized: (() => void) | null = null;

export function setToken(value: string | null): void {
  token = value;
}

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

export function buildQuery(query: Query = {}): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => params.append(key, String(v)));
    else params.append(key, String(value));
  }
  const text = params.toString();
  return text ? `?${text}` : "";
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(`/api/v1${path}${buildQuery(options.query)}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Cannot reach the FinTrace API. Is the backend running?");
  }

  const text = await response.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    const err = (data as { error?: { code?: string; message?: string; details?: unknown[]; request_id?: string } } | null)?.error;
    if (response.status === 401 && token) onUnauthorized?.();
    throw new ApiError(
      response.status,
      err?.code ?? "HTTP_ERROR",
      err?.message ?? `Request failed with status ${response.status}`,
      err?.details ?? [],
      err?.request_id ?? response.headers.get("X-Request-ID"),
    );
  }
  return data as T;
}
