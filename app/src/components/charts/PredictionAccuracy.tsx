"use client";

import { usePredictionAccuracy } from "@/lib/hooks/usePredictions";
import { RadialBarChart, RadialBar, ResponsiveContainer } from "recharts";

/**
 * Prediction Accuracy Display — circular gauge + stats.
 */
export function PredictionAccuracy() {
  const { data } = usePredictionAccuracy(7);

  const accuracy = data?.accuracy_pct ?? 0;
  const total = data?.total_scored ?? 0;
  const correct = data?.correct ?? 0;
  const incorrect = data?.incorrect ?? 0;

  const chartData = [
    {
      name: "accuracy",
      value: accuracy,
      fill:
        accuracy >= 60
          ? "var(--wolf-emerald)"
          : accuracy >= 40
          ? "var(--wolf-amber)"
          : "var(--wolf-red)",
    },
  ];

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-[160px] h-[100px]">
        <ResponsiveContainer width="100%" height={100}>
          <RadialBarChart
            cx="50%"
            cy="100%"
            innerRadius="70%"
            outerRadius="100%"
            startAngle={180}
            endAngle={0}
            barSize={12}
            data={chartData}
          >
            <RadialBar
              dataKey="value"
              background={{ fill: "var(--surface)" }}
              cornerRadius={6}
            />
          </RadialBarChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-end pb-1">
          <span
            className="text-2xl font-bold"
            style={{
              color:
                accuracy >= 60
                  ? "var(--wolf-emerald)"
                  : accuracy >= 40
                  ? "var(--wolf-amber)"
                  : "var(--wolf-red)",
            }}
          >
            {accuracy}%
          </span>
        </div>
      </div>
      <div className="text-center mt-2">
        <div className="text-xs text-gray-400">7-Day Accuracy</div>
        <div className="flex gap-3 mt-1 text-[10px]">
          <span className="text-[var(--wolf-emerald)]">{correct} correct</span>
          <span className="text-[var(--wolf-red)]">{incorrect} wrong</span>
          <span className="text-gray-500">{total} total</span>
        </div>
      </div>
    </div>
  );
}
