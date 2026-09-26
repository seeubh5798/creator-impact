import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import ReportView from "@/components/ReportView";
import SiteHeader, { buttonSecondary } from "@/components/SiteHeader";
import { backendUrl } from "@/lib/api";
import type { Report } from "@/lib/types";

const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME || "Impact";

async function fetchReport(slug: string): Promise<Report | null> {
  const res = await fetch(backendUrl(`/public/reports/${encodeURIComponent(slug)}`), { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return res.json();
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const report = await fetchReport(slug).catch(() => null);
  if (!report) return { title: "Report not found" };
  const d = report.data;
  const title = `@${d.creator.username}${d.brand_name ? ` × ${d.brand_name}` : ""}: impact score ${report.score}/100`;
  const description = `${d.buying_intent.count} buying-intent comments · ${d.verdict}. Verified from Instagram data with ${APP_NAME}.`;
  return {
    title,
    description,
    openGraph: { title, description, type: "article", images: [`/r/${slug}/opengraph-image`] },
    twitter: { card: "summary_large_image", title, description },
    robots: { index: false },
  };
}

export default async function PublicReportPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const report = await fetchReport(slug);
  if (!report) notFound();
  return (
    <main className="flex flex-col pb-16">
      <SiteHeader right={<Link href="/login" className={`${buttonSecondary} h-9 px-3 text-sm`}>Get your report</Link>} />
      <div className="px-4 md:px-0">
        <ReportView report={report} variant="public" />
      </div>
    </main>
  );
}
