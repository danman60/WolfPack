import { ROTATION_STYLE } from "@/lib/rotation/contract";

export function MetricCard({ label, value, note, tone = "neutral", testId }: { label: string; value: string; note: string; tone?: "neutral" | "positive" | "negative"; testId?: string }) {
  return <section className={ROTATION_STYLE.panel} data-testid={testId}>
    <p className={ROTATION_STYLE.label}>{label}</p>
    <p className={`mt-3 mb-2 text-2xl md:text-3xl font-semibold tabular-nums break-words ${tone === "positive" ? "text-emerald-300" : tone === "negative" ? "text-red-300" : "text-white"}`}>{value}</p>
    <p className={ROTATION_STYLE.muted}>{note}</p>
  </section>;
}
