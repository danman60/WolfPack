"use client";

export default function RotationError({ reset }: { reset: () => void }) {
  return <section className="wolf-card p-6 max-w-xl"><h1 className="text-2xl font-semibold">Workspace could not load</h1><p className="mt-3 text-slate-300">Reload the workspace to retrieve your saved ledger. A failed screen does not confirm that a paper decision was recorded; check decision history before trying again.</p><button onClick={reset} className="mt-5 px-4 py-3 bg-emerald-300 text-slate-950 rounded-md font-semibold">Reload workspace</button></section>;
}
