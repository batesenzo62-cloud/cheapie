-- Cheapie — index products.multibuy_quantity
-- Run in Supabase SQL Editor (Dashboard -> SQL Editor -> New query -> Run).
--
-- 2026-09-03: added alongside the new "Multi-buy deals only" filter in
-- the Deals tab (queries `multibuy_quantity=not.is.null` directly, no
-- category/store filter to narrow it down first) — learning from the
-- category-browse timeout found earlier today (add_category_price_
-- index.sql) rather than shipping another unindexed filter against this
-- now-huge table and waiting to be told it's broken again. A partial
-- index (only real multi-buy rows, which are a small fraction of the
-- table) keeps this cheap to maintain on every upsert.
create index if not exists idx_products_multibuy
  on products (multibuy_quantity)
  where multibuy_quantity is not null;

analyze products;
