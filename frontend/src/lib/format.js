// ─── numeric formatters ──────────────────────────────────────

export const fmt = {
  marketCap(n) {
    if (n == null || isNaN(n)) return "—";
    if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
    if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
    if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
    return `$${n.toLocaleString()}`;
  },

  price(n) {
    if (n == null || isNaN(n)) return "—";
    return `$${n.toFixed(2)}`;
  },

  percent(n, digits = 2) {
    if (n == null || isNaN(n)) return "—";
    const sign = n > 0 ? "+" : "";
    return `${sign}${n.toFixed(digits)}%`;
  },

  pct(n, digits = 2) {
    if (n == null || isNaN(n)) return "—";
    const sign = n > 0 ? "+" : "";
    return `${sign}${n.toFixed(digits)}`;
  },

  num(n, digits = 2) {
    if (n == null || isNaN(n)) return "—";
    return n.toFixed(digits);
  },

  signed(n) {
    if (n == null) return "0";
    return n > 0 ? `+${n}` : `${n}`;
  },
};

// Tailwind class for a positive/negative numeric value.
export function trendClass(n, invert = false) {
  if (n == null) return "text-gray-400";
  const pos = invert ? n < 0 : n > 0;
  const neg = invert ? n > 0 : n < 0;
  if (pos) return "text-up";
  if (neg) return "text-down";
  return "text-gray-300";
}
