import { ApiError } from "../api/client";

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="state" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      {label}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const apiError = error instanceof ApiError ? error : null;
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div className="state state-error" role="alert">
      <strong>{apiError?.code === "MODEL_NOT_AVAILABLE" ? "No model is active" : "Could not load this"}</strong>
      <p>{message}</p>
      {apiError?.requestId && <p className="muted small">Request ID: {apiError.requestId}</p>}
      {onRetry && (
        <button type="button" className="btn" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="state state-empty">
      <strong>{title}</strong>
      {children && <div className="muted">{children}</div>}
    </div>
  );
}

export function InlineError({ error }: { error: unknown }) {
  if (!error) return null;
  const message = error instanceof Error ? error.message : String(error);
  return (
    <p className="inline-error" role="alert">
      {message}
    </p>
  );
}
