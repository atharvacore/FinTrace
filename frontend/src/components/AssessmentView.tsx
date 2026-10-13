import type { Assessment } from "../api/types";
import { formatDateTime, formatScore, humanize } from "../lib/format";
import { LevelBadge, ReasonCodes } from "./Badges";

export function AssessmentView({ assessment }: { assessment: Assessment }) {
  return (
    <div>
      <dl className="facts">
        <dt>Risk score</dt>
        <dd>
          <strong>{formatScore(assessment.risk_score, 5)}</strong> <LevelBadge level={assessment.risk_level} />
        </dd>
        <dt>Model version</dt>
        <dd>
          <code>{assessment.model_version}</code>
        </dd>
        <dt>Scored at</dt>
        <dd>{formatDateTime(assessment.scored_at)}</dd>
        <dt>Reason codes</dt>
        <dd>
          <ReasonCodes codes={assessment.reason_codes} />
        </dd>
      </dl>
      <h3>Rule hits</h3>
      {assessment.rule_hits.length === 0 ? (
        <p className="muted">No monitoring rule fired.</p>
      ) : (
        <ul className="list">
          {assessment.rule_hits.map((hit) => (
            <li key={hit.code}>
              <code>{hit.code}</code> {hit.name} <span className="muted">({humanize(hit.severity)})</span>
              <div className="muted small">{hit.detail}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
