-- Cheapie — index products (category, price_per_litre, price)
-- Run in Supabase SQL Editor (Dashboard -> SQL Editor -> New query -> Run).
--
-- 2026-09-03: reported directly — clicking Beer (and presumably every
-- other category) intermittently showed "no products available" or hung
-- on "Searching live database...". Confirmed live: a plain query for
-- `category=eq.beer` alone (just a row count, no even the real
-- order-by) returned a real Postgres statement timeout. Same root cause
-- already documented in add_store_id_index.sql for a different query
-- shape — this session's per-branch scraping (Big Barrel, Liquorland,
-- New World, PAK'nSAVE) grew the table hugely, and fetchLiveProducts'
-- category-browse query (category=eq.X, sorted by price_per_litre then
-- price) has no index supporting it, so every single request forces a
-- full-table filter + sort. It does eventually succeed on retry
-- (confirmed: took ~25s), which is exactly the kind of "looks broken,
-- isn't" experience worth fixing at the database level instead of just
-- retrying harder client-side.
create index if not exists idx_products_category_price
  on products (category, price_per_litre nulls last, price);

-- Same reasoning as add_store_id_index.sql: refresh the planner's
-- statistics immediately after this session's several large upserts,
-- rather than waiting for autovacuum.
analyze products;
