"use client";

import { useState } from "react";
import { buttonPrimary, buttonSecondary } from "@/components/SiteHeader";
import { api } from "@/lib/api";

export default function ReportActions({
  reportId,
  slug,
  isPublic,
  onChanged,
}: {
  reportId: string;
  slug: string;
  isPublic: boolean;
  onChanged: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const shareUrl = typeof window !== "undefined" ? `${window.location.origin}/r/${slug}` : `/r/${slug}`;

  async function copy() {
    await navigator.clipboard.writeText(shareUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function downloadPng() {
    setBusy("png");
    try {
      const { toPng } = await import("html-to-image");
      const node = document.getElementById("report-card");
      if (!node) return;
      const dataUrl = await toPng(node, { pixelRatio: 2, backgroundColor: "#f5f2ec", cacheBust: true });
      const a = document.createElement("a");
      a.href = dataUrl;
      a.download = `proofluence-report-${slug}.png`;
      a.click();
    } finally {
      setBusy(null);
    }
  }

  async function togglePublic() {
    setBusy("public");
    try {
      await api(`/reports/${reportId}`, { method: "PATCH", body: JSON.stringify({ is_public: !isPublic }) });
      onChanged();
    } finally {
      setBusy(null);
    }
  }

  async function refresh() {
    setBusy("refresh");
    try {
      await api(`/reports/${reportId}/refresh`, { method: "POST" });
      onChanged();
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="no-print flex flex-wrap gap-2">
      <button type="button" onClick={copy} className={buttonPrimary} disabled={!isPublic}>
        {copied ? "Link copied" : "Copy share link"}
      </button>
      <button type="button" onClick={downloadPng} className={buttonSecondary} disabled={busy === "png"}>
        {busy === "png" ? "Rendering…" : "Download image"}
      </button>
      <button type="button" onClick={() => window.print()} className={buttonSecondary}>Save as PDF</button>
      <button type="button" onClick={refresh} className={buttonSecondary} disabled={busy === "refresh"}>
        {busy === "refresh" ? "Queued…" : "Re-analyse"}
      </button>
      <button type="button" onClick={togglePublic} className={buttonSecondary} disabled={busy === "public"}>
        {isPublic ? "Make private" : "Make shareable"}
      </button>
    </div>
  );
}
