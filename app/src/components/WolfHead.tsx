"use client";

/**
 * 3D Animated Wireframe Wolf Heads — one per agent.
 *
 * Each wolf has a distinct personality expressed through geometry,
 * animation style, and color:
 *   - Quant: sharp, geometric, precise rotation (cyan)
 *   - Snoop: alert, ears up, scanning pulse (amber)
 *   - Sage:  calm, wise, slow breathing glow (purple)
 *   - Brief: bold, alpha, commanding pulse (emerald)
 */

import { type CSSProperties } from "react";

type AgentKey = "quant" | "snoop" | "sage" | "brief";

interface WolfHeadProps {
  agent: AgentKey;
  size?: number;
  className?: string;
}

const AGENT_COLORS: Record<AgentKey, string> = {
  quant: "var(--wolf-cyan)",
  snoop: "var(--wolf-amber)",
  sage: "var(--wolf-purple)",
  brief: "var(--wolf-emerald)",
};

const AGENT_LABELS: Record<AgentKey, string> = {
  quant: "The Quant",
  snoop: "The Snoop",
  sage: "The Sage",
  brief: "The Brief",
};

export function WolfHead({ agent, size = 48, className = "" }: WolfHeadProps) {
  const color = AGENT_COLORS[agent];

  return (
    <div
      className={`wolf-head wolf-head-${agent} ${className}`}
      style={
        {
          width: size,
          height: size,
          "--wolf-color": color,
          perspective: "200px",
        } as CSSProperties
      }
      title={AGENT_LABELS[agent]}
    >
      <div className={`wolf-head-inner wolf-anim-${agent}`}>
        <svg
          viewBox="0 0 64 64"
          width={size}
          height={size}
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Glow filter */}
          <defs>
            <filter id={`glow-${agent}`} x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="1.5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <g
            filter={`url(#glow-${agent})`}
            stroke={color}
            strokeWidth="1.2"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity="0.9"
          >
            {getWolfPaths(agent)}
          </g>
        </svg>
      </div>
    </div>
  );
}

function getWolfPaths(agent: AgentKey) {
  switch (agent) {
    case "quant":
      return <QuantWolf />;
    case "snoop":
      return <SnoopWolf />;
    case "sage":
      return <SageWolf />;
    case "brief":
      return <BriefWolf />;
  }
}

/** Quant — sharp angles, data-driven, crystalline geometry */
function QuantWolf() {
  return (
    <>
      {/* Left ear — sharp angular */}
      <path d="M14 8 L20 22 L10 24 Z" />
      <path d="M14 8 L18 14" />
      {/* Right ear — sharp angular */}
      <path d="M50 8 L44 22 L54 24 Z" />
      <path d="M50 8 L46 14" />
      {/* Head outline — faceted/geometric */}
      <path d="M10 24 L14 36 L20 42 L32 48 L44 42 L50 36 L54 24" />
      {/* Forehead ridge */}
      <path d="M20 22 L32 18 L44 22" />
      {/* Brow line */}
      <path d="M16 28 L24 26 L32 28 L40 26 L48 28" />
      {/* Eyes — diamond/precise */}
      <path d="M20 30 L24 28 L28 30 L24 32 Z" />
      <path d="M36 30 L40 28 L44 30 L40 32 Z" />
      {/* Eye pupils — dots */}
      <circle cx="24" cy="30" r="1" fill="var(--wolf-color)" />
      <circle cx="40" cy="30" r="1" fill="var(--wolf-color)" />
      {/* Nose bridge — straight line */}
      <path d="M32 28 L32 37" />
      {/* Nose */}
      <path d="M29 37 L32 40 L35 37" />
      {/* Muzzle — angular */}
      <path d="M24 38 L29 37 L32 40 L35 37 L40 38" />
      {/* Jaw */}
      <path d="M20 42 L28 44 L32 48 L36 44 L44 42" />
      {/* Cross-hatching (data grid lines) */}
      <path d="M22 34 L26 36" strokeOpacity="0.3" />
      <path d="M42 34 L38 36" strokeOpacity="0.3" />
      <path d="M28 24 L36 24" strokeOpacity="0.2" />
    </>
  );
}

/** Snoop — alert posture, tall ears, scanning/surveillance feel */
function SnoopWolf() {
  return (
    <>
      {/* Left ear — tall, alert, radar-dish */}
      <path d="M12 4 L16 6 L18 22 L8 22 Z" />
      <path d="M10 12 L16 14" strokeOpacity="0.4" />
      <path d="M10 16 L17 18" strokeOpacity="0.3" />
      {/* Right ear — tall, alert, slightly turned */}
      <path d="M52 4 L48 6 L46 22 L56 22 Z" />
      <path d="M54 12 L48 14" strokeOpacity="0.4" />
      <path d="M54 16 L47 18" strokeOpacity="0.3" />
      {/* Head outline — sleek, attentive */}
      <path d="M8 22 L12 34 L18 40 L32 46 L46 40 L52 34 L56 22" />
      {/* Forehead */}
      <path d="M18 22 L32 19 L46 22" />
      {/* Brow — arched, alert */}
      <path d="M14 27 L22 24 L28 27" />
      <path d="M36 27 L42 24 L50 27" />
      {/* Eyes — wide, scanning, circular */}
      <circle cx="23" cy="29" r="4" />
      <circle cx="41" cy="29" r="4" />
      {/* Iris rings */}
      <circle cx="23" cy="29" r="2" />
      <circle cx="41" cy="29" r="2" />
      {/* Pupils */}
      <circle cx="23" cy="29" r="0.8" fill="var(--wolf-color)" />
      <circle cx="41" cy="29" r="0.8" fill="var(--wolf-color)" />
      {/* Nose */}
      <path d="M32 28 L32 36" />
      <path d="M28 36 L32 39 L36 36" />
      {/* Muzzle */}
      <path d="M22 36 L28 36 L32 39 L36 36 L42 36" />
      {/* Jaw */}
      <path d="M18 40 L26 43 L32 46 L38 43 L46 40" />
      {/* Signal waves from ears */}
      <path d="M6 8 Q4 14 6 20" strokeOpacity="0.25" strokeDasharray="2 2" />
      <path d="M58 8 Q60 14 58 20" strokeOpacity="0.25" strokeDasharray="2 2" />
    </>
  );
}

/** Sage — calm, wise, heavy brow, noble proportions */
function SageWolf() {
  return (
    <>
      {/* Left ear — moderate, dignified */}
      <path d="M14 10 L20 22 L8 24 Z" />
      {/* Right ear */}
      <path d="M50 10 L44 22 L56 24 Z" />
      {/* Head outline — broader, heavier */}
      <path d="M8 24 L10 36 L18 44 L32 50 L46 44 L54 36 L56 24" />
      {/* Forehead — prominent, wise */}
      <path d="M18 22 L26 18 L32 16 L38 18 L46 22" />
      <path d="M22 20 L32 17 L42 20" strokeOpacity="0.3" />
      {/* Heavy brow ridge */}
      <path d="M12 28 L20 25 L26 28" strokeWidth="1.5" />
      <path d="M38 28 L44 25 L52 28" strokeWidth="1.5" />
      {/* Eyes — half-lidded, contemplative */}
      <path d="M18 30 L22 28 L26 30 L22 31 Z" />
      <path d="M38 30 L42 28 L46 30 L42 31 Z" />
      <circle cx="22" cy="29.5" r="0.7" fill="var(--wolf-color)" />
      <circle cx="42" cy="29.5" r="0.7" fill="var(--wolf-color)" />
      {/* Nose */}
      <path d="M32 28 L32 38" />
      <path d="M28 38 L32 42 L36 38" />
      {/* Muzzle — broad, strong */}
      <path d="M20 38 L28 38 L32 42 L36 38 L44 38" />
      {/* Jaw — pronounced */}
      <path d="M18 44 L24 46 L32 50 L40 46 L46 44" />
      {/* Wisdom lines — subtle forehead markings */}
      <path d="M24 22 L28 20 L32 22" strokeOpacity="0.2" />
      <path d="M32 22 L36 20 L40 22" strokeOpacity="0.2" />
      {/* Third eye mark */}
      <circle cx="32" cy="22" r="1.5" strokeOpacity="0.3" />
    </>
  );
}

/** Brief — alpha wolf, commanding, bold lines */
function BriefWolf() {
  return (
    <>
      {/* Left ear — strong, angled back */}
      <path d="M10 6 L18 20 L6 22 Z" strokeWidth="1.4" />
      {/* Right ear */}
      <path d="M54 6 L46 20 L58 22 Z" strokeWidth="1.4" />
      {/* Head outline — powerful, wide */}
      <path d="M6 22 L10 36 L18 42 L32 48 L46 42 L54 36 L58 22" strokeWidth="1.4" />
      {/* Forehead — bold V */}
      <path d="M18 20 L32 14 L46 20" strokeWidth="1.4" />
      {/* Crown mark */}
      <path d="M26 16 L32 12 L38 16" strokeOpacity="0.5" />
      {/* Brow — intense, angular */}
      <path d="M12 28 L22 24 L28 28" strokeWidth="1.5" />
      <path d="M36 28 L42 24 L52 28" strokeWidth="1.5" />
      {/* Eyes — fierce, narrow */}
      <path d="M17 30 L23 27 L29 30" strokeWidth="1.3" />
      <path d="M35 30 L41 27 L47 30" strokeWidth="1.3" />
      {/* Eye glint */}
      <circle cx="23" cy="29" r="1.2" fill="var(--wolf-color)" />
      <circle cx="41" cy="29" r="1.2" fill="var(--wolf-color)" />
      {/* Nose bridge — strong */}
      <path d="M32 26 L32 36" strokeWidth="1.3" />
      {/* Nose */}
      <path d="M27 36 L32 40 L37 36 Z" />
      {/* Muzzle — wide, powerful */}
      <path d="M20 38 L27 36 L32 40 L37 36 L44 38" strokeWidth="1.3" />
      {/* Jaw — strong */}
      <path d="M18 42 L26 45 L32 48 L38 45 L46 42" strokeWidth="1.3" />
      {/* Fangs hint */}
      <path d="M26 42 L27 45" strokeOpacity="0.4" />
      <path d="M38 42 L37 45" strokeOpacity="0.4" />
      {/* Neck/mane lines */}
      <path d="M14 38 L10 46" strokeOpacity="0.3" />
      <path d="M50 38 L54 46" strokeOpacity="0.3" />
    </>
  );
}

/** Export agent keys and colors for reuse */
export const WOLF_AGENTS: { key: AgentKey; label: string; color: string }[] = [
  { key: "quant", label: "The Quant", color: "var(--wolf-cyan)" },
  { key: "snoop", label: "The Snoop", color: "var(--wolf-amber)" },
  { key: "sage", label: "The Sage", color: "var(--wolf-purple)" },
  { key: "brief", label: "The Brief", color: "var(--wolf-emerald)" },
];
