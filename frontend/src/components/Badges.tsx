import type { AlertStatus, CaseStatus, RiskLevel } from "../api/types";
import { humanize } from "../lib/format";

const LEVEL_PIPS: Record<RiskLevel, number> = { low: 1, medium: 2, high: 3, critical: 4 };

/** Risk level as a badge with 1-4 pips, so the level reads without relying on colour. */
export function LevelBadge({ level }: { level: RiskLevel }) {
  const on = LEVEL_PIPS[level] ?? 0;
  return (
    <span className={`badge level-${level}`}>
      <span className="pips" aria-hidden="true">
        {[1, 2, 3, 4].map((n) => (
          <i key={n} className={n <= on ? "on" : undefined} />
        ))}
      </span>
      {humanize(level)}
    </span>
  );
}

export function StatusBadge({ status }: { status: AlertStatus | CaseStatus }) {
  return <span className={`badge status-${status}`}>{humanize(status)}</span>;
}

/** Reason codes as chips. In tables, `max` keeps rows short: the rest collapse into a "+N" chip with a tooltip. */
export function ReasonCodes({ codes, max }: { codes: string[]; max?: number }) {
  if (codes.length === 0) return <span className="muted">–</span>;
  const shown = max === undefined ? codes : codes.slice(0, max);
  const hidden = codes.slice(shown.length);
  return (
    <span className="codes">
      {shown.map((code) => (
        <code key={code} className="code">
          {code}
        </code>
      ))}
      {hidden.length > 0 && (
        <span className="code code-more" title={hidden.join(", ")}>
          +{hidden.length} more
        </span>
      )}
    </span>
  );
}

export function SyntheticLabel({ value }: { value: boolean | null | undefined }) {
  if (value === null || value === undefined) return <span className="muted">No label</span>;
  return (
    <span className={`badge ${value ? "label-fraud" : "label-legit"}`} title="Synthetic dataset label, not an investigation outcome">
      Synthetic label: {value ? "fraud" : "not fraud"}
    </span>
  );
}
