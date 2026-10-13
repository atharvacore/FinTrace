import { Link } from "react-router";
import type { Transaction } from "../api/types";
import { formatDateTime, formatMoney } from "../lib/format";

export function TransactionFacts({ tx, link = false }: { tx: Transaction; link?: boolean }) {
  return (
    <dl className="facts">
      <dt>Transaction</dt>
      <dd>{link ? <Link to={`/transactions/${tx.id}`}>#{tx.id}</Link> : `#${tx.id}`} {tx.external_id && <span className="muted small">({tx.external_id})</span>}</dd>
      <dt>Type</dt>
      <dd>{tx.type}</dd>
      <dt>Amount</dt>
      <dd>{formatMoney(tx.amount)}</dd>
      <dt>When</dt>
      <dd>
        {formatDateTime(tx.occurred_at)} <span className="muted small">(simulated hour {tx.step})</span>
      </dd>
      <dt>From</dt>
      <dd>
        <Link to={`/transactions?account=${encodeURIComponent(tx.origin_account)}`}>{tx.origin_account}</Link>{" "}
        <span className="muted small">
          balance {formatMoney(tx.origin_balance_before)} → {formatMoney(tx.origin_balance_after)}
        </span>
      </dd>
      <dt>To</dt>
      <dd>
        <Link to={`/transactions?account=${encodeURIComponent(tx.dest_account)}`}>{tx.dest_account}</Link>{" "}
        <span className="muted small">
          balance {formatMoney(tx.dest_balance_before)} → {formatMoney(tx.dest_balance_after)}
        </span>
      </dd>
      <dt>Source</dt>
      <dd>{tx.source === "csv" ? `CSV import #${tx.import_batch_id}` : "API"}</dd>
    </dl>
  );
}
