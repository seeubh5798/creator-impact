import SiteHeader from "@/components/SiteHeader";

const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME || "Impact";

export const metadata = { title: "Terms of service" };

export default function TermsPage() {
  return (
    <main>
      <SiteHeader />
      <article className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 pb-20 text-[15px] leading-relaxed md:px-0">
        <h1 className="font-display text-4xl font-semibold">Terms of service</h1>
        <p className="text-muted">Last updated: 26 September 2026 · [LEGAL ENTITY NAME], India. Review with a lawyer before launch.</p>
        <h2 className="font-display text-2xl font-semibold">The service</h2>
        <p>
          {APP_NAME} analyses public engagement on your own Instagram posts and produces reports. Reports measure
          audience signals such as buying-intent comments; they are not a measurement of sales and we make no
          guarantee about outcomes with brands.
        </p>
        <h2 className="font-display text-2xl font-semibold">Your account</h2>
        <p>
          You must own the Instagram account you connect and comply with Instagram&apos;s terms. You are responsible
          for what you share. Do not use the service to analyse accounts you do not control.
        </p>
        <h2 className="font-display text-2xl font-semibold">Plans and payment</h2>
        <p>
          The free plan includes a limited number of reports per month. Paid plans are billed monthly or yearly
          in INR including GST and can be cancelled at any time; access continues until the end of the paid period.
        </p>
        <h2 className="font-display text-2xl font-semibold">Liability</h2>
        <p>
          The service is provided as is. To the extent permitted by law, our liability is limited to the fees you
          paid in the previous three months. Indian law governs these terms.
        </p>
      </article>
    </main>
  );
}
