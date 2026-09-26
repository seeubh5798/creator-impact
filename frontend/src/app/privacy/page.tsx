import SiteHeader from "@/components/SiteHeader";

const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME || "Impact";
const CONTACT = process.env.NEXT_PUBLIC_CONTACT_EMAIL || "[YOUR CONTACT EMAIL]";

export const metadata = { title: "Privacy policy" };

// Meta app review requires a public privacy policy URL. Review this text with a
// lawyer before launch; the placeholders must be filled in.
export default function PrivacyPage() {
  return (
    <main>
      <SiteHeader />
      <article className="prose mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 pb-20 text-[15px] leading-relaxed md:px-0">
        <h1 className="font-display text-4xl font-semibold">Privacy policy</h1>
        <p className="text-muted">Last updated: 26 September 2026 · Operated by [LEGAL ENTITY NAME], India.</p>

        <h2 className="font-display text-2xl font-semibold">What {APP_NAME} does</h2>
        <p>
          {APP_NAME} creates impact reports for Instagram creators. When you connect your Instagram Creator or
          Business account through Instagram&apos;s official login, we read your posts, the comments on them and
          their insights (reach, saves, shares, likes, views, comments) to build reports you choose to share.
        </p>

        <h2 className="font-display text-2xl font-semibold">Data we store</h2>
        <ul className="list-disc pl-6">
          <li>Your Instagram user ID, username, account type, profile picture URL and follower count.</li>
          <li>An encrypted access token that lets us read your data. We never post, message or act on your behalf.</li>
          <li>Post metadata (caption, permalink, thumbnail URL, posting time) and insight numbers.</li>
          <li>
            For each comment: a category (buying intent, question, objection, praise, other, spam), detected
            language and topic. Commenter usernames are never stored. Comment text is kept for at most 30 days for
            quality checks and then deleted; only the aggregated labels remain.
          </li>
          <li>The reports you generate, and how many times a shared report link was opened.</li>
        </ul>

        <h2 className="font-display text-2xl font-semibold">How we use it</h2>
        <p>
          Only to produce your reports, keep your account working (for example refreshing the Instagram access
          token) and improve classification quality. We do not sell your data or use it for advertising. Shared
          report links show aggregated numbers, never individual commenters.
        </p>

        <h2 className="font-display text-2xl font-semibold">Third parties</h2>
        <p>
          Hosting and database: Supabase and our application host. Comment classification: an AI model provider
          (Anthropic) receives comment text without usernames. Payments (paid plans): Razorpay. Each processes
          data only to provide their service to us.
        </p>

        <h2 className="font-display text-2xl font-semibold" id="deletion">Deleting your data</h2>
        <p>
          Sign in and use &ldquo;Delete my account&rdquo; in the dashboard, or remove {APP_NAME} from your Instagram
          settings (Apps and websites); Meta then sends us a deletion request and we delete everything within 30
          days. You can also email {CONTACT}. Deletion removes your account, posts, comment labels and reports.
        </p>

        <h2 className="font-display text-2xl font-semibold">Your rights</h2>
        <p>
          Under India&apos;s Digital Personal Data Protection Act and, where applicable, the GDPR, you can access,
          correct or delete your data and withdraw consent at any time by disconnecting your account. Contact:{" "}
          {CONTACT}.
        </p>
      </article>
    </main>
  );
}
