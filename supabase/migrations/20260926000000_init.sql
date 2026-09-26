-- Creator Impact Reports: initial schema
-- Apply with: supabase db push   (or paste into Supabase SQL editor)
--
-- The backend connects with the Postgres connection string (service role),
-- which bypasses RLS. RLS is enabled on every table with NO policies, so the
-- public anon / authenticated keys can never read or write this data directly.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------- users
create table if not exists users (
    id              uuid primary key default gen_random_uuid(),
    display_name    text,
    email           text,
    plan            text not null default 'free' check (plan in ('free', 'pro', 'pro_plus', 'founding')),
    plan_expires_at timestamptz,
    is_demo         boolean not null default false,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

-- ---------------------------------------------------------- ig_accounts
create table if not exists ig_accounts (
    id                  uuid primary key default gen_random_uuid(),
    user_id             uuid not null unique references users(id) on delete cascade,
    ig_user_id          text not null unique,
    username            text not null,
    account_type        text,
    profile_picture_url text,
    followers_count     integer,
    media_count         integer,
    access_token_enc    text not null,          -- Fernet-encrypted long-lived token
    token_expires_at    timestamptz,
    last_synced_at      timestamptz,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);

-- ---------------------------------------------------------------- posts
create table if not exists posts (
    id                 uuid primary key default gen_random_uuid(),
    ig_account_id      uuid not null references ig_accounts(id) on delete cascade,
    ig_media_id        text not null unique,
    media_type         text,
    media_product_type text,
    caption            text,
    permalink          text,
    thumbnail_url      text,
    posted_at          timestamptz,
    like_count         integer,
    comments_count     integer,
    is_sponsored       boolean not null default false,
    brand_name         text,
    sponsored_at       timestamptz,
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now()
);
create index if not exists posts_account_posted_idx on posts (ig_account_id, posted_at desc);

-- --------------------------------------------------------- post_metrics
-- One snapshot of Instagram insights per analysis run (or baseline refresh).
create table if not exists post_metrics (
    id          bigserial primary key,
    post_id     uuid not null references posts(id) on delete cascade,
    captured_at timestamptz not null default now(),
    reach       integer,
    views       integer,
    likes       integer,
    comments    integer,
    saves       integer,
    shares      integer
);
create index if not exists post_metrics_post_idx on post_metrics (post_id, captured_at desc);

-- -------------------------------------------------------- analysis_runs
create table if not exists analysis_runs (
    id             uuid primary key default gen_random_uuid(),
    post_id        uuid not null references posts(id) on delete cascade,
    run_kind       text not null,                 -- initial | 24h | 72h | 7d | manual
    status         text not null default 'queued' check (status in ('queued', 'running', 'done', 'failed')),
    total_comments integer,
    spam_removed   integer,
    llm_used       boolean not null default false,
    error          text,
    started_at     timestamptz,
    finished_at    timestamptz,
    created_at     timestamptz not null default now()
);
create index if not exists analysis_runs_post_idx on analysis_runs (post_id, created_at desc);

-- ------------------------------------------------------- comment_labels
-- Classification cache: each comment is classified once, re-runs only
-- classify new comments. Commenter identity is never stored; the comment id
-- is stored as a salted hash. Raw text is purged after 30 days.
create table if not exists comment_labels (
    id           bigserial primary key,
    post_id      uuid not null references posts(id) on delete cascade,
    comment_hash text not null,
    category     text not null check (category in ('buying_intent', 'question', 'objection', 'praise', 'other', 'spam', 'own')),
    language     text,
    confidence   real,
    topic        text,
    like_count   integer not null default 0,
    text_excerpt text,                           -- nulled by the retention job
    commented_at timestamptz,
    created_at   timestamptz not null default now(),
    unique (post_id, comment_hash)
);
create index if not exists comment_labels_created_idx on comment_labels (created_at) where text_excerpt is not null;

-- ------------------------------------------------------------ baselines
create table if not exists baselines (
    ig_account_id       uuid primary key references ig_accounts(id) on delete cascade,
    computed_at         timestamptz not null default now(),
    sample_size         integer not null default 0,
    median_reach        real,
    median_saves        real,
    median_shares       real,
    median_likes        real,
    median_comments     real,
    median_comment_rate real,
    samples             jsonb not null default '[]'::jsonb
);

-- -------------------------------------------------------------- reports
create table if not exists reports (
    id         uuid primary key default gen_random_uuid(),
    post_id    uuid not null unique references posts(id) on delete cascade,
    user_id    uuid not null references users(id) on delete cascade,
    slug       text not null unique,
    status     text not null default 'processing' check (status in ('processing', 'ready', 'failed')),
    score      integer,
    verdict    text,
    data       jsonb not null default '{}'::jsonb,
    is_public  boolean not null default true,
    view_count integer not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists reports_user_idx on reports (user_id, created_at desc);

-- ----------------------------------------------------------------- jobs
-- Minimal Postgres job queue (no Redis needed). Workers claim with an
-- optimistic UPDATE ... WHERE status = 'queued', so many workers are safe.
create table if not exists jobs (
    id           bigserial primary key,
    kind         text not null,
    payload      jsonb not null default '{}'::jsonb,
    status       text not null default 'queued' check (status in ('queued', 'running', 'done', 'failed')),
    run_at       timestamptz not null default now(),
    attempts     integer not null default 0,
    max_attempts integer not null default 5,
    dedupe_key   text unique,
    locked_at    timestamptz,
    last_error   text,
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);
create index if not exists jobs_ready_idx on jobs (run_at) where status = 'queued';

-- ------------------------------------------------------------------ RLS
alter table users          enable row level security;
alter table ig_accounts    enable row level security;
alter table posts          enable row level security;
alter table post_metrics   enable row level security;
alter table analysis_runs  enable row level security;
alter table comment_labels enable row level security;
alter table baselines      enable row level security;
alter table reports        enable row level security;
alter table jobs           enable row level security;
