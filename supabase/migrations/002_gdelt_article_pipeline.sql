-- Article-level GDELT pipeline tables.  These tables are append-only by
-- release/tagging version; the browser should read prepared aggregates.
create table if not exists gdelt_articles (
  article_id text primary key,
  canonical_url text not null,
  raw_urls jsonb not null,
  outlet_id text,
  outlet_domain text,
  outlet_edition text,
  language text,
  first_seen_at timestamptz,
  source_date timestamptz,
  published_at timestamptz,
  date_basis text not null,
  title text,
  description text,
  publishing_geography text,
  source_class text not null default 'news',
  unique (canonical_url)
);

create table if not exists gdelt_capture_membership (
  snapshot_id text not null,
  article_id text not null references gdelt_articles(article_id),
  reporting_day date not null,
  included boolean not null default true,
  reason text,
  primary key (snapshot_id, article_id, reporting_day)
);

create table if not exists gdelt_article_source_snapshots (
  snapshot_id text not null,
  article_id text not null references gdelt_articles(article_id),
  source text not null,
  source_record_id text,
  raw_reference text,
  retrieved_at timestamptz not null,
  source_version text,
  status text not null,
  metadata jsonb not null default '{}',
  primary key (snapshot_id, article_id, source)
);

create table if not exists gdelt_capture_manifests (
  snapshot_id text primary key,
  source text not null,
  requested_start date not null,
  requested_end date not null,
  language_scope jsonb not null,
  outlet_registry_version text not null,
  membership_digest text not null,
  article_count integer not null,
  excluded_count integer not null,
  ambiguous_count integer not null,
  generated_at timestamptz not null
);

create table if not exists gdelt_tag_catalog (
  tag_id text not null,
  catalog_version text not null,
  family text not null,
  label text not null,
  definition text not null,
  payload jsonb not null default '{}',
  primary key (tag_id, catalog_version)
);

create table if not exists gdelt_article_tag_assertions (
  article_id text not null references gdelt_articles(article_id),
  tag_id text not null,
  assertion_type text not null default 'mentions_theme',
  method text not null,
  result text not null,
  evaluation_status text not null,
  tagging_version text not null,
  rule_hash text not null,
  evidence_ids jsonb not null default '[]',
  primary key (article_id, tag_id, assertion_type, method, tagging_version)
);

create table if not exists gdelt_article_tags (
  article_id text not null references gdelt_articles(article_id),
  tag_id text not null,
  assertion_type text not null default 'mentions_theme',
  result text not null,
  evaluation_status text not null,
  tagging_version text not null,
  resolution_version text not null,
  assertion_ids jsonb not null default '[]',
  primary key (article_id, tag_id, assertion_type, tagging_version, resolution_version)
);

create table if not exists gdelt_tag_evidence (
  evidence_id text primary key,
  article_id text not null references gdelt_articles(article_id),
  source text not null,
  source_record_id text,
  phrase text,
  context text,
  source_field text,
  position_decile smallint,
  truncated boolean not null default false,
  captured_at timestamptz,
  metadata jsonb not null default '{}'
);

create table if not exists gdelt_events (
  event_id text primary key,
  canonical_name text not null,
  event_type text not null,
  payload jsonb not null,
  registry_version text not null
);

create table if not exists gdelt_entities (
  entity_id text primary key,
  entity_type text not null,
  canonical_name text not null,
  payload jsonb not null
);

create table if not exists gdelt_entity_aliases (
  entity_id text not null references gdelt_entities(entity_id),
  alias text not null,
  valid_from date,
  valid_to date,
  primary key (entity_id, alias)
);

create table if not exists gdelt_article_event_links (
  link_id bigserial primary key,
  article_id text not null references gdelt_articles(article_id),
  event_id text references gdelt_events(event_id),
  relation text not null,
  method text not null,
  resolution_status text not null,
  linker_version text not null,
  evidence_ids jsonb not null default '[]'
);

create table if not exists gdelt_places (
  place_id text primary key,
  name text not null,
  provider_id text,
  code_system text,
  country_code text,
  boundary_version text,
  geometry jsonb
);

create table if not exists gdelt_article_locations (
  article_id text not null references gdelt_articles(article_id),
  place_id text references gdelt_places(place_id),
  raw_name text not null,
  role text not null,
  resolution_method text not null,
  ambiguity text,
  primary key (article_id, raw_name, role)
);

create table if not exists gdelt_classification_coverage (
  article_id text not null references gdelt_articles(article_id),
  tag_family text not null,
  evaluation_status text not null,
  available_text_scope text not null,
  failure_reason text,
  tagging_version text not null,
  primary key (article_id, tag_family, tagging_version)
);

create table if not exists gdelt_daily_metrics (
  release_id text not null,
  reporting_day date not null,
  tag_id text not null default '',
  event_id text not null default '',
  metric_name text not null,
  universe_count integer not null,
  evaluable_count integer not null,
  positive_count integer not null,
  unknown_count integer not null,
  value double precision,
  filter_definition text not null,
  tagging_version text not null,
  primary key (release_id, reporting_day, tag_id, event_id, metric_name, tagging_version)
);

create index if not exists gdelt_capture_day_idx on gdelt_capture_membership(reporting_day);
create index if not exists gdelt_article_tags_tag_idx on gdelt_article_tags(tag_id, result);
create index if not exists gdelt_metrics_day_idx on gdelt_daily_metrics(reporting_day, metric_name);
