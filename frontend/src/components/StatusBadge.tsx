export default function StatusBadge({ status, score }: { status: "processing" | "ready" | "failed"; score: number | null }) {
  if (status === "ready") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-soft px-2.5 py-1 text-xs font-semibold text-blue-dark">
        Score {score ?? "—"}
      </span>
    );
  }
  if (status === "failed") {
    return <span className="rounded-full bg-[#fbe9e1] px-2.5 py-1 text-xs font-semibold text-accent-dark">Failed</span>;
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-line-soft px-2.5 py-1 text-xs font-semibold text-muted">
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-muted" /> Analysing
    </span>
  );
}
