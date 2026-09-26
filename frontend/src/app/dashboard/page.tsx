"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import SiteHeader, { buttonPrimary, buttonSecondary } from "@/components/SiteHeader";
import StatusBadge from "@/components/StatusBadge";
import { api, ApiError } from "@/lib/api";
import { compact, mediaLabel, shortDate } from "@/lib/format";
import type { Me, Post } from "@/lib/types";

type Tagging = { post: Post; brand: string; busy: boolean; error: string | null };

export default function DashboardPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [posts, setPosts] = useState<Post[] | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [tagging, setTagging] = useState<Tagging | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [m, p] = await Promise.all([api<Me>("/auth/me"), api<{ posts: Post[] }>("/posts")]);
      setMe(m);
      setPosts(p.posts);
      return p.posts;
    } catch (e) {
      if (e instanceof ApiError && (e.status === 401 || e.status === 409)) router.replace("/login");
      else setError((e as Error).message);
      return [];
    }
  }, [router]);

  useEffect(() => {
    const t = setTimeout(load, 0);
    return () => clearTimeout(t);
  }, [load]);

  // Poll while the worker is still syncing a fresh account (no posts yet) or a report is processing.
  const shouldPoll = posts !== null && (posts.length === 0 || posts.some((p) => p.report?.status === "processing"));
  useEffect(() => {
    if (!shouldPoll) return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [shouldPoll, load]);

  async function sync() {
    setSyncing(true);
    setError(null);
    try {
      const p = await api<{ posts: Post[] }>("/posts/sync", { method: "POST" });
      setPosts(p.posts);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSyncing(false);
    }
  }

  async function confirmTag() {
    if (!tagging) return;
    setTagging({ ...tagging, busy: true, error: null });
    try {
      const r = await api<{ report_id: string }>(`/posts/${tagging.post.id}/sponsor`, {
        method: "POST",
        body: JSON.stringify({ brand_name: tagging.brand || null }),
      });
      setTagging(null);
      await load();
      router.push(`/reports/${r.report_id}`);
    } catch (e) {
      setTagging({ ...tagging, busy: false, error: (e as Error).message });
    }
  }

  async function logout() {
    await api("/auth/logout", { method: "POST" });
    router.replace("/");
  }

  async function deleteAccount() {
    if (!confirm("Delete your account and every report? This cannot be undone.")) return;
    await api("/auth/me", { method: "DELETE" });
    router.replace("/");
  }

  const sponsored = posts?.filter((p) => p.is_sponsored) ?? [];
  const others = posts?.filter((p) => !p.is_sponsored) ?? [];

  return (
    <main className="flex flex-col pb-16">
      <SiteHeader
        right={
          <>
            {me?.account && <span className="hidden text-sm text-muted md:inline">@{me.account.username}</span>}
            <button type="button" onClick={logout} className={`${buttonSecondary} h-9 px-3 text-sm`}>Sign out</button>
          </>
        }
      />
      <div className="mx-auto flex w-full max-w-[1168px] flex-col gap-8 px-4 md:px-0">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="font-display text-4xl font-semibold">Your posts</h1>
            <p className="mt-1 text-[15px] text-muted">
              Tag a sponsored post to get its impact report.
              {me?.usage.monthly_limit !== null && me?.usage.monthly_limit !== undefined && (
                <> {me.usage.remaining} of {me.usage.monthly_limit} free reports left this month.</>
              )}
              {me?.user.is_demo && <> You&apos;re on the shared demo account.</>}
            </p>
          </div>
          <button type="button" onClick={sync} disabled={syncing} className={buttonSecondary}>
            {syncing ? "Syncing…" : "Refresh from Instagram"}
          </button>
        </div>

        {error && <div role="alert" className="rounded-lg border border-accent bg-card p-3 text-sm text-accent-dark">{error}</div>}

        {posts === null && <p className="text-muted">Loading…</p>}
        {posts?.length === 0 && (
          <p className="rounded-[14px] border border-line bg-card p-6 text-muted">
            Fetching your recent posts from Instagram. This takes a few seconds.
          </p>
        )}

        {sponsored.length > 0 && (
          <section className="flex flex-col gap-3">
            <h2 className="font-display text-2xl font-semibold">Sponsored posts</h2>
            <div className="grid gap-3 md:grid-cols-2">
              {sponsored.map((p) => (
                <div key={p.id} className="flex items-center gap-4 rounded-[14px] border border-line bg-card p-4">
                  <Thumb post={p} />
                  <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <div className="truncate font-semibold">{p.brand_name || "Untitled brand"}</div>
                    <div className="truncate text-sm text-muted">{shortDate(p.posted_at)} · {mediaLabel(p.media_type)} · {p.caption || "No caption"}</div>
                    <div className="mt-1 flex items-center gap-2">
                      {p.report && <StatusBadge status={p.report.status} score={p.report.score} />}
                      {p.report && <Link href={`/reports/${p.report.id}`} className="text-sm font-medium">Open report</Link>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {others.length > 0 && (
          <section className="flex flex-col gap-3">
            <h2 className="font-display text-2xl font-semibold">Recent posts</h2>
            <div className="grid gap-3 md:grid-cols-2">
              {others.map((p) => (
                <div key={p.id} className="flex items-center gap-4 rounded-[14px] border border-line bg-card p-4">
                  <Thumb post={p} />
                  <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <div className="truncate text-[15px]">{p.caption || <span className="text-muted">No caption</span>}</div>
                    <div className="text-sm text-muted">
                      {shortDate(p.posted_at)} · {mediaLabel(p.media_type)} · {compact(p.like_count)} likes · {compact(p.comments_count)} comments
                    </div>
                  </div>
                  <button type="button" onClick={() => setTagging({ post: p, brand: guessBrand(p.caption), busy: false, error: null })}
                    className={`${buttonSecondary} h-9 shrink-0 px-3 text-sm`}>
                    Tag as sponsored
                  </button>
                </div>
              ))}
            </div>
          </section>
        )}

        <div className="mt-8 border-t border-line pt-6 text-sm text-muted">
          Want out? <button type="button" onClick={deleteAccount} className="underline">Delete my account</button> removes
          your Instagram connection, posts, comment labels and reports.
        </div>
      </div>

      {tagging && (
        <div className="fixed inset-0 z-20 flex items-end justify-center bg-ink/40 p-4 md:items-center" role="dialog" aria-modal="true" aria-labelledby="tag-title">
          <form
            onSubmit={(e) => { e.preventDefault(); confirmTag(); }}
            className="flex w-full max-w-md flex-col gap-4 rounded-[14px] bg-card p-6"
          >
            <h2 id="tag-title" className="font-display text-2xl font-semibold">Tag as sponsored</h2>
            <p className="text-sm text-muted">{tagging.post.caption || "No caption"}</p>
            <label className="flex flex-col gap-1 text-sm font-medium">
              Brand name
              <input
                autoFocus
                value={tagging.brand}
                onChange={(e) => setTagging({ ...tagging, brand: e.target.value })}
                maxLength={80}
                placeholder="e.g. GlowLab"
                className="h-11 rounded-lg border border-sand bg-white px-3 text-[15px] font-normal outline-none focus:border-ink"
              />
            </label>
            {tagging.error && <div role="alert" className="text-sm text-accent-dark">{tagging.error}</div>}
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setTagging(null)} className={buttonSecondary}>Cancel</button>
              <button type="submit" disabled={tagging.busy} className={buttonPrimary}>
                {tagging.busy ? "Starting…" : "Generate report"}
              </button>
            </div>
          </form>
        </div>
      )}
    </main>
  );
}

function Thumb({ post }: { post: Post }) {
  if (post.thumbnail_url) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={post.thumbnail_url} alt="" className="h-16 w-16 shrink-0 rounded-lg object-cover" />;
  }
  return (
    <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-lg bg-[#e9e3d8] text-xs font-semibold uppercase text-muted">
      {mediaLabel(post.media_type)}
    </div>
  );
}

function guessBrand(caption: string): string {
  const m = caption.match(/@([a-zA-Z0-9_.]+)/);
  return m ? m[1] : "";
}
