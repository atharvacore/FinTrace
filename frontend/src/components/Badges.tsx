import type { AlertStatus, CaseStatus, RiskLevel } from "../api/types";
import { humanize } from "../lib/format";

export function LevelBadge({ level }: { level: RiskLevel }) {
  return <span className={`badge level-${level}`}>{humanize(level)}</span>;
}

export function StatusBadge({ status }: { status: AlertStatus | CaseStatus }) {
  return <span className={`badge status-${status}`}>{humanize(status)}</span>;
}

export function ReasonCodes({ codes }: { codes: string[] }) {
  if (codes.length === 0) return <span className="muted">–</span>;
  return (
    <span className="codes">
      {codes.map((code) => (
        <code key={code} className="code">
          {code}
        </code>
      ))}
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
