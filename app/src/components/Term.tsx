"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { glossary, CATEGORY_COLORS, CATEGORY_LABELS } from "@/lib/glossary";

/**
 * <Term id="leverage">Leverage</Term>
 *
 * Wraps inline text with a hover tooltip that explains the term in plain English.
 * - Dotted underline hints at interactivity
 * - Framer Motion spring animation on hover
 * - Smart positioning (above by default, flips below near viewport top)
 * - Mobile: tap to show, tap elsewhere to dismiss
 */
export function Term({
  id,
  children,
}: {
  id: string;
  children: React.ReactNode;
}) {
  const entry = glossary[id];
  if (!entry) return <>{children}</>;

  const [open, setOpen] = useState(false);
  const [above, setAbove] = useState(true);
  const triggerRef = useRef<HTMLSpanElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const categoryColor = CATEGORY_COLORS[entry.category];
  const categoryLabel = CATEGORY_LABELS[entry.category];

  const show = useCallback(() => {
    clearTimeout(timeoutRef.current);
    // Check if near top of viewport — flip tooltip below if so
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setAbove(rect.top > 160);
    }
    setOpen(true);
  }, []);

  const hide = useCallback(() => {
    timeoutRef.current = setTimeout(() => setOpen(false), 120);
  }, []);

  const keepOpen = useCallback(() => {
    clearTimeout(timeoutRef.current);
  }, []);

  // Close on outside click (mobile)
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent | TouchEvent) => {
      if (
        triggerRef.current?.contains(e.target as Node) ||
        tooltipRef.current?.contains(e.target as Node)
      )
        return;
      setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    document.addEventListener("touchstart", handler);
    return () => {
      document.removeEventListener("mousedown", handler);
      document.removeEventListener("touchstart", handler);
    };
  }, [open]);

  // Cleanup timeout on unmount
  useEffect(() => () => clearTimeout(timeoutRef.current), []);

  return (
    <span className="relative inline">
      <span
        ref={triggerRef}
        onMouseEnter={show}
        onMouseLeave={hide}
        onClick={() => setOpen((o) => !o)}
        className="cursor-help border-b border-dotted border-gray-600 hover:border-gray-400 transition-colors duration-200"
      >
        {children}
      </span>

      <AnimatePresence>
        {open && (
          <motion.div
            ref={tooltipRef}
            initial={{ opacity: 0, y: above ? 6 : -6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: above ? 4 : -4, scale: 0.98 }}
            transition={{
              type: "spring",
              stiffness: 380,
              damping: 24,
              mass: 0.8,
            }}
            onMouseEnter={keepOpen}
            onMouseLeave={hide}
            className={`absolute z-[100] w-72 ${
              above ? "bottom-full mb-2.5" : "top-full mt-2.5"
            } left-1/2 -translate-x-1/2`}
          >
            <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)]/95 backdrop-blur-xl shadow-2xl shadow-black/40 p-3.5 text-left">
              {/* Category pill + term */}
              <div className="flex items-center gap-2 mb-2">
                <span
                  className="px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider"
                  style={{
                    color: categoryColor,
                    backgroundColor: `color-mix(in srgb, ${categoryColor} 12%, transparent)`,
                  }}
                >
                  {categoryLabel}
                </span>
                <span className="text-[11px] font-semibold text-white">
                  {entry.term}
                </span>
              </div>

              {/* Definition */}
              <p className="text-[12px] leading-[1.6] text-gray-300">
                {entry.definition}
              </p>

              {/* Arrow */}
              <div
                className={`absolute left-1/2 -translate-x-1/2 w-2.5 h-2.5 rotate-45 border-[var(--border)] bg-[var(--surface)]/95 ${
                  above
                    ? "bottom-[-5px] border-b border-r"
                    : "top-[-5px] border-t border-l"
                }`}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </span>
  );
}
