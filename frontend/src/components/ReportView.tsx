import type { Report, TopicCount } from "@/lib/types";
import { compact, mediaLabel, pct, ratioText, shortDate } from "@/lib/format";

const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME || "Impact";

function initials(name: string): string {
  return name.replace(/[^a-zA-Z]/g, "").slice(0, 2).toUpperCase() || "IG";
}

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`print-break-avoid rounded-[14px] border border-line bg-card ${className}`}>{children}</div>
  );
}

function Heading({ children }: { children: React.ReactNode }) {
  return <h2 className="font-display text-[20px] font-semibold md:text-[22px]">{children}</h2>;
}

function ShieldCheck({ className = "" }: { className?: string }) {
  return (
    <svg className={className} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z" />
      <path d="M9 12l2 2 4-4" />
    </svg>
  );
}

function MetricCard({ label, value, note, accent }: { label: string; value: string; note: string | null; accent?: boolean }) {
  return (
    <Card className="flex flex-col gap-1 p-4 md:p-6">
      <div className="text-[13px] text-muted md:text-sm">{label}</div>
      <div className="font-mono text-[26px] font-medium md:text-[34px]">{value}</div>
      {note && (
        <div className={`text-[13px] font-medium md:text-sm ${accent ? "text-accent" : "text-blue"}`}>{note}</div>
      )}
    </Card>
  );
}

function TopicList({ items, divided }: { items: TopicCount[]; divided?: boolean }) {
  if (!items.length) return <p className="text-[15px] text-muted">Nothing notable yet.</p>;
  return (
    <ul className="flex flex-col gap-3 text-[15px]">
      {items.map((t, i) => (
        <li key={t.label}
          className={`flex justify-between gap-4 ${divided && i < items.length - 1 ? "border-b border-line-soft pb-3" : ""}`}>
          <span>{t.label}</span>
          <span className="font-mono text-muted">{t.count}</span>
        </li>
      ))}
    </ul>
  );
}

const SEGMENTS = [
  { key: "buying_intent", label: "Buying intent", className: "bg-accent" },
  { key: "question", label: "Product questions", className: "bg-blue" },
  { key: "praise", label: "Praise", className: "bg-blue-light" },
  { key: "objection", label: "Objections", className: "bg-ink" },
  { key: "other", label: "Other", className: "bg-sand" },
] as const;

export default function ReportView({ report, variant }: { report: Report; variant: "owner" | "public" }) {
  const d = report.data;
  const score = report.score ?? d.score;
  const breakdown = d.comments.breakdown;
  const total = d.comments.analyzed + d.comments.spam_removed || 1;
  const segments = [
    ...SEGMENTS.map((s) => ({ ...s, n: breakdown[s.key] ?? 0 })),
    { key: "spam", label: "Spam, removed", className: "bg-line-soft border border-sand", n: d.comments.spam_removed },
  ].filter((s) => s.n > 0);
  const kind = mediaLabel(d.post.media_type);
  const langs = Object.keys(d.comments.languages || {})
    .filter((l) => l !== "und")
    .map((l) => ({ en: "English", hi: "Hindi", hinglish: "Hinglish" })[l] || l);

  return (
    <div id="report-card" className="mx-auto flex w-full max-w-[1168px] flex-col gap-4 bg-paper md:gap-6">
      {/* Creator row */}
      <Card className="flex flex-col gap-4 p-5 md:flex-row md:items-center md:gap-5 md:px-6">
        <div className="flex items-center gap-4 md:flex-1">
          {d.creator.profile_picture_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={d.creator.profile_picture_url} alt="" className="h-14 w-14 rounded-full object-cover md:h-16 md:w-16" />
          ) : (
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[#e9e3d8] text-lg font-semibold text-muted md:h-16 md:w-16">
              {initials(d.creator.username)}
            </div>
          )}
          <div className="flex flex-col gap-1">
            <div className="text-lg font-semibold md:text-[22px]">@{d.creator.username}</div>
            <div className="text-sm text-muted md:text-[15px]">
              Sponsored {kind}{d.brand_name ? ` for ${d.brand_name}` : ""} · Posted {shortDate(d.post.posted_at)}
              {d.post.permalink && variant === "owner" && (
                <> · <a href={d.post.permalink} target="_blank" rel="noreferrer">View on Instagram</a></>
              )}
            </div>
          </div>
        </div>
        <div className="flex flex-col gap-1.5 md:items-end">
          <div className="inline-flex w-fit items-center gap-2 rounded-full bg-blue-soft px-3.5 py-2 text-sm font-semibold text-blue-dark">
            <ShieldCheck /> Verified from Instagram data
          </div>
          <div className="text-[13px] text-muted">
            Updated {shortDate(d.updated_at)}
            {d.hours_since_post !== null && d.hours_since_post !== undefined &&
              ` · ${d.hours_since_post < 48 ? `${d.hours_since_post}h` : `${Math.round(d.hours_since_post / 24)} days`} after posting`}
          </div>
        </div>
      </Card>

      {/* Score + metrics */}
      <div className="flex flex-col gap-4 md:flex-row md:gap-6">
        <Card className="flex flex-col gap-2 p-6 md:w-[360px] md:shrink-0 md:p-7">
          <div className="text-sm font-medium text-muted">Impact score</div>
          <div className="flex items-baseline gap-1.5">
            <span className="font-display text-[80px] font-semibold leading-none text-accent md:text-[96px]">
              {score ?? "—"}
            </span>
            <span className="text-lg text-muted md:text-xl">/ 100</span>
          </div>
          <div className="text-lg font-semibold md:text-xl">{d.verdict}</div>
          <p className="text-sm leading-relaxed text-muted md:text-[15px]">
            {d.percentile !== null ? `Better than ${d.percentile}% of this creator's own recent posts. ` : ""}
            Based on buying-intent comments, saves, shares and reach vs their usual.
          </p>
          <div className="mt-2 h-2 rounded-full bg-line-soft">
            <div className="h-2 rounded-full bg-accent" style={{ width: `${score ?? 0}%` }} />
          </div>
        </Card>
        <div className="grid flex-1 grid-cols-2 gap-3 md:gap-4">
          <MetricCard label="Buying-intent comments" value={compact(d.buying_intent.count)}
            note={d.buying_intent.rate !== null ? `${pct(d.buying_intent.rate)} of comments` : null} accent />
          <MetricCard label="Saves" value={compact(d.metrics.saves.value)} note={ratioText(d.metrics.saves.ratio)} />
          <MetricCard label="Shares" value={compact(d.metrics.shares.value)} note={ratioText(d.metrics.shares.ratio)} />
          <MetricCard label="Accounts reached" value={compact(d.metrics.reach.value)} note={ratioText(d.metrics.reach.ratio)} />
        </div>
      </div>

      {/* Comment breakdown */}
      <Card className="flex flex-col gap-4 p-5 md:px-7 md:py-6">
        <div className="flex flex-col gap-1 md:flex-row md:items-baseline md:justify-between">
          <Heading>What {compact(total)} comments said</Heading>
          <div className="text-sm text-muted">
            {langs.join(", ")}{langs.length ? " · " : ""}{d.comments.spam_removed} spam comments removed
          </div>
        </div>
        <div className="flex h-4 gap-[3px] md:h-[18px]" role="img"
          aria-label={segments.map((s) => `${s.label} ${Math.round((100 * s.n) / total)}%`).join(", ")}>
          {segments.map((s) => (
            <div key={s.key} className={`rounded ${s.className}`} style={{ width: `${(100 * s.n) / total}%` }} />
          ))}
        </div>
        <ul className="flex flex-col gap-2 text-sm md:flex-row md:flex-wrap md:gap-x-7">
          {segments.map((s) => (
            <li key={s.key} className="flex items-center justify-between gap-2 md:justify-start">
              <span className="flex items-center gap-2">
                <span className={`inline-block h-2.5 w-2.5 rounded-[3px] ${s.className}`} />
                {s.label}
              </span>
              <span className="font-mono">{Math.round((100 * s.n) / total)}%</span>
            </li>
          ))}
        </ul>
      </Card>

      {/* Questions / objections / quotes */}
      <div className="flex flex-col gap-4 md:flex-row md:gap-6">
        <Card className="flex flex-col gap-3.5 p-5 md:flex-1 md:px-7 md:py-6">
          <Heading>Top audience questions</Heading>
          <TopicList items={d.top_questions} divided />
        </Card>
        <div className="flex flex-col gap-4 md:flex-1 md:gap-6">
          <Card className="flex flex-col gap-3.5 p-5 md:px-7 md:py-6">
            <Heading>Main objections</Heading>
            <TopicList items={d.objections} />
          </Card>
          {d.quotes.length > 0 && (
            <Card className="flex flex-col gap-3 p-5 md:px-7 md:py-6">
              <Heading>In their words</Heading>
              {d.quotes.map((q, i) => (
                <p key={i} className="text-[15px] leading-relaxed">
                  &ldquo;{q.text}&rdquo; <span className="text-muted">· Viewer {i + 1}</span>
                </p>
              ))}
            </Card>
          )}
        </div>
      </div>

      {variant === "public" && (
        <div className="no-print flex flex-col gap-3 rounded-[14px] bg-ink p-5 text-white md:flex-row md:items-center md:justify-between md:p-6">
          <div>
            <div className="font-display text-xl font-semibold">Are you a creator?</div>
            <p className="text-[15px] text-line">
              Prove what your sponsored posts really do. Your first 3 reports are free.
            </p>
          </div>
          <a href="/login" className="flex h-12 items-center justify-center rounded-lg bg-white px-5 text-[15px] font-semibold text-ink no-underline hover:text-ink">
            Get your free report
          </a>
        </div>
      )}

      <div className="flex flex-col gap-1 pb-2 text-center text-[13px] text-muted md:flex-row md:justify-between md:text-left">
        <span>
          {d.comments.total.toLocaleString("en-IN")} comments analysed · Commenter names hidden · Metrics from
          Instagram · Baseline: last {d.baseline.sample_size} posts
        </span>
        <span className="font-medium">Made with {APP_NAME}</span>
      </div>
    </div>
  );
}
