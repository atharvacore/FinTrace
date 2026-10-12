import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router";
import { api } from "../api/client";
import type { ScoreOneResult, TransactionDetail } from "../api/types";
import { useUser } from "../auth/AuthContext";
import { LevelBadge, ReasonCodes, StatusBadge, SyntheticLabel } from "../components/Badges";
import { AssessmentView } from "../components/AssessmentView";
import { Empty, ErrorState, InlineError, Loading } from "../components/States";
import { TransactionFacts } from "../components/TransactionFacts";
import { formatDateTime, formatScore } from "../lib/format";
import { hasRole } from "../lib/roles";

export function TransactionDetailPage() {
  const id = Number(useParams().transactionId);
  const user = useUser();
  const queryClient = useQueryClient();
  const tx = useQuery({ queryKey: ["transaction", id], queryFn: () => api<TransactionDetail>(`/transactions/${id}`) });
  const score = useMutation({
    mutationFn: () => api<ScoreOneResult>(`/scoring/transactions/${id}`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries(),
  });

  if (tx.isPending) return <Loading />;
  if (tx.isError) return <ErrorState error={tx.error} onRetry={() => tx.refetch()} />;
  const t = tx.data;
  const [latest, ...older] = t.assessments;

  return (
    <div className="page">
      <header className="page-head">
        <p className="crumbs">
          <Link to="/transactions">Transactions</Link> / #{t.id}
        </p>
        <h1>
          Transaction #{t.id} {latest && <LevelBadge level={latest.risk_level} />}
        </h1>
        <p>
          <SyntheticLabel value={t.synthetic_label_is_fraud} />{" "}
          <span className="muted small">Shown for evaluation only; it is not an investigation outcome.</span>
        </p>
      </header>

      <div className="grid-2">
        <section className="card">
          <h2>Details</h2>
          <TransactionFacts tx={t} />
        </section>
        <section className="card">
          <h2>Latest assessment</h2>
          {latest ? <AssessmentView assessment={latest} /> : <Empty title="Not scored yet" />}
          {hasRole(user, "senior_analyst") && (
            <div className="actions">
              <button type="button" className="btn" disabled={score.isPending} onClick={() => score.mutate()}>
                {score.isPending ? "Scoring…" : latest ? "Score again" : "Score now"}
              </button>
            </div>
          )}
          <InlineError error={score.error} />
        </section>
      </div>

      <section className="card">
        <h2>Alerts</h2>
        {t.alerts.length === 0 ? (
          <p className="muted">No alerts for this transaction.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Alert</th>
                <th>Priority</th>
                <th>Status</th>
                <th>Case</th>
                <th>Raised</th>
              </tr>
            </thead>
            <tbody>
              {t.alerts.map((a) => (
                <tr key={a.id}>
                  <td>
                    <Link to={`/alerts/${a.id}`}>#{a.id}</Link>
                  </td>
                  <td>
                    <LevelBadge level={a.priority} />
                  </td>
                  <td>
                    <StatusBadge status={a.status} />
                  </td>
                  <td>{a.case_id ? <Link to={`/cases/${a.case_id}`}>{a.case_reference}</Link> : <span className="muted">–</span>}</td>
                  <td>{formatDateTime(a.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {older.length > 0 && (
        <section className="card">
          <h2>Earlier assessments</h2>
          <table>
            <thead>
              <tr>
                <th>Scored</th>
                <th>Model</th>
                <th className="num">Score</th>
                <th>Level</th>
                <th>Reasons</th>
              </tr>
            </thead>
            <tbody>
              {older.map((a) => (
                <tr key={a.id}>
                  <td>{formatDateTime(a.scored_at)}</td>
                  <td>
                    <code>{a.model_version}</code>
                  </td>
                  <td className="num">{formatScore(a.risk_score)}</td>
                  <td>
                    <LevelBadge level={a.risk_level} />
                  </td>
                  <td>
                    <ReasonCodes codes={a.reason_codes} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
