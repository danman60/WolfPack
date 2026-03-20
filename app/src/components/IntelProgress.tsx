"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

const STAGES = [
  { label: "Fetching market data", icon: "~", pct: 10, duration: 5000 },
  { label: "Running quantitative modules", icon: "~", pct: 25, duration: 8000 },
  { label: "Quant agent analyzing", icon: "~", pct: 40, duration: 10000 },
  { label: "Snoop scanning social feeds", icon: "~", pct: 55, duration: 10000 },
  { label: "Sage forecasting outlook", icon: "~", pct: 70, duration: 8000 },
  { label: "Brief synthesizing signals", icon: "~", pct: 85, duration: 10000 },
  { label: "Storing results", icon: "~", pct: 95, duration: 4000 },
];

/**
 * Animated intelligence progress bar.
 * Shows fake-but-realistic progress stages during the ~60s intelligence cycle.
 * Disappears when `running` becomes false.
 */
export function IntelProgress({ running }: { running: boolean }) {
  const [stageIdx, setStageIdx] = useState(0);
  const [smoothPct, setSmoothPct] = useState(0);

  // Advance through stages
  useEffect(() => {
    if (!running) {
      setStageIdx(0);
      setSmoothPct(0);
      return;
    }

    setSmoothPct(STAGES[0].pct);
    let idx = 0;
    const timers: ReturnType<typeof setTimeout>[] = [];

    let elapsed = 0;
    for (let i = 0; i < STAGES.length; i++) {
      elapsed += STAGES[i].duration;
      timers.push(
        setTimeout(() => {
          idx = Math.min(i + 1, STAGES.length - 1);
          setStageIdx(idx);
          setSmoothPct(STAGES[idx].pct);
        }, elapsed)
      );
    }

    return () => timers.forEach(clearTimeout);
  }, [running]);

  return (
    <AnimatePresence>
      {running && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
          transition={{ duration: 0.4, ease: "easeInOut" }}
          className="overflow-hidden"
        >
          <div className="wolf-card p-5 mb-5 border-[var(--wolf-amber)]/20">
            {/* Header */}
            <div className="flex items-center gap-3 mb-4">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                className="w-5 h-5 border-2 border-[var(--wolf-amber)] border-t-transparent rounded-full"
              />
              <span className="text-sm font-semibold text-[var(--wolf-amber)]">
                Intelligence Cycle Running
              </span>
              <span className="ml-auto text-xs text-gray-500 font-mono tabular-nums">
                {smoothPct}%
              </span>
            </div>

            {/* Progress bar */}
            <div className="relative h-2 bg-[var(--surface)] rounded-full overflow-hidden mb-4">
              <motion.div
                className="absolute inset-y-0 left-0 rounded-full"
                animate={{ width: `${smoothPct}%` }}
                transition={{ duration: 1.2, ease: "easeOut" }}
                style={{
                  background: "linear-gradient(90deg, var(--wolf-amber), var(--wolf-emerald))",
                }}
              />
              {/* Shimmer overlay */}
              <motion.div
                className="absolute inset-0 rounded-full"
                animate={{ x: ["-100%", "200%"] }}
                transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                style={{
                  background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.08), transparent)",
                  width: "40%",
                }}
              />
            </div>

            {/* Stage indicators */}
            <div className="grid grid-cols-4 gap-2">
              {STAGES.slice(0, 4).map((stage, i) => {
                const isActive = stageIdx === i;
                const isDone = stageIdx > i;
                return (
                  <motion.div
                    key={stage.label}
                    animate={{
                      opacity: isDone ? 0.5 : isActive ? 1 : 0.3,
                    }}
                    className="flex items-center gap-2"
                  >
                    <div
                      className={`w-1.5 h-1.5 rounded-full transition-colors duration-500 ${
                        isDone
                          ? "bg-[var(--wolf-emerald)]"
                          : isActive
                          ? "bg-[var(--wolf-amber)]"
                          : "bg-gray-700"
                      }`}
                    />
                    <span className="text-[10px] text-gray-400 truncate">
                      {stage.label}
                    </span>
                  </motion.div>
                );
              })}
            </div>

            {/* Current stage detail */}
            <motion.p
              key={stageIdx}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className="text-xs text-gray-400 mt-3 text-center"
            >
              {STAGES[stageIdx]?.label}...
            </motion.p>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
