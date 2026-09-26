import Link from "next/link";

const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME || "Impact";

export default function SiteHeader({ right }: { right?: React.ReactNode }) {
  return (
    <header className="no-print mx-auto flex w-full max-w-[1168px] items-center justify-between px-4 py-5 md:px-0">
      <Link href="/" className="font-display text-2xl font-semibold !text-ink no-underline">
        {APP_NAME}
      </Link>
      <nav className="flex items-center gap-3">{right}</nav>
    </header>
  );
}

export const buttonPrimary =
  "inline-flex h-11 items-center justify-center rounded-lg border border-ink bg-ink px-4 text-[15px] font-medium text-white no-underline hover:text-white disabled:opacity-50";
export const buttonSecondary =
  "inline-flex h-11 items-center justify-center rounded-lg border border-ink bg-white px-4 text-[15px] font-medium text-ink no-underline hover:text-ink disabled:opacity-50";
