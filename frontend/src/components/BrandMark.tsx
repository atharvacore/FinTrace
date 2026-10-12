/** The FinTrace mark: a ledger tile with a money trail that ends on a flagged node. */
export function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 34 34" aria-hidden="true">
      <rect x="0.75" y="0.75" width="32.5" height="32.5" rx="3" fill="none" stroke="currentColor" strokeOpacity="0.35" strokeWidth="1.5" />
      <path d="M6 24 L12 18 L17 21 L23 11" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="23" cy="11" r="3.2" fill="var(--signal)" />
      <circle cx="23" cy="11" r="6" fill="none" stroke="var(--signal)" strokeOpacity="0.5" strokeWidth="1" />
    </svg>
  );
}
