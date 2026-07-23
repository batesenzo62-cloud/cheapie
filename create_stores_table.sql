-- Cheapie — stores table + product-to-store linkage
-- Run this in the Supabase SQL Editor (Dashboard → SQL Editor → New query).
-- This is schema (DDL), which the REST API / service-role key cannot run —
-- it has to go through here once, manually.

create table if not exists stores (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  address text not null,
  latitude double precision not null,
  longitude double precision not null,
  region text
);

alter table products add column if not exists store_id uuid references stores(id);

-- Public read access, so the app's anon key can query stores for the map.
alter table stores enable row level security;
create policy "Public read access" on stores for select using (true);
