import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router";
import { api } from "../api/client";
import type { AssignableUser, CaseDecision, CaseDetail, CaseStatus, Note, RiskLevel } from "../api/types";
import { useUser } from "../auth/AuthContext";
import { LevelBadge, ReasonCodes, StatusBadge } from "../components/Badges";
import { ErrorState, InlineError, Loading } from "../components/States";
import { formatDateTime, formatMoney, formatScore, humanize } from "../lib/format";
import { hasRole } from "../lib/roles";

const WORKING: CaseStatus[] = ["open", "investigating", "pending_decision"];
const DECISIONS: { value: CaseDecision; label: string }[] = [
  { value: "no_further_action", label: "No further action" },
  { value: "false_positive", label: "False positive" },
  { value: "escalate_for_reporting", label: "Escalate for reporting" },
];

export function CaseDetailPage() {
  const id = Number(useParams().caseId);
  const user = useUser();
  const senior = hasRole(user, "senior_analyst");
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const [alertInput, setAlertInput] = useState("");
  const [decision, setDecision] = useState<CaseDecision>("no_further_action");
  const [rationale, setRationale] = useState("");

  const detail = useQuery({ queryKey: ["case", id], queryFn: () => api<CaseDetail>(`/cases/${id}`) });
  const people = useQuery({
    queryKey: ["users", "assignable"],
    queryFn: () => api<AssignableUser[]>("/users/assignable"),
    enabled: senior,
  });

  const onCase = (data: CaseDetail) => {
    queryClient.setQueryData(["case", id], data);
    queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "case" });
  };
  const patch = useMutation({
    mutationFn: (body: Partial<{ status: CaseStatus; priority: RiskLevel; assignee_id: number | null }>) =>
      api<CaseDetail>(`/cases/${id}`, { method: "PATCH", body }),
    onSuccess: onCase,
  });
  const link = useMutation({
    mutationFn: (alertIds: number[]) => api<CaseDetail>(`/cases/${id}/alerts`, { method: "POST", body: { alert_ids: alertIds } }),
    onSuccess: (data) => {
      setAlertInput("");
      onCase(data);
    },
  });
  const unlink = useMutation({
    mutationFn: (alertId: number) => api<CaseDetail>(`/cases/${id}/alerts/${alertId}`, { method: "DELETE" }),
    onSuccess: onCase,
  });
  const addNote = useMutation({
    mutationFn: () => api<Note>(`/cases/${id}/notes`, { method: "POST", body: { body: note } }),
    onSuccess: () => {
      setNote("");
      queryClient.invalidateQueries();
    },
  });
  const decide = useMutation({
    mutationFn: () => api<CaseDetail>(`/cases/${id}/decision`, { method: "POST", body: { decision, rationale } }),
    onSuccess: (data) => {
      setRationale("");
      onCase(data);
    },
  });

  if (detail.isPending) return <Loading />;
  if (detail.isError) return <ErrorState error={detail.error} onRetry={() => detail.refetch()} />;
  const c = detail.data;
  const closed = c.status === "closed";
  const canWork = !closed && (senior || c.assignee == null || c.assignee.id === user.id);

  function submitLink(event: FormEvent) {
    event.preventDefault();
    const ids = alertInput
      .split(/[\s,]+/)
      .map((s) => Number(s.replace(/^#/, "")))
      .filter((n) => Number.isInteger(n) && n > 0);
    if (ids.length) link.mutate(ids);
  }

  return (
    <div className="page">
      <header className="page-head">
        <p className="crumbs">
          <Link to="/cases">Cases</Link> / {c.reference}
        </p>
        <h1>
          {c.reference}: {c.title} <LevelBadge level={c.priority} /> <StatusBadge status={c.status} />
        </h1>
        <p className="muted">
          Opened by {c.created_by.full_name} on {formatDateTime(c.created_at)}. Assignee: {c.assignee?.full_name ?? "unassigned"}.
        </p>
        {c.description && <p className="description">{c.description}</p>}
      </header>

      {closed ? (
        <section className="card decision">
          <h2>Decision: {humanize(c.decision)}</h2>
          <p className="description">{c.decision_rationale}</p>
          <p className="muted small">
            Recorded by {c.decided_by?.full_name} on {formatDateTime(c.decided_at)}. A closed case is final; notes can still be
            added.
          </p>
        </section>
      ) : (
        <section className="card">
          <h2>Work the case</h2>
          {!canWork && <p className="muted">This case is assigned to {c.assignee?.full_name}. You can read it and add notes.</p>}
          {canWork && (
            <div className="actions">
              <label className="inline">
                Status
                <select value={c.status} disabled={patch.isPending} onChange={(e) => patch.mutate({ status: e.target.value as CaseStatus })}>
                  {WORKING.map((s) => (
                    <option key={s} value={s}>
                      {humanize(s)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="inline">
                Priority
                <select value={c.priority} disabled={patch.isPending} onChange={(e) => patch.mutate({ priority: e.target.value as RiskLevel })}>
                  {(["low", "medium", "high", "critical"] as RiskLevel[]).map((s) => (
                    <option key={s} value={s}>
                      {humanize(s)}
                    </option>
                  ))}
                </select>
              </label>
              {senior && people.data ? (
                <label className="inline">
                  Assignee
                  <select
                    value={c.assignee?.id ?? ""}
                    disabled={patch.isPending}
                    onChange={(e) => patch.mutate({ assignee_id: e.target.value ? Number(e.target.value) : null })}
                  >
                    <option value="">Unassigned</option>
                    {people.data.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.full_name}
                      </option>
                    ))}
                  </select>
                </label>
              ) : c.assignee?.id === user.id ? (
                <button type="button" className="btn" onClick={() => patch.mutate({ assignee_id: null })}>
                  Unassign me
                </button>
              ) : (
                <button type="button" className="btn" onClick={() => patch.mutate({ assignee_id: user.id })}>
                  Assign to me
                </button>
              )}
            </div>
          )}
          <InlineError error={patch.error} />
        </section>
      )}

      <section className="card">
        <h2>Linked alerts ({c.alerts.length})</h2>
        {c.alerts.length === 0 ? (
          <p className="muted">No alerts linked yet.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Alert</th>
                  <th>Priority</th>
                  <th>Status</th>
                  <th className="num">Score</th>
                  <th>Transaction</th>
                  <th className="num">Amount</th>
                  <th>Reasons</th>
                  {canWork && <th aria-label="Actions" />}
                </tr>
              </thead>
              <tbody>
                {c.alerts.map((a) => (
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
                    <td className="num">{formatScore(a.risk_score)}</td>
                    <td>
                      <Link to={`/transactions/${a.transaction.id}`}>{a.transaction.type}</Link>{" "}
                      <span className="muted small">
                        {a.transaction.origin_account} → {a.transaction.dest_account}
                      </span>
                    </td>
                    <td className="num">{formatMoney(a.transaction.amount)}</td>
                    <td>
                      <ReasonCodes codes={a.reason_codes} />
                    </td>
                    {canWork && (
                      <td>
                        <button type="button" className="btn btn-small btn-ghost" disabled={unlink.isPending} onClick={() => unlink.mutate(a.id)}>
                          Unlink
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {canWork && (
          <form className="inline-form" onSubmit={submitLink}>
            <label className="inline">
              Link alerts by ID
              <input placeholder="e.g. 12, 15" value={alertInput} onChange={(e) => setAlertInput(e.target.value)} />
            </label>
            <button type="submit" className="btn" disabled={link.isPending}>
              Link
            </button>
          </form>
        )}
        <InlineError error={link.error ?? unlink.error} />
      </section>

      {!closed && senior && (
        <section className="card">
          <h2>Record decision</h2>
          <p className="muted small">
            Closes the case. A decision is a human judgement; the risk score is a triage signal, not evidence.
          </p>
          <form
            className="form"
            onSubmit={(e) => {
              e.preventDefault();
              decide.mutate();
            }}
          >
            <label>
              Decision
              <select value={decision} onChange={(e) => setDecision(e.target.value as CaseDecision)}>
                {DECISIONS.map((d) => (
                  <option key={d.value} value={d.value}>
                    {d.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Rationale
              <textarea rows={3} required minLength={10} value={rationale} onChange={(e) => setRationale(e.target.value)} />
            </label>
            <InlineError error={decide.error} />
            <div className="actions">
              <button type="submit" className="btn btn-primary" disabled={decide.isPending}>
                Record decision and close
              </button>
            </div>
          </form>
        </section>
      )}

      <div className="grid-2">
        <section className="card">
          <h2>Notes ({c.notes.length})</h2>
          {c.notes.length === 0 && <p className="muted">No notes yet.</p>}
          <ol className="notes">
            {c.notes.map((n) => (
              <li key={n.id}>
                <div className="muted small">
                  {n.author.full_name}, {formatDateTime(n.created_at)}
                </div>
                <p className="description">{n.body}</p>
              </li>
            ))}
          </ol>
          <form
            className="form"
            onSubmit={(e) => {
              e.preventDefault();
              if (note.trim()) addNote.mutate();
            }}
          >
            <label>
              Add a note
              <textarea rows={3} maxLength={10000} value={note} onChange={(e) => setNote(e.target.value)} />
            </label>
            <InlineError error={addNote.error} />
            <div className="actions">
              <button type="submit" className="btn" disabled={addNote.isPending || !note.trim()}>
                Add note
              </button>
              <span className="muted small">Notes cannot be edited or deleted.</span>
            </div>
          </form>
        </section>
        <section className="card">
          <h2>Timeline</h2>
          <ol className="timeline">
            {c.timeline.map((e) => (
              <li key={e.id}>
                <span className="muted small">{formatDateTime(e.created_at)}</span> <strong>{e.actor?.full_name ?? "System"}</strong>{" "}
                {humanize(e.action.replace("case.", ""))}
                {e.after && "status" in e.after && e.before && e.before.status !== e.after.status && (
                  <span className="muted"> ({humanize(String(e.before.status))} → {humanize(String(e.after.status))})</span>
                )}
              </li>
            ))}
          </ol>
        </section>
      </div>
    </div>
  );
}
