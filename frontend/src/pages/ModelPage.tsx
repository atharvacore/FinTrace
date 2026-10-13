import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { ModelEvaluation, ModelVersion, RiskDistribution } from "../api/types";
import { Histogram } from "../components/Histogram";
import { ErrorState, Loading } from "../components/States";
import { formatDateTime, formatInt, formatPct, formatScore, humanize } from "../lib/format";

interface PointMetrics {
  threshold: number;
  precision: number;
  recall: number;
  f1: number;
  alerts_per_1000?: number;
  confusion_matrix?: { tp: number; fp: number; fn: number; tn: number };
}
interface SplitMetrics {
  rows: number;
  positives: number;
  prevalence: number;
  average_precision: number;
  roc_auc: number;
  at_operating_threshold: PointMetrics;
  at_alert_budgets?: Record<string, PointMetrics>;
}
interface ModelMetrics {
  description?: string;
  operating_threshold?: number;
  validation?: SplitMetrics;
  test?: SplitMetrics;
}

function num(value: number | undefined, digits = 4) {
  return value === undefined || value === null ? "–" : value.toFixed(digits);
}

function MetricsTable({ models, chosen }: { models: Record<string, ModelMetrics>; chosen: string }) {
  const rows = Object.entries(models).flatMap(([name, m]) =>
    (["validation", "test"] as const).map((split) => ({ name, split, s: m[split] })),
  );
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Model</th>
            <th>Split</th>
            <th className="num">Rows</th>
            <th className="num">Prevalence</th>
            <th className="num">Avg precision</th>
            <th className="num">ROC AUC</th>
            <th className="num">Precision</th>
            <th className="num">Recall</th>
            <th className="num">F1</th>
            <th>TP / FP / FN</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ name, split, s }) => {
            const p = s?.at_operating_threshold;
            const cm = p?.confusion_matrix;
            return (
              <tr key={`${name}-${split}`} className={name === chosen ? "highlight" : undefined}>
                <td>
                  {humanize(name)}
                  {name === chosen && <span className="badge level-low badge-gap">deployed</span>}
                </td>
                <td>{split}</td>
                <td className="num">{formatInt(s?.rows)}</td>
                <td className="num">{formatPct(s?.prevalence, 3)}</td>
                <td className="num">{num(s?.average_precision)}</td>
                <td className="num">{num(s?.roc_auc)}</td>
                <td className="num">{num(p?.precision)}</td>
                <td className="num">{num(p?.recall)}</td>
                <td className="num">{num(p?.f1)}</td>
                <td className="nowrap">{cm ? `${formatInt(cm.tp)} / ${formatInt(cm.fp)} / ${formatInt(cm.fn)}` : "–"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function BudgetTable({ budgets }: { budgets: Record<string, PointMetrics> }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Budget (set on validation)</th>
            <th className="num">Threshold</th>
            <th className="num">Alerts per 1,000</th>
            <th className="num">Precision</th>
            <th className="num">Recall</th>
            <th className="num">FP per TP</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(budgets)
            .sort(([x], [y]) => parseFloat(x.replace("top_", "")) - parseFloat(y.replace("top_", "")))
            .map(([name, b]) => {
            const cm = b.confusion_matrix;
            return (
              <tr key={name}>
                <td>{name.replace("top_", "Top ").replace("pct", "%")}</td>
                <td className="num">{num(b.threshold, 6)}</td>
                <td className="num">{num(b.alerts_per_1000, 2)}</td>
                <td className="num">{num(b.precision)}</td>
                <td className="num">{num(b.recall)}</td>
                <td className="num">{cm && cm.tp ? (cm.fp / cm.tp).toFixed(2) : "–"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function ModelPage() {
  const evaluation = useQuery({ queryKey: ["metrics", "model-evaluation"], queryFn: () => api<ModelEvaluation>("/metrics/model-evaluation") });
  const dist = useQuery({ queryKey: ["metrics", "risk-distribution"], queryFn: () => api<RiskDistribution>("/metrics/risk-distribution") });
  const versions = useQuery({ queryKey: ["models"], queryFn: () => api<ModelVersion[]>("/models") });

  if (evaluation.isPending) return <Loading />;
  if (evaluation.isError) return <ErrorState error={evaluation.error} onRetry={() => evaluation.refetch()} />;
  const e = evaluation.data;
  const models = e.models as Record<string, ModelMetrics>;
  const chosen = String(e.selection.chosen ?? "");
  const deployed = models[chosen];
  const boundaries = (e.split.boundaries ?? {}) as Record<string, number>;

  return (
    <div className="page">
      <header className="page-head">
        <h1>Model evaluation</h1>
        <p className="muted">
          Offline results stored with the active model, measured once on a chronological test period. Thresholds and budgets were
          chosen on validation.
        </p>
      </header>

      <section className="card caveats" role="note">
        <h2>Read this first</h2>
        <ul>
          {e.caveats.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      </section>

      <div className="grid-2">
        <section className="card">
          <h2>Active model</h2>
          <dl className="facts">
            <dt>Version</dt>
            <dd>
              <code>{e.version}</code>
            </dd>
            <dt>Algorithm</dt>
            <dd>{humanize(e.algorithm)}</dd>
            <dt>Feature set</dt>
            <dd>{e.feature_set}</dd>
            <dt>Alert threshold</dt>
            <dd>{formatScore(e.threshold, 5)}</dd>
            <dt>Trained</dt>
            <dd>{formatDateTime(e.trained_at)}</dd>
            <dt>Data</dt>
            <dd>
              {e.data_kind ?? "–"}, {formatInt(Number(e.dataset.rows_used ?? 0))} rows
            </dd>
          </dl>
        </section>
        <section className="card">
          <h2>How it was evaluated</h2>
          <p>
            Split {String(e.split.method ?? "")}: train up to hour {boundaries.train_last_step}, validation to {boundaries.valid_last_step},
            test to {boundaries.test_last_step}. Selected by {String(e.selection.metric ?? "")}.
          </p>
          <ul className="list small">
            {e.methodology.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </section>
      </div>

      <section className="card">
        <h2>Results at the operating threshold</h2>
        <MetricsTable models={models} chosen={chosen} />
      </section>

      {deployed?.test?.at_alert_budgets && (
        <section className="card">
          <h2>Analyst workload on the test period</h2>
          <BudgetTable budgets={deployed.test.at_alert_budgets} />
        </section>
      )}

      <section className="card">
        <h2>Scores in this database</h2>
        {dist.isPending && <Loading />}
        {dist.isError && <ErrorState error={dist.error} onRetry={() => dist.refetch()} />}
        {dist.data && <Histogram data={dist.data} />}
      </section>

      {versions.data && (
        <section className="card">
          <h2>Registered versions</h2>
          <table>
            <thead>
              <tr>
                <th>Version</th>
                <th>Feature set</th>
                <th className="num">Threshold</th>
                <th>Registered</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {versions.data.map((v) => (
                <tr key={v.id}>
                  <td>
                    <code>{v.version}</code>
                    {v.is_synthetic_demo && <span className="badge level-medium badge-gap">demo</span>}
                  </td>
                  <td>{v.feature_set}</td>
                  <td className="num">{formatScore(v.threshold, 5)}</td>
                  <td>{formatDateTime(v.registered_at)}</td>
                  <td>{v.is_active ? "Active" : <span className="muted">Inactive</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">Admins switch versions with POST /api/v1/models/&#123;id&#125;/activate.</p>
        </section>
      )}
    </div>
  );
}
