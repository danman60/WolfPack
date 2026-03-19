"use client";

import { usePredictionHistory } from "@/lib/hooks/usePredictions";
import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

/**
 * Prediction vs Reality Overlay — dual Y-axis chart showing actual price vs Brief confidence.
 */
export function PredictionOverlay() {
  const { data: predictions } = usePredictionHistory(7);

  if (!predictions || predictions.length === 0) {
    return (
      <div className="wolf-card p-6 text-center text-gray-500 text-sm">
        No prediction data yet. Run intelligence cycles to generate predictions.
      </div>
    );
  }

  const chartData = predictions.map((p) => ({
    time: new Date(p.predicted_at).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    }),
    price: p.price_at_prediction,
    priceAfter: p.price_after,
    conviction: p.predicted_conviction,
    outcome: p.outcome,
    pnl: p.pnl_pct,
  }));

  return (
    <div className="wolf-card p-5">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-1 h-4 rounded-full bg-[var(--wolf-cyan)]" />
        <h3 className="section-title">Prediction vs Reality</h3>
        <div className="flex gap-3 ml-auto text-[10px] text-gray-500">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-[var(--wolf-cyan)]" />
            Price
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-0.5 bg-[var(--wolf-amber)]" style={{ borderTop: "2px dashed var(--wolf-amber)" }} />
            Conviction
          </span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <ComposedChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis
            dataKey="time"
            tick={{ fill: "#6b7280", fontSize: 10 }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            yAxisId="price"
            orientation="left"
            tick={{ fill: "#6b7280", fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            domain={["auto", "auto"]}
            tickFormatter={(v: number) =>
              v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v.toFixed(0)
            }
          />
          <YAxis
            yAxisId="conviction"
            orientation="right"
            domain={[0, 100]}
            tick={{ fill: "#6b7280", fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => `${v}%`}
          />
          <Tooltip
            contentStyle={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: "8px",
              fontSize: "12px",
            }}
            labelStyle={{ color: "#9ca3af" }}
          />
          <Area
            yAxisId="price"
            type="monotone"
            dataKey="price"
            stroke="var(--wolf-cyan)"
            fill="var(--wolf-cyan)"
            fillOpacity={0.1}
            strokeWidth={2}
            name="Price at Prediction"
          />
          <Line
            yAxisId="conviction"
            type="monotone"
            dataKey="conviction"
            stroke="var(--wolf-amber)"
            strokeWidth={2}
            strokeDasharray="5 3"
            dot={false}
            name="Conviction %"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
