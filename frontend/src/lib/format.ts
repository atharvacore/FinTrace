const money = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const integer = new Intl.NumberFormat("en-US");

export function formatMoney(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "–";
  return money.format(Number(value));
}

export function formatInt(value: number | null | undefined): string {
  return value === null || value === undefined ? "–" : integer.format(value);
}

export function formatScore(value: string | number | null | undefined, digits = 4): string {
  if (value === null || value === undefined) return "–";
  return Number(value).toFixed(digits);
}

export function formatPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  return `${(value * 100).toFixed(digits)}%`;
}

// Timestamps are shown in UTC: PaySim times are synthetic hours on a fixed calendar.
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "–";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return `${d.toISOString().slice(0, 16).replace("T", " ")} UTC`;
}

export function humanize(value: string | null | undefined): string {
  if (!value) return "–";
  const text = value.replace(/_/g, " ").toLowerCase();
  return text.charAt(0).toUpperCase() + text.slice(1);
}
