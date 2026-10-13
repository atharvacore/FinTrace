import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api } from "../api/client";
import type { Alert, Page } from "../api/types";
import { LevelBadge, ReasonCodes, StatusBadge } from "../components/Badges";
import { NewCaseForm } from "../components/NewCaseForm";
import { Pagination } from "../components/Pagination";
import { Empty, ErrorState, Loading } from "../components/States";
import { formatDateTime, formatMoney, formatScore } from "../lib/format";
import { useSearchState } from "../lib/useSearchState";

const ACTIVE = ["open", "in_review", "escalated"];
const PAGE_SIZE = 25;

export function AlertsPage() {
  const { get, getAll, page, update } = useSearchState();
  const [selected, setSelected] = useState<number[]>([]);
  const [creating, setCreating] = useState(false);

  const statuses = getAll("status");
  const view = get("view") || (statuses.length ? "custom" : "active");
  const query = {
    status: view === "active" ? ACTIVE : view === "all" ? [] : statuses,
    priority: getAll("priority"),
    assigned_to_me: get("assigned_to_me") === "true" || undefined,
    unassigned: get("unassigned") === "true" || undefined,
    in_case: get("in_case") || undefined,
    min_score: get("min_score") || undefined,
    reason_code: get("reason_code") || undefined,
    sort: get("sort") || "-priority",
    page,
    page_size: PAGE_SIZE,
  };
  const alerts = useQuery({
    queryKey: ["alerts", query],
    queryFn: () => api<Page<Alert>>("/alerts", { query }),
    placeholderData: keepPreviousData,
  });

  const toggle = (id: number) =>
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  const selectable = alerts.data?.items.filter((a) => a.case_id == null) ?? [];

  return (
    <div className="page">
      <header className="page-head">
        <h1>Alert queue</h1>
        <p className="muted">Alerts are raised when the model score reaches the threshold or a high-severity rule fires.</p>
      </header>

      <div className="filters card">
        <label>
          Show
          <select
            value={view === "custom" ? statuses[0] ?? "" : view}
            onChange={(e) => {
              const v = e.target.value;
              if (v === "active" || v === "all") update({ view: v, status: null });
              else update({ view: null, status: v });
            }}
          >
            <option value="active">Open, in review, escalated</option>
            <option value="all">All statuses</option>
            <option value="open">Open</option>
            <option value="in_review">In review</option>
            <option value="escalated">Escalated</option>
            <option value="closed_false_positive">Closed: false positive</option>
            <option value="closed_actioned">Closed: actioned</option>
          </select>
        </label>
        <label>
          Priority
          <select value={getAll("priority")[0] ?? ""} onChange={(e) => update({ priority: e.target.value || null })}>
            <option value="">Any</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </label>
        <label>
          Case
          <select value={get("in_case")} onChange={(e) => update({ in_case: e.target.value || null })}>
            <option value="">Any</option>
            <option value="false">Not in a case</option>
            <option value="true">In a case</option>
          </select>
        </label>
        <label>
          Min score
          <input
            type="number"
            min={0}
            max={1}
            step={0.01}
            value={get("min_score")}
            onChange={(e) => update({ min_score: e.target.value || null })}
          />
        </label>
        <label>
          Sort
          <select value={get("sort") || "-priority"} onChange={(e) => update({ sort: e.target.value })}>
            <option value="-priority">Priority</option>
            <option value="-risk_score">Score</option>
            <option value="-created_at">Newest</option>
            <option value="created_at">Oldest</option>
          </select>
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={get("assigned_to_me") === "true"}
            onChange={(e) => update({ assigned_to_me: e.target.checked ? "true" : null, unassigned: null })}
          />
          Assigned to me
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={get("unassigned") === "true"}
            onChange={(e) => update({ unassigned: e.target.checked ? "true" : null, assigned_to_me: null })}
          />
          Unassigned
        </label>
      </div>

      {selected.length > 0 && !creating && (
        <div className="selection-bar">
          {selected.length} selected
          <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>
            Open case with selected
          </button>
          <button type="button" className="btn" onClick={() => setSelected([])}>
            Clear
          </button>
        </div>
      )}
      {creating && <NewCaseForm alertIds={selected} onCancel={() => setCreating(false)} />}

      {alerts.isPending ? (
        <Loading />
      ) : alerts.isError ? (
        <ErrorState error={alerts.error} onRetry={() => alerts.refetch()} />
      ) : alerts.data.items.length === 0 ? (
        <Empty title="No alerts match these filters">
          Alerts appear after transactions are scored (<code>POST /api/v1/scoring/run</code>).
        </Empty>
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th aria-label="Select" />
                  <th>Alert</th>
                  <th>Priority</th>
                  <th>Status</th>
                  <th className="num">Score</th>
                  <th>Transaction</th>
                  <th className="num">Amount</th>
                  <th>Reasons</th>
                  <th>Assignee</th>
                  <th>Case</th>
                  <th>Raised</th>
                </tr>
              </thead>
              <tbody>
                {alerts.data.items.map((a) => (
                  <tr key={a.id}>
                    <td>
                      {a.case_id == null && (
                        <input
                          type="checkbox"
                          aria-label={`Select alert ${a.id}`}
                          checked={selected.includes(a.id)}
                          onChange={() => toggle(a.id)}
                        />
                      )}
                    </td>
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
                      <span className="muted small">{a.transaction.origin_account} → {a.transaction.dest_account}</span>
                    </td>
                    <td className="num">{formatMoney(a.transaction.amount)}</td>
                    <td>
                      <ReasonCodes codes={a.reason_codes} max={3} />
                    </td>
                    <td>{a.assignee?.full_name ?? <span className="muted">Unassigned</span>}</td>
                    <td>{a.case_id ? <Link to={`/cases/${a.case_id}`}>{a.case_reference}</Link> : <span className="muted">–</span>}</td>
                    <td className="nowrap">{formatDateTime(a.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {selectable.length > 0 && selected.length === 0 && (
            <p className="muted small">Tick alerts that are not in a case yet to open a case with them.</p>
          )}
          <Pagination page={page} pageSize={PAGE_SIZE} total={alerts.data.total} onPage={(p) => update({ page: String(p) }, true)} />
        </>
      )}
    </div>
  );
}
