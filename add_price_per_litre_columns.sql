-- Cheapie — pack size / price-per-litre columns
-- Run in Supabase SQL Editor (Dashboard -> SQL Editor -> New query -> Run).

alter table products add column if not exists unit_count integer default 1;
alter table products add column if not exists unit_volume_ml numeric;
alter table products add column if not exists price_per_litre numeric;

-- Included upfront this time, since custom tables/columns on this project
-- have needed explicit grants before the anon/service_role keys could use them.
grant select on public.products to anon, authenticated;
grant all on public.products to service_role;
