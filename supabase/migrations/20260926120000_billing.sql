-- Razorpay subscriptions

create table if not exists subscriptions (
    id                       uuid primary key default gen_random_uuid(),
    user_id                  uuid not null references users(id) on delete cascade,
    provider                 text not null default 'razorpay',
    provider_subscription_id text not null unique,
    provider_plan_id         text not null,
    plan                     text not null check (plan in ('pro', 'pro_plus')),
    interval                 text not null check (interval in ('monthly', 'yearly')),
    status                   text not null default 'created',   -- Razorpay status: created, authenticated, active, pending, halted, cancelled, completed, expired
    current_start            timestamptz,
    current_end              timestamptz,
    cancel_at_cycle_end      boolean not null default false,
    last_payment_id          text,
    raw                      jsonb not null default '{}'::jsonb,
    created_at               timestamptz not null default now(),
    updated_at               timestamptz not null default now()
);
create index if not exists subscriptions_user_idx on subscriptions (user_id, created_at desc);

-- Every webhook delivery, keyed by Razorpay's event id, so retries are idempotent.
create table if not exists billing_events (
    id          bigserial primary key,
    provider    text not null default 'razorpay',
    event_id    text not null unique,
    event_type  text not null,
    payload     jsonb not null,
    processed   boolean not null default false,
    error       text,
    received_at timestamptz not null default now()
);

alter table subscriptions  enable row level security;
alter table billing_events enable row level security;
