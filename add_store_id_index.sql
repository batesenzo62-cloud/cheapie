-- Cheapie — index products.store_id
-- Run this in the Supabase SQL Editor (Dashboard → SQL Editor → New query).
--
-- 2026-07-30: showStoreSheet() queries `products?store_id=eq.<uuid>&order=
-- price.asc` every time a store pin is clicked. There was never an index
-- on store_id, which was fine while the table was small — but after this
-- session's per-branch scraping work grew it to ~200K rows in one big
-- burst, that combination (filter on an unindexed column + sort the
-- matches) hit an actual Postgres statement timeout for real (confirmed:
-- a plain curl of that exact query returned a 500 with "canceling
-- statement due to statement timeout", code 57014, right after the bulk
-- upsert — it succeeded again on retry once, but stayed a live risk of
-- recurring under load or after future large upserts). An indexed lookup
-- avoids the full-table sort entirely.
create index if not exists idx_products_store_id on products (store_id, price);

-- Refresh the planner's statistics immediately rather than waiting for
-- autovacuum to get around to it — the 202K-row upsert this session was
-- exactly the kind of sudden shift in table size/shape that stale
-- statistics produce bad query plans around.
analyze products;
