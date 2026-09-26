// Indian number formatting: 1,960 · 18.4K · 1.8L · 2.1Cr
export function compact(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  if (n >= 1e7) return `${trim(n / 1e7)}Cr`;
  if (n >= 1e5) return `${trim(n / 1e5)}L`;
  if (n >= 1e4) return `${trim(n / 1e3)}K`;
  return n.toLocaleString("en-IN");
}

function trim(x: number): string {
  return x.toFixed(1).replace(/\.0$/, "");
}

export function pct(rate: number | null | undefined, digits = 1): string {
  if (rate === null || rate === undefined) return "—";
  return `${(rate * 100).toFixed(digits)}%`;
}

export function ratioText(r: number | null | undefined): string | null {
  if (r === null || r === undefined) return null;
  return `${r.toFixed(1)}× this creator's usual`;
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export function mediaLabel(t: string | null | undefined): string {
  switch ((t || "").toUpperCase()) {
    case "REELS":
      return "reel";
    case "STORY":
      return "story";
    case "CAROUSEL_ALBUM":
      return "carousel";
    default:
      return "post";
  }
}
