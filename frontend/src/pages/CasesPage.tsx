import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api } from "../api/client";
import type { Case, Page } from "../api/types";
import { LevelBadge, StatusBadge } from "../components/Badges";
import { NewCaseForm } from "../components/NewCaseForm";
import { Pagination } from "../components/Pagination";
import { Empty, ErrorState, Loading } from "../components/States";
import { formatDateTime, humanize } from "../lib/format";
import { useSearchState } from "../lib/useSearchState";

const PAGE_SIZE = 25;

export function CasesPage() {
  const { get, page, update } = useSearchState();
  const [creating, setCreating] = useState(false);
  const [text, setText] = useState(get("q"));
  const query = {
    status: get("status") || undefined,
    priority: get("priority") || undefined,
    assigned_to_me: get("assigned_to_me") === "true" || undefined,
    q: get("q") || undefined,
    sort: get("sort") || "-updated_at",
    page,
    page_size: PAGE_SIZE,
  };
  const cases = useQuery({
    queryKey: ["cases", query],
    queryFn: () => api<Page<Case>>("/cases", { query }),
    placeholderData: keepPreviousData,
  });

  return (
    <div className="page">
      <header className="page-head row">
        <div>
          <h1>Cases</h1>
          <p className="muted">Investigations group related alerts. A senior analyst closes a case by recording a decision.</p>
        </div>
        {!creating && (
          <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>
            New case
          </button>
        )}
      </header>
      {creating && <NewCaseForm onCancel={() => setCreating(false)} />}

      <form
        className="filters card"
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          update({ q: text.trim() || null });
        }}
      >
        <label className="grow">
          Search
          <input placeholder="Reference or title" value={text} onChange={(e) => setText(e.target.value)} />
        </label>
        <label>
          Status
          <select value={get("status")} onChange={(e) => update({ status: e.target.value || null })}>
            <option value="">Any</option>
            {["open", "investigating", "pending_decision", "closed"].map((s) => (
              <option key={s} value={s}>
                {humanize(s)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Priority
          <select value={get("priority")} onChange={(e) => update({ priority: e.target.value || null })}>
            <option value="">Any</option>
            {["critical", "high", "medium", "low"].map((s) => (
              <option key={s} value={s}>
                {humanize(s)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Sort
          <select value={get("sort") || "-updated_at"} onChange={(e) => update({ sort: e.target.value })}>
            <option value="-updated_at">Recently updated</option>
            <option value="-priority">Priority</option>
            <option value="-created_at">Newest</option>
            <option value="created_at">Oldest</option>
          </select>
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={get("assigned_to_me") === "true"}
            onChange={(e) => update({ assigned_to_me: e.target.checked ? "true" : null })}
          />
          Assigned to me
        </label>
        <button type="submit" className="btn">
          Search
        </button>
      </form>

      {cases.isPending ? (
        <Loading />
      ) : cases.isError ? (
        <ErrorState error={cases.error} onRetry={() => cases.refetch()} />
      ) : cases.data.items.length === 0 ? (
        <Empty title="No cases match">Open a case from the alert queue, or with New case.</Empty>
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Reference</th>
                  <th>Title</th>
                  <th>Priority</th>
                  <th>Status</th>
                  <th>Decision</th>
                  <th className="num">Alerts</th>
                  <th className="num">Notes</th>
                  <th>Assignee</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {cases.data.items.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <Link to={`/cases/${c.id}`}>{c.reference}</Link>
                    </td>
                    <td>{c.title}</td>
                    <td>
                      <LevelBadge level={c.priority} />
                    </td>
                    <td>
                      <StatusBadge status={c.status} />
                    </td>
                    <td>{c.decision ? humanize(c.decision) : <span className="muted">–</span>}</td>
                    <td className="num">{c.alert_count}</td>
                    <td className="num">{c.note_count}</td>
                    <td>{c.assignee?.full_name ?? <span className="muted">Unassigned</span>}</td>
                    <td className="nowrap">{formatDateTime(c.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} pageSize={PAGE_SIZE} total={cases.data.total} onPage={(p) => update({ page: String(p) }, true)} />
        </>
      )}
    </div>
  );
}
