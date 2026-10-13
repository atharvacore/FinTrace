import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { ImportBatch, Page, ScoreRunResult } from "../api/types";
import { useUser } from "../auth/AuthContext";
import { Pagination } from "../components/Pagination";
import { Empty, ErrorState, InlineError, Loading } from "../components/States";
import { formatDateTime, formatInt, humanize } from "../lib/format";
import { hasRole } from "../lib/roles";
import { useSearchState } from "../lib/useSearchState";

const PAGE_SIZE = 20;
const MAX_MB = 50; // Same cap as the API (FINTRACE_MAX_UPLOAD_MB); larger files go through the CLI.

function ImportResult({ batch }: { batch: ImportBatch }) {
  return (
    <section className="card">
      <h2>
        Import #{batch.id}: {batch.filename}
        <span className={`badge status-${batch.status}`}>{humanize(batch.status)}</span>
      </h2>
      <div className="stats">
        {(
          [
            ["Rows read", batch.rows_total],
            ["Inserted", batch.rows_inserted],
            ["Duplicates skipped", batch.rows_duplicate],
            ["Rejected", batch.rows_rejected],
          ] as const
        ).map(([label, value]) => (
          <div key={label} className="stat stat-compact">
            <div className="stat-value">{formatInt(value)}</div>
            <div className="stat-label">{label}</div>
          </div>
        ))}
      </div>
      {batch.errors.length > 0 && (
        <>
          <h3>Rejected rows</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th className="num">Line</th>
                  <th>Problems</th>
                </tr>
              </thead>
              <tbody>
                {batch.errors.map((e) => (
                  <tr key={e.row}>
                    <td className="num">{e.row}</td>
                    <td>{e.errors.join("; ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {batch.errors_truncated && (
            <p className="muted small">Only the first {formatInt(batch.errors.length)} problems are kept.</p>
          )}
        </>
      )}
    </section>
  );
}

function UploadForm({ onDone }: { onDone: (batch: ImportBatch) => void }) {
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [tooBig, setTooBig] = useState(false);
  const upload = useMutation({
    mutationFn: (f: File) => {
      const form = new FormData();
      form.append("file", f);
      return api<ImportBatch>("/imports", { method: "POST", body: form });
    },
    onSuccess: (batch) => {
      queryClient.invalidateQueries({ queryKey: ["imports"] });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["metrics"] });
      setFile(null);
      if (input.current) input.current.value = "";
      onDone(batch);
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (file && !tooBig) upload.mutate(file);
  }

  return (
    <form className="card form" onSubmit={submit}>
      <h2>Upload a CSV</h2>
      <p className="muted small">
        PaySim format: <code>step,type,amount,nameOrig,oldbalanceOrg,newbalanceOrig,nameDest,oldbalanceDest,newbalanceDest,isFraud,isFlaggedFraud</code>.
        Every row is checked; bad rows are listed by line number and rows already imported are skipped. Up to {MAX_MB} MB;
        import bigger files with <code>python -m app.cli import-csv</code>.
      </p>
      <label>
        CSV file
        <input
          ref={input}
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => {
            const f = e.target.files?.[0] ?? null;
            setFile(f);
            setTooBig(!!f && f.size > MAX_MB * 1024 * 1024);
          }}
        />
      </label>
      {tooBig && <p className="inline-error">This file is over {MAX_MB} MB. Use the CLI import instead.</p>}
      <InlineError error={upload.error} />
      <div className="actions">
        <button type="submit" className="btn btn-primary" disabled={!file || tooBig || upload.isPending}>
          {upload.isPending ? "Importing…" : "Import"}
        </button>
      </div>
    </form>
  );
}

function ScoreButton() {
  const queryClient = useQueryClient();
  const run = useMutation({
    mutationFn: () => api<ScoreRunResult>("/scoring/run", { method: "POST", body: { limit: 5000 } }),
    onSuccess: () => {
      for (const key of ["metrics", "alerts", "transactions"]) queryClient.invalidateQueries({ queryKey: [key] });
    },
  });
  return (
    <section className="card">
      <h2>Score new transactions</h2>
      <p className="muted small">Scores up to 5,000 transactions the active model has not seen yet, oldest first, and raises alerts.</p>
      <div className="actions">
        <button type="button" className="btn" disabled={run.isPending} onClick={() => run.mutate()}>
          {run.isPending ? "Scoring…" : "Score next 5,000"}
        </button>
        {run.data && (
          <span role="status">
            Scored {formatInt(run.data.scored)} with {run.data.model_version}, {formatInt(run.data.alerts_created)} new alerts,{" "}
            {formatInt(run.data.remaining_unscored)} still unscored.
          </span>
        )}
      </div>
      <InlineError error={run.error} />
    </section>
  );
}

export function ImportsPage() {
  const user = useUser();
  const { page, update } = useSearchState();
  const [latest, setLatest] = useState<ImportBatch | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const canUpload = hasRole(user, "senior_analyst");

  const history = useQuery({
    queryKey: ["imports", page],
    queryFn: () => api<Page<ImportBatch>>("/imports", { query: { page, page_size: PAGE_SIZE } }),
    placeholderData: keepPreviousData,
  });
  const detail = useQuery({
    queryKey: ["imports", "detail", openId],
    queryFn: () => api<ImportBatch>(`/imports/${openId}`),
    enabled: openId !== null,
  });

  return (
    <div className="page">
      <header className="page-head">
        <h1>Imports</h1>
        <p className="muted">
          Bring synthetic transactions in from CSV files. {canUpload ? "" : "Senior analysts and admins can upload; you can see the history."}
        </p>
      </header>

      {canUpload && (
        <div className="grid-2">
          <UploadForm
            onDone={(batch) => {
              setLatest(batch);
              setOpenId(null);
            }}
          />
          <ScoreButton />
        </div>
      )}
      {latest && <ImportResult batch={latest} />}

      {history.isPending ? (
        <Loading />
      ) : history.isError ? (
        <ErrorState error={history.error} onRetry={() => history.refetch()} />
      ) : history.data.items.length === 0 ? (
        <Empty title="No imports yet">Upload a CSV above, or run <code>python -m app.cli import-csv</code>.</Empty>
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th className="num">ID</th>
                  <th>File</th>
                  <th>Status</th>
                  <th className="num">Read</th>
                  <th className="num">Inserted</th>
                  <th className="num">Duplicates</th>
                  <th className="num">Rejected</th>
                  <th>When</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {history.data.items.map((b) => (
                  <tr key={b.id} className={openId === b.id ? "highlight" : undefined}>
                    <td className="num">#{b.id}</td>
                    <td>
                      {b.filename}
                      <div className="muted small mono" title={b.file_sha256}>
                        sha256 {b.file_sha256.slice(0, 12)}…
                      </div>
                    </td>
                    <td>
                      <span className={`badge status-${b.status}`}>{humanize(b.status)}</span>
                    </td>
                    <td className="num">{formatInt(b.rows_total)}</td>
                    <td className="num">{formatInt(b.rows_inserted)}</td>
                    <td className="num">{formatInt(b.rows_duplicate)}</td>
                    <td className="num">{formatInt(b.rows_rejected)}</td>
                    <td className="nowrap">{formatDateTime(b.created_at)}</td>
                    <td>
                      {b.rows_rejected > 0 && (
                        <button type="button" className="btn btn-small" onClick={() => setOpenId(openId === b.id ? null : b.id)}>
                          {openId === b.id ? "Hide problems" : "Show problems"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} pageSize={PAGE_SIZE} total={history.data.total} onPage={(p) => update({ page: String(p) }, true)} />
        </>
      )}

      {openId !== null && detail.isPending && <Loading />}
      {openId !== null && detail.isError && <ErrorState error={detail.error} onRetry={() => detail.refetch()} />}
      {openId !== null && detail.data && <ImportResult batch={detail.data} />}
    </div>
  );
}
