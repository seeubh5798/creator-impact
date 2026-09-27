"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import SiteHeader, { buttonPrimary, buttonSecondary } from "@/components/SiteHeader";
import { api, ApiError } from "@/lib/api";
import { shortDate } from "@/lib/format";

const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME || "Proofluence";

type Billing = {
  enabled: boolean;
  key_id: string | null;
  plan: string;
  plan_expires_at: string | null;
  subscription: {
    id: string; plan: string; interval: string; status: string; current_end: string | null; cancel_at_cycle_end: boolean;
  } | null;
  plans: Record<"pro" | "pro_plus", { name: string; monthly: number; yearly: number }>;
};

type PlanKey = "pro" | "pro_plus";
type Interval = "monthly" | "yearly";

const FEATURES: Record<PlanKey, string[]> = {
  pro: ["Unlimited reports", "No “Made with” footer", "Re-analyse any time", "Rate calculator (coming soon)"],
  pro_plus: ["Everything in Pro", "Campaign reports (coming soon)", "Your logo on reports (coming soon)", "Priority support"],
};

declare global {
  interface Window { Razorpay?: new (opts: Record<string, unknown>) => { open: () => void } }
}

function loadCheckout(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.Razorpay) return resolve();
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Could not load Razorpay checkout"));
    document.body.appendChild(s);
  });
}

function rupees(paise: number): string {
  return `₹${(paise / 100).toLocaleString("en-IN")}`;
}

export default function BillingPage() {
  const router = useRouter();
  const [billing, setBilling] = useState<Billing | null>(null);
  const [interval, setInterval_] = useState<Interval>("monthly");
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const load = useCallback(async () => {
    try {
      setBilling(await api<Billing>("/billing"));
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.replace("/login");
      else setMessage({ kind: "error", text: (e as Error).message });
    }
  }, [router]);

  useEffect(() => {
    const t = setTimeout(load, 0);
    return () => clearTimeout(t);
  }, [load]);

  async function subscribe(plan: PlanKey) {
    if (!billing) return;
    setBusy(plan);
    setMessage(null);
    try {
      const created = await api<{ subscription_id: string; key_id: string }>("/billing/subscriptions", {
        method: "POST",
        body: JSON.stringify({ plan, interval }),
      });
      await loadCheckout();
      const rzp = new window.Razorpay!({
        key: created.key_id,
        subscription_id: created.subscription_id,
        name: APP_NAME,
        description: `${billing.plans[plan].name} · ${interval}`,
        theme: { color: "#17171B" },
        handler: async (resp: Record<string, string>) => {
          try {
            await api("/billing/verify", { method: "POST", body: JSON.stringify(resp) });
            setMessage({ kind: "ok", text: `You're on ${billing.plans[plan].name}. Thank you!` });
            await load();
          } catch (e) {
            setMessage({ kind: "error", text: (e as Error).message });
          } finally {
            setBusy(null);
          }
        },
        modal: { ondismiss: () => setBusy(null) },
      });
      rzp.open();
    } catch (e) {
      setMessage({ kind: "error", text: (e as Error).message });
      setBusy(null);
    }
  }

  async function cancel() {
    if (!confirm("Cancel your subscription? You keep access until the end of the paid period.")) return;
    setBusy("cancel");
    try {
      setBilling(await api<Billing>("/billing/cancel", { method: "POST" }));
      setMessage({ kind: "ok", text: "Cancelled. Your plan stays active until the end of the current period." });
    } catch (e) {
      setMessage({ kind: "error", text: (e as Error).message });
    } finally {
      setBusy(null);
    }
  }

  const sub = billing?.subscription;

  return (
    <main className="flex flex-col pb-16">
      <SiteHeader right={<Link href="/dashboard" className={`${buttonSecondary} h-9 px-3 text-sm`}>Dashboard</Link>} />
      <div className="mx-auto flex w-full max-w-[1168px] flex-col gap-8 px-4 md:px-0">
        <div>
          <h1 className="font-display text-4xl font-semibold">Plans</h1>
          <p className="mt-1 text-[15px] text-muted">
            Free gives you 3 reports a month. One extra brand deal pays for a year of Pro.
          </p>
        </div>

        {message && (
          <div role="alert" className={`rounded-lg border bg-card p-3 text-sm ${message.kind === "ok" ? "border-blue text-blue-dark" : "border-accent text-accent-dark"}`}>
            {message.text}
          </div>
        )}

        {billing && (
          <div className="rounded-[14px] border border-line bg-card p-5 text-[15px]">
            <span className="font-semibold">
              Current plan: {billing.plans[billing.plan as PlanKey]?.name ?? ({ free: "Free", founding: "Founding creator (free Pro)" }[billing.plan] ?? billing.plan)}
            </span>
            {sub && (
              <span className="text-muted">
                {" "}· {sub.interval} · {sub.cancel_at_cycle_end || sub.status === "cancelled" ? "ends" : "renews"}{" "}
                {shortDate(sub.current_end)}
              </span>
            )}
            {sub && !sub.cancel_at_cycle_end && sub.status !== "cancelled" && (
              <button type="button" onClick={cancel} disabled={busy === "cancel"} className="ml-3 text-sm underline">
                Cancel subscription
              </button>
            )}
            {!billing.enabled && <p className="mt-2 text-sm text-muted">Payments aren&apos;t switched on for this server yet.</p>}
          </div>
        )}

        <div className="flex gap-2">
          {(["monthly", "yearly"] as Interval[]).map((i) => (
            <button key={i} type="button" onClick={() => setInterval_(i)}
              className={`h-10 rounded-full px-4 text-sm font-medium ${interval === i ? "bg-ink text-white" : "border border-line bg-card"}`}>
              {i === "monthly" ? "Monthly" : "Yearly · 2 months free"}
            </button>
          ))}
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {(["pro", "pro_plus"] as PlanKey[]).map((key) => {
            const p = billing?.plans[key];
            const price = p ? (interval === "monthly" ? p.monthly : p.yearly) : 0;
            const isCurrent = billing?.plan === key && sub && !sub.cancel_at_cycle_end && sub.status !== "cancelled";
            return (
              <div key={key} className="flex flex-col gap-4 rounded-[14px] border border-line bg-card p-6">
                <div className="text-lg font-semibold">{p?.name ?? key}</div>
                <div>
                  <span className="font-display text-4xl font-semibold">{rupees(price)}</span>
                  <span className="text-muted"> / {interval === "monthly" ? "month" : "year"}, incl. GST</span>
                </div>
                <ul className="flex flex-col gap-1.5 text-[15px] text-muted">
                  {FEATURES[key].map((f) => <li key={f}>· {f}</li>)}
                </ul>
                <button type="button" onClick={() => subscribe(key)}
                  disabled={!billing?.enabled || busy !== null || !!isCurrent}
                  className={isCurrent ? buttonSecondary : buttonPrimary}>
                  {isCurrent ? "Current plan" : busy === key ? "Opening checkout…" : `Upgrade to ${p?.name ?? key}`}
                </button>
              </div>
            );
          })}
        </div>
        <p className="text-sm text-muted">
          Payments are handled by Razorpay (UPI, cards, netbanking). You can cancel any time from this page.
        </p>
      </div>
    </main>
  );
}
