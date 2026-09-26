export type Metric = { value: number | null; baseline: number | null; ratio: number | null };

export type TopicCount = { label: string; count: number };

export type ReportData = {
  version?: number;
  error?: string;
  creator: { username: string; profile_picture_url: string | null; followers_count: number | null };
  post: {
    permalink: string | null;
    media_type: string | null;
    posted_at: string | null;
    thumbnail_url: string | null;
    caption_excerpt: string;
  };
  brand_name: string | null;
  score: number | null;
  verdict: string;
  percentile: number | null;
  metrics: Record<"reach" | "saves" | "shares" | "likes" | "comments" | "views", Metric>;
  baseline: { sample_size: number; computed_at: string };
  comments: {
    total: number;
    analyzed: number;
    spam_removed: number;
    breakdown: Record<"buying_intent" | "question" | "objection" | "praise" | "other", number>;
    languages: Record<string, number>;
  };
  buying_intent: { count: number; rate: number | null };
  top_questions: TopicCount[];
  objections: TopicCount[];
  quotes: { text: string }[];
  run_kind: string;
  hours_since_post: number | null;
  updated_at: string;
};

export type Report = {
  id?: string;
  post_id?: string;
  slug: string;
  status: "processing" | "ready" | "failed";
  score: number | null;
  verdict: string | null;
  created_at: string | null;
  updated_at: string | null;
  is_public?: boolean;
  view_count?: number;
  data: ReportData;
};

export type Post = {
  id: string;
  media_type: string | null;
  caption: string;
  permalink: string | null;
  thumbnail_url: string | null;
  posted_at: string | null;
  like_count: number | null;
  comments_count: number | null;
  is_sponsored: boolean;
  brand_name: string | null;
  report: { id: string; status: Report["status"]; score: number | null } | null;
};

export type Me = {
  user: { id: string; display_name: string | null; is_demo: boolean };
  account: {
    username: string;
    profile_picture_url: string | null;
    followers_count: number | null;
    last_synced_at: string | null;
  } | null;
  usage: { plan: string; reports_this_month: number; monthly_limit: number | null; remaining: number | null };
};

export type ReportListItem = {
  id: string;
  slug: string;
  status: Report["status"];
  score: number | null;
  verdict: string | null;
  brand_name: string | null;
  posted_at: string | null;
  thumbnail_url: string | null;
  created_at: string;
  view_count: number;
};
