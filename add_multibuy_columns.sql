-- Cheapie — multi-buy deal columns ("2 for $20", "Any 3 for $30")
-- Run in Supabase SQL Editor (Dashboard -> SQL Editor -> New query -> Run).

alter table products add column if not exists multibuy_quantity integer;
alter table products add column if not exists multibuy_total_price numeric;

-- Same grants add_price_per_litre_columns.sql needed for its new columns —
-- custom columns on this table have needed this explicitly before the
-- anon/service_role keys could use them.
grant select on public.products to anon, authenticated;
grant all on public.products to service_role;
