import { useState, type FormEvent } from "react";
import { Navigate, useLocation } from "react-router";
import { useAuth } from "../auth/AuthContext";
import { BrandMark } from "../components/BrandMark";
import { InlineError } from "../components/States";
import { ThemeToggle } from "../components/ThemeToggle";

export function LoginPage() {
  const { user, login } = useAuth();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  if (user) {
    const from = (location.state as { from?: string } | null)?.from ?? "/";
    return <Navigate to={from} replace />;
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <aside className="login-art">
        <div className="brand">
          <BrandMark />
          <span className="brand-name">FinTrace</span>
          <span className="brand-sub">Investigation desk</span>
        </div>
        <div>
          <blockquote>
            Follow the money. <em>Flag</em> what matters. Let people decide.
          </blockquote>
          <svg className="trace" viewBox="0 0 600 180" aria-hidden="true">
            <path className="trace-base" d="M0 150 L60 138 L110 146 L170 120 L230 132 L290 104 L350 118 L410 90 L470 100 L530 40 L600 52" />
            <path className="trace-live" d="M0 150 L60 138 L110 146 L170 120 L230 132 L290 104 L350 118 L410 90 L470 100 L530 40" />
            <circle className="halo" cx="530" cy="40" r="14" />
            <circle cx="530" cy="40" r="5" />
          </svg>
        </div>
        <p>
          A financial crime detection and investigation prototype. It runs on synthetic data only, and its risk scores are
          triage signals for human review, not proof of wrongdoing.
        </p>
      </aside>
      <div className="login-side">
        <ThemeToggle />
        <form className="login-card" onSubmit={submit}>
          <p className="eyebrow">Analyst sign-in</p>
          <h1>Welcome back</h1>
          <label>
            Email
            <input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label>
            Password
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <InlineError error={error} />
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
          <p className="muted small">
            Accounts are created by an admin with <code>python -m app.cli create-user</code>.
          </p>
        </form>
      </div>
    </div>
  );
}
