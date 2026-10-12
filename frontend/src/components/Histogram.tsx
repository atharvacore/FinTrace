import { useState } from "react";
import type { RiskDistribution } from "../api/types";
import { formatInt, formatScore } from "../lib/format";

/** Risk-score histogram with the alert threshold marked. Log scale by default: most scores are tiny. */
export function Histogram({ data }: { data: RiskDistribution }) {
  const [log, setLog] = useState(true);
  const width = 640;
  const height = 220;
  const pad = { top: 12, right: 12, bottom: 34, left: 48 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const scale = (n: number) => (log ? Math.log10(n + 1) : n);
  const max = Math.max(1, ...data.bins.map((b) => scale(b.count)));
  const barW = innerW / data.bins.length;
  const threshold = Number(data.threshold);

  return (
    <figure className="chart">
      <div className="chart-head">
        <figcaption>
          Latest score per transaction ({formatInt(data.transactions)} scored by {data.model_version})
        </figcaption>
        <label className="toggle">
          <input type="checkbox" checked={log} onChange={(e) => setLog(e.target.checked)} /> Log scale
        </label>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Histogram of risk scores">
        <g transform={`translate(${pad.left},${pad.top})`}>
          <line x1={0} y1={innerH} x2={innerW} y2={innerH} className="axis" />
          {data.bins.map((bin, i) => {
            const h = (scale(bin.count) / max) * innerH;
            const fh = bin.count ? (h * bin.labelled_fraud) / bin.count : 0;
            return (
              <g key={bin.lower}>
                <title>
                  {`${formatScore(bin.lower, 2)}–${formatScore(bin.upper, 2)}: ${formatInt(bin.count)} transactions, ${formatInt(bin.labelled_fraud)} with synthetic fraud label`}
                </title>
                <rect x={i * barW + 1} y={innerH - h} width={Math.max(barW - 2, 1)} height={h} className="bar" />
                {!log && fh > 0 && (
                  <rect x={i * barW + 1} y={innerH - fh} width={Math.max(barW - 2, 1)} height={fh} className="bar-fraud" />
                )}
              </g>
            );
          })}
          <line x1={threshold * innerW} x2={threshold * innerW} y1={0} y2={innerH} className="threshold" />
          {[0, 0.25, 0.5, 0.75, 1].map((t) => (
            <text key={t} x={t * innerW} y={innerH + 16} className="tick" textAnchor="middle">
              {t}
            </text>
          ))}
          <text x={innerW / 2} y={innerH + 30} className="tick" textAnchor="middle">
            Risk score
          </text>
          <text x={-8} y={8} className="tick" textAnchor="end">
            {log ? "log" : formatInt(max)}
          </text>
        </g>
      </svg>
      <p className="muted small">
        Dashed line: alert threshold {formatScore(data.threshold)} ({formatInt(data.above_threshold)} transactions at
        or above it).{" "}
        {log ? "Switch off log scale to see synthetic fraud labels per bar." : "Darker part: synthetic fraud label."}
      </p>
    </figure>
  );
}
