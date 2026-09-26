"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import SiteHeader, { buttonPrimary, buttonSecondary } from "@/components/SiteHeader";
import { api } from "@/lib/api";

const ERRORS: Record<string, string> = {
  access_denied: "You cancelled the Instagram login.",
  state_mismatch: "Your login session expired. Please try again.",
  instagram: "Instagram didn't accept the login. Make sure you use a Creator or Business account.",
  missing_code: "Instagram didn't return a login code. Please try again.",
};

function LoginInner() {
  const router = useRouter();
  const params = useSearchParams();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const error = params.get("error");

  async function demo() {
    setBusy(true);
    setErr(null);
    try {
      await api("/auth/demo", { method: "POST" });
      router.push("/dashboard");
    } catch {
      setErr("Demo mode is turned off on this server.");
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-6 px-4 pt-12">
      <h1 className="font-display text-4xl font-semibold">Sign in</h1>
      <p className="text-[15px] leading-relaxed text-muted">
        Connect your Instagram Creator or Business account. We only read your posts, comments and insights,
        and we never post anything.
      </p>
      {(error || err) && (
        <div role="alert" className="rounded-lg border border-accent bg-card p-3 text-sm text-accent-dark">
          {err || ERRORS[error!] || "Something went wrong. Please try again."}
        </div>
      )}
      <a href="/api/auth/instagram/login" className={buttonPrimary}>Continue with Instagram</a>
      <button type="button" onClick={demo} disabled={busy} className={buttonSecondary}>
        {busy ? "Opening demo…" : "Try the demo account"}
      </button>
      <p className="text-sm text-muted">
        Personal Instagram accounts can switch to Creator for free in Instagram settings → Account type and tools.
      </p>
    </div>
  );
}

export default function LoginPage() {
  return (
    <main>
      <SiteHeader />
      <Suspense>
        <LoginInner />
      </Suspense>
    </main>
  );
}
