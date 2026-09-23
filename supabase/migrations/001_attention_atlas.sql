-- Prepared serving tables for a T&E-owned Supabase project.
-- Apply only through the explicit sync-supabase operation; Netlify never refreshes data.
create table if not exists dataset_releases (
  release_id text primary key,
  date_start date not null,
  date_end date not null,
  configuration_version text not null,
  configuration_hash text not null,
  status text not null,
  created_at timestamptz not null,
  metadata jsonb not null default '{}'::jsonb
);
create table if not exists daily_attention (
  release_id text not null references dataset_releases(release_id),
  date date not null,
  source text not null,
  topic_id text not null,
  measure text not null,
  value double precision,
  unit text not null,
  denominator double precision,
  denominator_definition text not null,
  geography text not null,
  quality_status text not null,
  completeness double precision,
  metadata jsonb not null default '{}'::jsonb,
  primary key (release_id, date, source, topic_id, measure, geography)
);
create table if not exists physical_observations (
  release_id text not null references dataset_releases(release_id),
  observation_id text not null,
  source text not null,
  metric text not null,
  observed_at date not null,
  geography text not null,
  value double precision,
  unit text not null,
  quality_status text not null,
  metadata jsonb not null default '{}'::jsonb,
  primary key (release_id, observation_id)
);
create table if not exists event_records (
  release_id text not null references dataset_releases(release_id),
  event_id text not null,
  source text not null,
  event_type text not null,
  name text not null,
  start_at timestamptz not null,
  end_at timestamptz,
  country_codes text[] not null,
  geometry jsonb,
  primary key (release_id, event_id)
);
create table if not exists layer_observations (
  release_id text not null references dataset_releases(release_id),
  observation_id text not null,
  source text not null,
  series_id text not null,
  metric text not null,
  observed_at date not null,
  geography text not null,
  geography_level text not null,
  value double precision,
  unit text not null,
  quality_status text not null,
  completeness double precision,
  revision_status text not null,
  metadata jsonb not null default '{}'::jsonb,
  primary key (release_id, observation_id)
);
create table if not exists source_snapshots (
  release_id text not null references dataset_releases(release_id),
  source text not null,
  snapshot_id text not null,
  status text not null,
  observed_start date,
  observed_end date,
  retrieved_at timestamptz not null,
  completeness double precision,
  notes text not null,
  primary key (release_id, source, snapshot_id)
);
