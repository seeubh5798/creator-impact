"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import ReportActions from "@/components/ReportActions";
import ReportView from "@/components/ReportView";
import SiteHeader, { buttonSecondary } from "@/components/SiteHeader";
import { api, ApiError } from "@/lib/api";
import type { Report } from "@/lib/types";

export default function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setReport(await api<Report>(`/reports/${id}`));
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.replace("/login");
      else setError(e instanceof ApiError && e.status === 404 ? "Report not found." : (e as Error).message);
    }
  }, [id, router]);

  useEffect(() => {
    const t = setTimeout(load, 0); // initial fetch (kept out of the synchronous effect body)
    return () => clearTimeout(t);
  }, [load]);

  useEffect(() => {
    if (report?.status !== "processing") return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [report?.status, load]);

  return (
    <main className="flex flex-col pb-16">
      <SiteHeader right={<Link href="/dashboard" className={`${buttonSecondary} h-9 px-3 text-sm`}>All posts</Link>} />
      <div className="mx-auto flex w-full max-w-[1168px] flex-col gap-6 px-4 md:px-0">
        {error && <p className="text-accent-dark">{error}</p>}
        {!report && !error && <p className="text-muted">Loading…</p>}

        {report?.status === "processing" && (
          <div className="rounded-[14px] border border-line bg-card p-8 text-center">
            <div className="mx-auto mb-3 h-2 w-40 animate-pulse rounded-full bg-line-soft" />
            <h1 className="font-display text-2xl font-semibold">Reading the comments…</h1>
            <p className="mt-1 text-muted">Usually done in a minute or two. This page updates by itself.</p>
          </div>
        )}

        {report?.status === "failed" && (
          <div className="rounded-[14px] border border-accent bg-card p-8">
            <h1 className="font-display text-2xl font-semibold">We couldn&apos;t build this report</h1>
            <p className="mt-1 text-muted">{report.data?.error || "Something went wrong while reading this post."}</p>
            <div className="mt-4">
              <ReportActions reportId={report.id!} slug={report.slug} isPublic={!!report.is_public} onChanged={load} />
            </div>
          </div>
        )}

        {report?.status === "ready" && (
          <>
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="flex items-center gap-3">
                <h1 className="font-display text-3xl font-semibold">Impact report</h1>
                {!report.is_public && <span className="rounded-full bg-line-soft px-2.5 py-1 text-xs font-semibold text-muted">Private</span>}
                {report.is_public && <span className="text-sm text-muted">{report.view_count} views</span>}
              </div>
              <ReportActions reportId={report.id!} slug={report.slug} isPublic={!!report.is_public} onChanged={load} />
            </div>
            <ReportView report={report} variant="owner" />
          </>
        )}
      </div>
    </main>
  );
}
