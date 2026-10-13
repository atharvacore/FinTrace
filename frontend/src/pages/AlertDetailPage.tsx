import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router";
import { api } from "../api/client";
import type { AlertDetail, AlertStatus, AssignableUser, Case, CaseDetail, Page } from "../api/types";
import { useUser } from "../auth/AuthContext";
import { LevelBadge, StatusBadge } from "../components/Badges";
import { AssessmentView } from "../components/AssessmentView";
import { NewCaseForm } from "../components/NewCaseForm";
import { ErrorState, InlineError, Loading } from "../components/States";
import { TransactionFacts } from "../components/TransactionFacts";
import { formatDateTime, humanize } from "../lib/format";
import { allowedAlertMoves, hasRole } from "../lib/roles";

const MOVE_LABEL: Record<AlertStatus, string> = {
  open: "Back to open",
  in_review: "Start review",
  escalated: "Escalate",
  closed_false_positive: "Close as false positive",
  closed_actioned: "Close as actioned",
};

export function AlertDetailPage() {
  const id = Number(useParams().alertId);
  const user = useUser();
  const queryClient = useQueryClient();
  const senior = hasRole(user, "senior_analyst");
  const [creatingCase, setCreatingCase] = useState(false);
  const [caseId, setCaseId] = useState("");

  const alert = useQuery({ queryKey: ["alert", id], queryFn: () => api<AlertDetail>(`/alerts/${id}`) });
  const people = useQuery({
    queryKey: ["users", "assignable"],
    queryFn: () => api<AssignableUser[]>("/users/assignable"),
    enabled: senior,
  });
  const openCases = useQuery({
    queryKey: ["cases", "linkable"],
    queryFn: () =>
      api<Page<Case>>("/cases", { query: { status: ["open", "investigating", "pending_decision"], page_size: 100 } }),
    enabled: !!alert.data && alert.data.case_id == null,
  });

  const refresh = () => queryClient.invalidateQueries();
  const update = useMutation({
    mutationFn: (body: { status?: AlertStatus; assignee_id?: number | null }) =>
      api<AlertDetail>(`/alerts/${id}`, { method: "PATCH", body }),
    onSuccess: (data) => {
      queryClient.setQueryData(["alert", id], data);
      refresh();
    },
  });
  const link = useMutation({
    mutationFn: (target: number) =>
      api<CaseDetail>(`/cases/${target}/alerts`, { method: "POST", body: { alert_ids: [id] } }),
    onSuccess: refresh,
  });

  if (alert.isPending) return <Loading />;
  if (alert.isError) return <ErrorState error={alert.error} onRetry={() => alert.refetch()} />;
  const a = alert.data;
  const moves = allowedAlertMoves(a.status, user, a.assignee?.id);
  const canTake = a.assignee == null || senior;

  return (
    <div className="page">
      <header className="page-head">
        <p className="crumbs">
          <Link to="/alerts">Alert queue</Link> / Alert #{a.id}
        </p>
        <h1>
          Alert #{a.id} <LevelBadge level={a.priority} /> <StatusBadge status={a.status} />
        </h1>
        <p className="muted">
          Raised {formatDateTime(a.created_at)}
          {a.closed_at && `, closed ${formatDateTime(a.closed_at)}`}. Assignee: {a.assignee?.full_name ?? "unassigned"}.
        </p>
      </header>

      <section className="card">
        <h2>Actions</h2>
        <div className="actions">
          {a.assignee?.id !== user.id && canTake && (
            <button type="button" className="btn" disabled={update.isPending} onClick={() => update.mutate({ assignee_id: user.id })}>
              Assign to me
            </button>
          )}
          {a.assignee && (a.assignee.id === user.id || senior) && (
            <button type="button" className="btn" disabled={update.isPending} onClick={() => update.mutate({ assignee_id: null })}>
              Unassign
            </button>
          )}
          {moves.map((status) => (
            <button
              key={status}
              type="button"
              className={`btn ${status.startsWith("closed") ? "" : "btn-primary"}`}
              disabled={update.isPending}
              onClick={() => update.mutate({ status })}
            >
              {MOVE_LABEL[status]}
            </button>
          ))}
          {senior && people.data && (
            <label className="inline">
              Assign to
              <select
                value={a.assignee?.id ?? ""}
                onChange={(e) => update.mutate({ assignee_id: e.target.value ? Number(e.target.value) : null })}
              >
                <option value="">Unassigned</option>
                {people.data.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.full_name} ({humanize(p.role)})
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        {moves.length === 0 && !senior && (
          <p className="muted small">
            {a.status === "escalated"
              ? "Escalated alerts are handled by a senior analyst."
              : a.status.startsWith("closed")
                ? "Only a senior analyst can reopen a closed alert."
                : "This alert is assigned to someone else."}
          </p>
        )}
        <InlineError error={update.error} />
      </section>

      <section className="card">
        <h2>Case</h2>
        {a.case_id ? (
          <p>
            Part of <Link to={`/cases/${a.case_id}`}>{a.case_reference}</Link>.
          </p>
        ) : creatingCase ? (
          <NewCaseForm
            alertIds={[a.id]}
            defaultPriority={a.priority}
            defaultTitle={`${a.transaction.type} ${a.transaction.origin_account} → ${a.transaction.dest_account}`}
            onCancel={() => setCreatingCase(false)}
          />
        ) : (
          <div className="actions">
            <button type="button" className="btn btn-primary" onClick={() => setCreatingCase(true)}>
              Open a case
            </button>
            {openCases.data && openCases.data.items.length > 0 && (
              <>
                <select aria-label="Existing case" value={caseId} onChange={(e) => setCaseId(e.target.value)}>
                  <option value="">Add to an existing case…</option>
                  {openCases.data.items.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.reference}: {c.title}
                    </option>
                  ))}
                </select>
                <button type="button" className="btn" disabled={!caseId || link.isPending} onClick={() => link.mutate(Number(caseId))}>
                  Add
                </button>
              </>
            )}
          </div>
        )}
        <InlineError error={link.error} />
      </section>

      <div className="grid-2">
        <section className="card">
          <h2>Transaction</h2>
          <TransactionFacts tx={a.transaction} link />
        </section>
        <section className="card">
          <h2>Why it was flagged</h2>
          <AssessmentView assessment={a.assessment} />
        </section>
      </div>
    </div>
  );
}
