import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../api/client";
import type { AuditEvent, Page } from "../api/types";
import { Pagination } from "../components/Pagination";
import { Empty, ErrorState, Loading } from "../components/States";
import { formatDateTime } from "../lib/format";
import { useSearchState } from "../lib/useSearchState";

const PAGE_SIZE = 50;
const LINKS: Record<string, string> = { case: "/cases/", alert: "/alerts/", transaction: "/transactions/" };

function Change({ event }: { event: AuditEvent }) {
  const before = event.before ?? {};
  const after = event.after ?? {};
  const keys = Array.from(new Set([...Object.keys(before), ...Object.keys(after)]));
  const changed = keys.filter((k) => JSON.stringify(before[k]) !== JSON.stringify(after[k]));
  if (changed.length === 0) return <span className="muted">–</span>;
  return (
    <ul className="changes">
      {changed.slice(0, 6).map((k) => (
        <li key={k}>
          <code>{k}</code>: {k in before ? <span className="muted">{JSON.stringify(before[k])} → </span> : null}
          {JSON.stringify(after[k] ?? null)}
        </li>
      ))}
    </ul>
  );
}

export function AuditPage() {
  const { get, page, update } = useSearchState();
  const query = {
    entity_type: get("entity_type") || undefined,
    entity_id: get("entity_id") || undefined,
    action: get("action") || undefined,
    page,
    page_size: PAGE_SIZE,
  };
  const events = useQuery({
    queryKey: ["audit", query],
    queryFn: () => api<Page<AuditEvent>>("/audit-events", { query }),
    placeholderData: keepPreviousData,
  });

  return (
    <div className="page">
      <header className="page-head">
        <h1>Audit log</h1>
        <p className="muted">Append-only record of sensitive changes: who did what, to which record, and when.</p>
      </header>
      <div className="filters card">
        <label>
          Record type
          <select value={get("entity_type")} onChange={(e) => update({ entity_type: e.target.value || null, entity_id: null })}>
            <option value="">Any</option>
            {["case", "alert", "user", "monitoring_rule", "model_version", "import_batch", "transaction", "transaction_batch"].map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label>
          Record ID
          <input value={get("entity_id")} onChange={(e) => update({ entity_id: e.target.value || null })} />
        </label>
        <label>
          Action
          <input placeholder="e.g. case. or alert.updated" value={get("action")} onChange={(e) => update({ action: e.target.value || null })} />
        </label>
      </div>
      {events.isPending ? (
        <Loading />
      ) : events.isError ? (
        <ErrorState error={events.error} onRetry={() => events.refetch()} />
      ) : events.data.items.length === 0 ? (
        <Empty title="No audit events match" />
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>When</th>
                  <th>Who</th>
                  <th>Action</th>
                  <th>Record</th>
                  <th>Change</th>
                  <th>Request</th>
                </tr>
              </thead>
              <tbody>
                {events.data.items.map((e) => {
                  const base = LINKS[e.entity_type];
                  return (
                    <tr key={e.id}>
                      <td className="nowrap">{formatDateTime(e.created_at)}</td>
                      <td>{e.actor?.full_name ?? <span className="muted">System</span>}</td>
                      <td>
                        <code>{e.action}</code>
                      </td>
                      <td>
                        {base ? <Link to={`${base}${e.entity_id}`}>{`${e.entity_type} ${e.entity_id}`}</Link> : `${e.entity_type} ${e.entity_id}`}
                      </td>
                      <td>
                        <Change event={e} />
                      </td>
                      <td className="muted small mono">{e.request_id?.slice(0, 12) ?? "–"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <Pagination page={page} pageSize={PAGE_SIZE} total={events.data.total} onPage={(p) => update({ page: String(p) }, true)} />
        </>
      )}
    </div>
  );
}
