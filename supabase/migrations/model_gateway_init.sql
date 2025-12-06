-- OmniRAG Model Gateway initial schema
-- Safe for Supabase Postgres

-- Extensions
create extension if not exists pgcrypto;

-- Enums
do $$ begin
  if not exists (select 1 from pg_type where typname = 'model_stack') then
    create type model_stack as enum ('cn','overseas','local');
  end if;
end $$;

do $$ begin
  if not exists (select 1 from pg_type where typname = 'model_category') then
    create type model_category as enum ('llm','embedding','reranker','vision');
  end if;
end $$;

do $$ begin
  if not exists (select 1 from pg_type where typname = 'environment') then
    create type environment as enum ('dev','test','prod');
  end if;
end $$;

do $$ begin
  if not exists (select 1 from pg_type where typname = 'provider_status') then
    create type provider_status as enum ('active','inactive');
  end if;
end $$;

do $$ begin
  if not exists (select 1 from pg_type where typname = 'auth_type') then
    create type auth_type as enum ('api_key','oauth','none');
  end if;
end $$;

do $$ begin
  if not exists (select 1 from pg_type where typname = 'task_type') then
    create type task_type as enum ('chat','embedding','rerank','image','other');
  end if;
end $$;

do $$ begin
  if not exists (select 1 from pg_type where typname = 'fallback_strategy') then
    create type fallback_strategy as enum ('priority','round_robin','weighted');
  end if;
end $$;

-- Updated timestamp trigger
create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- Model Providers
create table if not exists model_providers (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  display_name text,
  stack model_stack not null,
  category model_category not null,
  endpoint text not null,
  status provider_status not null default 'active',
  priority int not null default 0,
  tags jsonb not null default '{}',
  parameters jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (name, stack, category)
);

create index if not exists idx_model_providers_stack on model_providers(stack);
create index if not exists idx_model_providers_category on model_providers(category);
create index if not exists idx_model_providers_status on model_providers(status);
create index if not exists idx_model_providers_priority on model_providers(priority);

create trigger trg_model_providers_updated
before update on model_providers
for each row execute procedure set_updated_at();

-- Credentials per environment (store only metadata + ciphertext)
create table if not exists model_credentials (
  id uuid primary key default gen_random_uuid(),
  provider_id uuid not null references model_providers(id) on delete cascade,
  env environment not null,
  auth auth_type not null default 'api_key',
  key_name text,
  key_last4 text,
  secret_ciphertext bytea,
  rate_limit_rps int,
  quota_limit int,
  quota_window text,
  billing_info jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (provider_id, env)
);

create index if not exists idx_model_credentials_provider_env on model_credentials(provider_id, env);

create trigger trg_model_credentials_updated
before update on model_credentials
for each row execute procedure set_updated_at();

-- Metrics (aggregated windows)
create table if not exists model_metrics (
  id bigserial primary key,
  provider_id uuid not null references model_providers(id) on delete cascade,
  env environment not null,
  window_start timestamptz not null,
  window_end timestamptz not null,
  ttft_ms numeric(10,2),
  throughput_tps numeric(10,2),
  error_rate numeric(5,4),
  calls bigint,
  token_in bigint,
  token_out bigint,
  created_at timestamptz not null default now()
);

create index if not exists idx_model_metrics_window on model_metrics(provider_id, env, window_start);

-- Task Bindings with fallback
create table if not exists task_bindings (
  id uuid primary key default gen_random_uuid(),
  task_name text not null,
  task_type task_type not null,
  env environment not null,
  stack model_stack not null,
  primary_provider_id uuid not null references model_providers(id),
  backup_provider_ids uuid[],
  fallback fallback_strategy not null default 'priority',
  routing_rules jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (task_name, task_type, env, stack)
);

create index if not exists idx_task_bindings_task on task_bindings(env, task_name);

create trigger trg_task_bindings_updated
before update on task_bindings
for each row execute procedure set_updated_at();

-- Audit Logs
create table if not exists audit_logs (
  id bigserial primary key,
  actor_id uuid,
  actor_name text,
  action text not null,
  resource_type text not null,
  resource_id uuid,
  diff jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_audit_logs_resource on audit_logs(resource_id);
create index if not exists idx_audit_logs_created on audit_logs(created_at);
