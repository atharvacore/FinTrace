import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../api/client";
import type { Overview, RiskDistribution } from "../api/types";
import { Histogram } from "../components/Histogram";
import { Empty, ErrorState, Loading } from "../components/States";
import { formatInt, formatPct, formatScore, humanize } from "../lib/format";

function Stat({ label, value, to, hint }: { label: string; value: string; to?: string; hint?: string }) {
  const body = (
    <>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {hint && <div className="muted small">{hint}</div>}
    </>
  );
  return to ? (
    <Link to={to} className="card stat stat-link">
      {body}
    </Link>
  ) : (
    <div className="card stat">{body}</div>
  );
}

function Breakdown({ title, counts, linkFor }: { title: string; counts: Record<string, number>; linkFor?: (key: string) => string }) {
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  return (
    <section className="card">
      <h2>{title}</h2>
      {total === 0 ? (
        <p className="muted">None yet.</p>
      ) : (
        <ul className="bars">
          {Object.entries(counts).map(([key, n]) => (
            <li key={key}>
              <span className="bars-label">{linkFor && n > 0 ? <Link to={linkFor(key)}>{humanize(key)}</Link> : humanize(key)}</span>
              <span className="bars-track">
                <span className={`bars-fill fill-${key}`} style={{ width: `${(100 * n) / total}%` }} />
              </span>
              <span className="bars-value">{formatInt(n)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

const PRIORITIES = ["critical", "high", "medium", "low"] as const;

/** Open alerts as one segmented strip, worst first, so the mix is visible at a glance. */
function PriorityStrip({ counts }: { counts: Record<string, number> }) {
  const total = PRIORITIES.reduce((sum, p) => sum + (counts[p] ?? 0), 0);
  return (
    <div>
      {total > 0 && (
        <div className="strip" aria-hidden="true">
          {PRIORITIES.filter((p) => counts[p]).map((p) => (
            <span key={p} className={`fill-${p}`} style={{ flexGrow: counts[p] }} />
          ))}
        </div>
      )}
      <ul className="legend" aria-label="Open alerts by priority" style={{ marginTop: "0.8rem" }}>
        {PRIORITIES.map((p) => (
          <li key={p}>
            <span className={`swatch fill-${p}`} aria-hidden="true" />
            {counts[p] ? <Link to={`/alerts?priority=${p}`}>{humanize(p)}</Link> : humanize(p)}
            <span className="count">{formatInt(counts[p] ?? 0)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function OverviewPage() {
  const overview = useQuery({ queryKey: ["metrics", "overview"], queryFn: () => api<Overview>("/metrics/overview") });
  const dist = useQuery({
    queryKey: ["metrics", "risk-distribution"],
    queryFn: () => api<RiskDistribution>("/metrics/risk-distribution"),
    enabled: !!overview.data?.active_model,
  });

  if (overview.isPending) return <Loading />;
  if (overview.isError) return <ErrorState error={overview.error} onRetry={() => overview.refetch()} />;
  const o = overview.data;
  const lc = o.label_check;

  return (
    <div className="page">
      <header className="page-head">
        <p className="eyebrow">Investigation desk · {new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}</p>
        <h1>Overview</h1>
        <p className="muted">{o.notice}</p>
      </header>

      {o.transactions_total === 0 && (
        <Empty title="No transactions yet">
          Import the synthetic sample with <code>python -m app.cli import-csv ../data/sample/synthetic_transactions.csv</code>.
        </Empty>
      )}
      {o.transactions_total > 0 && !o.active_model && (
        <Empty title="No model is active">
          Transactions cannot be scored until an admin registers a model (<code>python -m app.cli sync-model</code>).
        </Empty>
      )}

      <section className="hero">
        <div className="hero-panel">
          <div>
            <div className="stat-value">
              {formatInt((o.alerts_by_status.open ?? 0) + (o.alerts_by_status.in_review ?? 0) + (o.alerts_by_status.escalated ?? 0))}
            </div>
            <div className="stat-label">Open alerts</div>
          </div>
          <PriorityStrip counts={o.open_alerts_by_priority} />
          <Link to="/alerts" className="small">
            Work the alert queue →
          </Link>
        </div>
        <div className="stats">
          <Stat label="My open alerts" value={formatInt(o.my_open_alerts)} to="/alerts?assigned_to_me=true" />
          <Stat label="My open cases" value={formatInt(o.my_open_cases)} to="/cases?assigned_to_me=true" />
          <Stat
            label="Transactions"
            value={formatInt(o.transactions_total)}
            to="/transactions"
            hint={`${formatInt(o.transactions_scored)} scored by the active model`}
          />
          <Stat
            label="Alerts per 1,000 scored"
            value={o.alerts_per_1000_scored === null ? "–" : o.alerts_per_1000_scored.toFixed(2)}
            hint="Analyst workload"
          />
        </div>
      </section>

      <div className="grid-3">
        <Breakdown title="Alerts by status" counts={o.alerts_by_status} linkFor={(s) => `/alerts?status=${s}`} />
        <Breakdown title="Cases by status" counts={o.cases_by_status} linkFor={(s) => `/cases?status=${s}`} />
        <Breakdown title="Case decisions" counts={o.decisions} />
      </div>

      {o.active_model && (
        <section className="card">
          <h2>Risk score distribution</h2>
          {dist.isPending && <Loading />}
          {dist.isError && <ErrorState error={dist.error} onRetry={() => dist.refetch()} />}
          {dist.data && <Histogram data={dist.data} />}
        </section>
      )}

      <div className="grid-2">
        {o.active_model && (
          <section className="card">
            <h2>Active model</h2>
            <dl className="facts">
              <dt>Version</dt>
              <dd>
                <code>{o.active_model.version}</code>
              </dd>
              <dt>Alert threshold</dt>
              <dd>{formatScore(o.active_model.threshold)}</dd>
            </dl>
            {o.active_model.is_synthetic_demo && (
              <p className="warning">Trained on the bundled synthetic sample for smoke tests. Its scores are not results.</p>
            )}
            <Link to="/model">Evaluation details</Link>
          </section>
        )}
        {lc && (
          <section className="card">
            <h2>Alerts against synthetic labels</h2>
            <dl className="facts">
              <dt>Labelled fraud that raised an alert</dt>
              <dd>
                {formatInt(lc.labelled_fraud_alerted)} of {formatInt(lc.labelled_fraud_scored)} (
                {formatPct(lc.labelled_fraud_scored ? lc.labelled_fraud_alerted / lc.labelled_fraud_scored : null)})
              </dd>
              <dt>Alerts on labelled fraud</dt>
              <dd>
                {formatInt(lc.alerts_labelled_fraud)} of {formatInt(lc.alerts_with_label)} (
                {formatPct(lc.alerts_with_label ? lc.alerts_labelled_fraud / lc.alerts_with_label : null)})
              </dd>
            </dl>
            <p className="muted small">{lc.note}</p>
          </section>
        )}
      </div>
    </div>
  );
}
