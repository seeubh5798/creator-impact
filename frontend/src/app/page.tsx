import Link from "next/link";
import SiteHeader, { buttonPrimary, buttonSecondary } from "@/components/SiteHeader";

const STEPS = [
  { title: "Connect Instagram", body: "One tap with Instagram's official login. We never see your password." },
  { title: "Tag a sponsored post", body: "Pick the reel or post and name the brand. Analysis takes a few minutes." },
  { title: "Share the proof", body: "Send the brand a verified report link or PDF, and ask for the rate you deserve." },
];

const INSIDE = [
  ["Buying-intent comments", "“Price?”, “link do”, “kahan milega” — counted across English, Hindi and Hinglish."],
  ["Performance vs your usual", "Saves, shares and reach compared with your own recent posts, not generic benchmarks."],
  ["What the audience asked", "Top questions and objections: free product research the brand will remember."],
  ["Verified numbers", "Pulled straight from Instagram's API. No screenshots, nothing typed in by hand."],
];

const PLANS = [
  { name: "Free", price: "₹0", note: "3 reports a month", features: ["Full impact report", "Share link + PDF", "Made-with footer"] },
  { name: "Pro", price: "₹299", note: "per month", features: ["Unlimited reports", "Rate calculator", "Live media kit", "No footer"] },
  { name: "Pro+", price: "₹999", note: "per month", features: ["Everything in Pro", "Campaign reports", "Your own branding"] },
];

export default function Home() {
  return (
    <main className="flex flex-col">
      <SiteHeader right={<Link href="/login" className={buttonSecondary}>Sign in</Link>} />

      <section className="mx-auto flex w-full max-w-[1168px] flex-col gap-6 px-4 pb-16 pt-10 md:px-0 md:pt-20">
        <h1 className="max-w-3xl font-display text-[44px] font-semibold leading-[1.05] md:text-[72px]">
          Prove what your sponsored posts really do.
        </h1>
        <p className="max-w-2xl text-lg leading-relaxed text-muted md:text-xl">
          Brands pay on views and likes. Your audience buys. Turn every brand post into a verified impact report
          that shows buying intent, audience questions and how the post beat your usual.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link href="/login" className={buttonPrimary}>Get your free report</Link>
          <Link href="/login?demo=1" className={buttonSecondary}>See a sample report</Link>
        </div>
      </section>

      <section className="border-y border-line bg-card">
        <div className="mx-auto grid w-full max-w-[1168px] gap-8 px-4 py-14 md:grid-cols-3 md:px-0">
          {STEPS.map((s, i) => (
            <div key={s.title} className="flex flex-col gap-2">
              <div className="font-mono text-sm text-accent">0{i + 1}</div>
              <h2 className="font-display text-2xl font-semibold">{s.title}</h2>
              <p className="text-[15px] leading-relaxed text-muted">{s.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto w-full max-w-[1168px] px-4 py-16 md:px-0">
        <h2 className="mb-8 font-display text-3xl font-semibold md:text-4xl">What&apos;s in every report</h2>
        <div className="grid gap-4 md:grid-cols-2">
          {INSIDE.map(([title, body]) => (
            <div key={title} className="rounded-[14px] border border-line bg-card p-6">
              <h3 className="mb-1 text-lg font-semibold">{title}</h3>
              <p className="text-[15px] leading-relaxed text-muted">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto w-full max-w-[1168px] px-4 pb-20 md:px-0">
        <h2 className="mb-8 font-display text-3xl font-semibold md:text-4xl">Pricing</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {PLANS.map((p) => (
            <div key={p.name} className="flex flex-col gap-3 rounded-[14px] border border-line bg-card p-6">
              <div className="text-lg font-semibold">{p.name}</div>
              <div><span className="font-display text-4xl font-semibold">{p.price}</span> <span className="text-muted">{p.note}</span></div>
              <ul className="flex flex-col gap-1.5 text-[15px] text-muted">
                {p.features.map((f) => <li key={f}>· {f}</li>)}
              </ul>
            </div>
          ))}
        </div>
        <p className="mt-4 text-sm text-muted">Prices include GST. Yearly plans get 2 months free. Brand and agency plans coming soon.</p>
      </section>

      <footer className="border-t border-line">
        <div className="mx-auto flex w-full max-w-[1168px] justify-between px-4 py-6 text-sm text-muted md:px-0">
          <span>© {new Date().getFullYear()}</span>
          <span className="flex gap-4"><Link href="/privacy">Privacy</Link><Link href="/terms">Terms</Link></span>
        </div>
      </footer>
    </main>
  );
}
