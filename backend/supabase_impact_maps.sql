create table if not exists impact_maps (
  map_id text primary key,
  title text not null default '',
  graph_data text not null default '{}',
  event_kind text not null default '',
  event_id text not null default '',
  updated_at timestamptz not null default now()
);

create index if not exists idx_impact_maps_updated on impact_maps (updated_at desc);
