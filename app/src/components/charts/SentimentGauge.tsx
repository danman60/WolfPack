"use client";

/**
 * Sentiment Gauge — semicircle SVG gauge showing Brief agent's directional conviction.
 * Range: -100 (strong SELL/red) to +100 (strong BUY/green).
 */
export function SentimentGauge({ value, label }: { value: number; label?: string }) {
  // Clamp to [-100, 100]
  const clamped = Math.max(-100, Math.min(100, value));
  // Map to angle: -100 -> 180°, 0 -> 90°, 100 -> 0°
  const angle = 180 - ((clamped + 100) / 200) * 180;
  const radians = (angle * Math.PI) / 180;

  // Needle endpoint (center at 100,100, radius 70)
  const nx = 100 + 70 * Math.cos(radians);
  const ny = 100 - 70 * Math.sin(radians);

  // Color based on value
  const color =
    clamped > 30
      ? "var(--wolf-emerald)"
      : clamped < -30
      ? "var(--wolf-red)"
      : "var(--wolf-amber)";

  const sentiment =
    clamped > 50
      ? "Strong Buy"
      : clamped > 20
      ? "Buy"
      : clamped < -50
      ? "Strong Sell"
      : clamped < -20
      ? "Sell"
      : "Neutral";

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 200 120" width="200" height="120">
        {/* Background arc */}
        <path
          d="M 10 100 A 90 90 0 0 1 190 100"
          fill="none"
          stroke="var(--surface)"
          strokeWidth="16"
          strokeLinecap="round"
        />
        {/* Red zone (left) */}
        <path
          d="M 10 100 A 90 90 0 0 1 55 30"
          fill="none"
          stroke="rgba(239,68,68,0.3)"
          strokeWidth="16"
          strokeLinecap="round"
        />
        {/* Yellow zone (center) */}
        <path
          d="M 55 30 A 90 90 0 0 1 145 30"
          fill="none"
          stroke="rgba(245,158,11,0.3)"
          strokeWidth="16"
          strokeLinecap="round"
        />
        {/* Green zone (right) */}
        <path
          d="M 145 30 A 90 90 0 0 1 190 100"
          fill="none"
          stroke="rgba(16,185,129,0.3)"
          strokeWidth="16"
          strokeLinecap="round"
        />
        {/* Needle */}
        <line
          x1="100"
          y1="100"
          x2={nx}
          y2={ny}
          stroke={color}
          strokeWidth="3"
          strokeLinecap="round"
        />
        {/* Center dot */}
        <circle cx="100" cy="100" r="5" fill={color} />
        {/* Labels */}
        <text x="10" y="115" fill="#9ca3af" fontSize="10" textAnchor="start">
          SELL
        </text>
        <text x="190" y="115" fill="#9ca3af" fontSize="10" textAnchor="end">
          BUY
        </text>
      </svg>
      <div className="text-center -mt-1">
        <div className="text-lg font-bold" style={{ color }}>
          {sentiment}
        </div>
        <div className="text-xs text-gray-500">
          {label ?? "Brief Conviction"}: {clamped > 0 ? "+" : ""}
          {clamped}
        </div>
      </div>
    </div>
  );
}
