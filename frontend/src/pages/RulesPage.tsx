import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import type { RiskLevel, Rule } from "../api/types";
import { useUser } from "../auth/AuthContext";
import { LevelBadge } from "../components/Badges";
import { Empty, ErrorState, InlineError, Loading } from "../components/States";
import { formatDateTime, humanize } from "../lib/format";
import { hasRole } from "../lib/roles";

function RuleEditor({ rule, onDone }: { rule: Rule; onDone: () => void }) {
  const queryClient = useQueryClient();
  const [severity, setSeverity] = useState<RiskLevel>(rule.severity);
  const [enabled, setEnabled] = useState(rule.enabled);
  const [params, setParams] = useState(JSON.stringify(rule.parameters, null, 2));
  const [parseError, setParseError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: (parameters: Record<string, unknown>) =>
      api<Rule>(`/rules/${rule.id}`, { method: "PATCH", body: { severity, enabled, parameters } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rules"] });
      onDone();
    },
  });

  return (
    <form
      className="form"
      onSubmit={(e) => {
        e.preventDefault();
        try {
          const parsed = JSON.parse(params) as Record<string, unknown>;
          setParseError(null);
          save.mutate(parsed);
        } catch {
          setParseError("Parameters must be valid JSON.");
        }
      }}
    >
      <label>
        Severity
        <select value={severity} onChange={(e) => setSeverity(e.target.value as RiskLevel)}>
          {(["low", "medium", "high", "critical"] as RiskLevel[]).map((s) => (
            <option key={s} value={s}>
              {humanize(s)}
            </option>
          ))}
        </select>
      </label>
      <label className="check">
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} /> Enabled
      </label>
      <label>
        Parameters (JSON)
        <textarea rows={5} className="mono" value={params} onChange={(e) => setParams(e.target.value)} />
      </label>
      <InlineError error={parseError ?? save.error} />
      <div className="actions">
        <button type="submit" className="btn btn-primary" disabled={save.isPending}>
          Save
        </button>
        <button type="button" className="btn" onClick={onDone}>
          Cancel
        </button>
      </div>
    </form>
  );
}

export function RulesPage() {
  const user = useUser();
  const admin = hasRole(user, "admin");
  const [editing, setEditing] = useState<number | null>(null);
  const rules = useQuery({ queryKey: ["rules"], queryFn: () => api<Rule[]>("/rules") });

  return (
    <div className="page">
      <header className="page-head">
        <h1>Monitoring rules</h1>
        <p className="muted">
          Rules add reason codes and can raise the risk level. Only rules with high or critical severity raise alerts on their own.
          {admin ? " Changes apply to the next scoring run and are audited." : " Only admins can change rules."}
        </p>
      </header>
      {rules.isPending ? (
        <Loading />
      ) : rules.isError ? (
        <ErrorState error={rules.error} onRetry={() => rules.refetch()} />
      ) : rules.data.length === 0 ? (
        <Empty title="No rules configured" />
      ) : (
        <div className="cards">
          {rules.data.map((rule) => (
            <section key={rule.id} className="card">
              <h2>
                {rule.name} <LevelBadge level={rule.severity} /> {!rule.enabled && <span className="badge">Disabled</span>}
              </h2>
              <p className="muted">
                <code>{rule.code}</code> ({rule.rule_type}). {rule.description}
              </p>
              {editing === rule.id ? (
                <RuleEditor rule={rule} onDone={() => setEditing(null)} />
              ) : (
                <>
                  <pre className="mono small">{JSON.stringify(rule.parameters, null, 2)}</pre>
                  <p className="muted small">Updated {formatDateTime(rule.updated_at)}</p>
                  {admin && (
                    <button type="button" className="btn" onClick={() => setEditing(rule.id)}>
                      Edit
                    </button>
                  )}
                </>
              )}
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
