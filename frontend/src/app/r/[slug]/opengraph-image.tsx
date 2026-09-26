import { ImageResponse } from "next/og";
import { backendUrl } from "@/lib/api";
import type { Report } from "@/lib/types";

export const alt = "Creator impact report";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME || "Impact";

export default async function Image({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const res = await fetch(backendUrl(`/public/reports/${encodeURIComponent(slug)}`), { cache: "no-store" });
  const report: Report | null = res.ok ? await res.json() : null;
  const d = report?.data;

  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between",
        padding: 64, background: "#F5F2EC", color: "#17171B", fontFamily: "Georgia, serif" }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 28 }}>
          <span style={{ fontWeight: 600 }}>{APP_NAME}</span>
          <span style={{ color: "#163A77", background: "#EAF0FA", borderRadius: 999, padding: "8px 20px", fontSize: 22 }}>
            Verified from Instagram data
          </span>
        </div>
        {d ? (
          <div style={{ display: "flex", alignItems: "flex-end", gap: 40 }}>
            <div style={{ display: "flex", alignItems: "baseline" }}>
              <span style={{ fontSize: 220, fontWeight: 600, lineHeight: 1, color: "#B4410E" }}>{report!.score}</span>
              <span style={{ fontSize: 40, color: "#5C5A55", marginLeft: 8 }}>/ 100</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 12, paddingBottom: 24 }}>
              <span style={{ fontSize: 44, fontWeight: 600 }}>{d.verdict}</span>
              <span style={{ fontSize: 30, color: "#5C5A55" }}>
                @{d.creator.username}{d.brand_name ? ` × ${d.brand_name}` : ""}
              </span>
              <span style={{ fontSize: 30, color: "#5C5A55" }}>
                {d.buying_intent.count} buying-intent comments · {d.metrics.saves.ratio ? `${d.metrics.saves.ratio}× saves` : ""}
              </span>
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 48 }}>Report not found</div>
        )}
      </div>
    ),
    size,
  );
}
