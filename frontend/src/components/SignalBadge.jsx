const GRADE = {
  STRONG_BUY:  { label: "강매수",   color: "#10b981" },
  BUY_QUEUE:   { label: "매수대기", color: "#7dd3fc" },
  HOLD:        { label: "관망",     color: "#6b7280" },
  SELL_QUEUE:  { label: "매도대기", color: "#fb923c" },
  SELL:        { label: "매도",     color: "#ef4444" },
};

export function SignalBadge({ grade }) {
  const { label, color } = GRADE[grade] ?? { label: grade, color: "#6b7280" };
  return (
    <div className="inline-flex items-center gap-2">
      <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: color }} />
      <span className="text-xs font-semibold tracking-wide" style={{ color }}>{label}</span>
    </div>
  );
}

export function gradeColor(grade) {
  return GRADE[grade]?.color ?? "#6b7280";
}
