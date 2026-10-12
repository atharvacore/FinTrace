import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import { api } from "../api/client";
import type { Page, TransactionListItem } from "../api/types";
import { LevelBadge } from "../components/Badges";
import { Pagination } from "../components/Pagination";
import { Empty, ErrorState, Loading } from "../components/States";
import { formatDateTime, formatMoney, formatScore } from "../lib/format";
import { useSearchState } from "../lib/useSearchState";

const PAGE_SIZE = 25;
const TYPES = ["CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"];

export function TransactionsPage() {
  const { get, page, update } = useSearchState();
  const q = get("q");
  const [text, setText] = useState(q);
  // Keep the search box in sync when the URL changes (back button, links).
  const [syncedQ, setSyncedQ] = useState(q);
  if (q !== syncedQ) {
    setSyncedQ(q);
    setText(q);
  }

  const query = {
    q: get("q") || undefined,
    account: get("account") || undefined,
    type: get("type") || undefined,
    min_amount: get("min_amount") || undefined,
    max_amount: get("max_amount") || undefined,
    risk_level: get("risk_level") || undefined,
    has_open_alert: get("has_open_alert") || undefined,
    sort: get("sort") || "-occurred_at",
    page,
    page_size: PAGE_SIZE,
  };
  const txs = useQuery({
    queryKey: ["transactions", query],
    queryFn: () => api<Page<TransactionListItem>>("/transactions", { query }),
    placeholderData: keepPreviousData,
  });

  function search(event: FormEvent) {
    event.preventDefault();
    update({ q: text.trim() || null, account: null });
  }

  return (
    <div className="page">
      <header className="page-head">
        <h1>Transactions</h1>
        <p className="muted">Synthetic PaySim-format transactions. Times are simulated hours on a fixed 2026 calendar.</p>
      </header>

      <form className="filters card" onSubmit={search} role="search">
        <label className="grow">
          Search
          <input
            placeholder="Account or external ID (prefix)"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </label>
        <label>
          Type
          <select value={get("type")} onChange={(e) => update({ type: e.target.value || null })}>
            <option value="">Any</option>
            {TYPES.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
        <label>
          Min amount
          <input type="number" min={0} value={get("min_amount")} onChange={(e) => update({ min_amount: e.target.value || null })} />
        </label>
        <label>
          Max amount
          <input type="number" min={0} value={get("max_amount")} onChange={(e) => update({ max_amount: e.target.value || null })} />
        </label>
        <label>
          Risk level
          <select value={get("risk_level")} onChange={(e) => update({ risk_level: e.target.value || null })}>
            <option value="">Any</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </label>
        <label>
          Open alert
          <select value={get("has_open_alert")} onChange={(e) => update({ has_open_alert: e.target.value || null })}>
            <option value="">Any</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </label>
        <label>
          Sort
          <select value={get("sort") || "-occurred_at"} onChange={(e) => update({ sort: e.target.value })}>
            <option value="-occurred_at">Newest</option>
            <option value="occurred_at">Oldest</option>
            <option value="-amount">Largest amount</option>
            <option value="amount">Smallest amount</option>
          </select>
        </label>
        <button type="submit" className="btn">
          Search
        </button>
      </form>
      {get("account") && (
        <p>
          Showing account <code>{get("account")}</code>.{" "}
          <button type="button" className="btn btn-small btn-ghost" onClick={() => update({ account: null })}>
            Clear
          </button>
        </p>
      )}

      {txs.isPending ? (
        <Loading />
      ) : txs.isError ? (
        <ErrorState error={txs.error} onRetry={() => txs.refetch()} />
      ) : txs.data.items.length === 0 ? (
        <Empty title="No transactions match">Try fewer filters, or import the synthetic sample.</Empty>
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>When</th>
                  <th>Type</th>
                  <th className="num">Amount</th>
                  <th>From</th>
                  <th>To</th>
                  <th className="num">Latest score</th>
                  <th>Level</th>
                  <th>Open alert</th>
                </tr>
              </thead>
              <tbody>
                {txs.data.items.map((t) => (
                  <tr key={t.id}>
                    <td>
                      <Link to={`/transactions/${t.id}`}>#{t.id}</Link>
                    </td>
                    <td className="nowrap">{formatDateTime(t.occurred_at)}</td>
                    <td>{t.type}</td>
                    <td className="num">{formatMoney(t.amount)}</td>
                    <td>{t.origin_account}</td>
                    <td>{t.dest_account}</td>
                    <td className="num">{t.risk_score == null ? <span className="muted">Not scored</span> : formatScore(t.risk_score)}</td>
                    <td>{t.risk_level ? <LevelBadge level={t.risk_level} /> : <span className="muted">–</span>}</td>
                    <td>{t.has_open_alert ? "Yes" : <span className="muted">No</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} pageSize={PAGE_SIZE} total={txs.data.total} onPage={(p) => update({ page: String(p) }, true)} />
        </>
      )}
    </div>
  );
}
