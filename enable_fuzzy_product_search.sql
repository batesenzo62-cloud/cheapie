-- Cheapie — typo-tolerant product search for the Nearby map's search bar
-- Run this in the Supabase SQL Editor (Dashboard → SQL Editor → New query).
-- This is schema (DDL) + extension enablement, which the REST API / anon
-- key cannot run — it has to go through here once, manually.

create extension if not exists pg_trgm;

-- Speeds up trigram similarity search on product_name at scale (harmless
-- while the table is still small — this is what makes it fast once it's
-- not, same reasoning as the other indexes in this project).
--
-- 2026-08-02 fix #2: this index was originally built on the raw
-- product_name column, but the function below (and this one, always)
-- filters on lower(product_name) — a different expression. Postgres can't
-- use a plain-column index to satisfy a predicate on a wrapped expression
-- like lower(...), so every search still fell back to a full-table scan
-- even after switching to the <% operator (confirmed: the RPC kept
-- returning the same 57014 statement-timeout error after that first fix
-- went live). Rebuilding the index on lower(product_name) directly — the
-- exact expression the query actually filters on — is what lets Postgres
-- use it.
drop index if exists idx_products_product_name_trgm;
create index if not exists idx_products_product_name_trgm
  on products using gin (lower(product_name) gin_trgm_ops);

-- 2026-07-25 fix: similarity() compares two strings' ENTIRE trigram sets,
-- so a short query like "vodka" (5 letters) scored against a much longer
-- product name like "Absolut Vodka 200ml" got penalized hard for the
-- length mismatch alone — even though "vodka" is a clean, exact substring
-- of it. Confirmed directly: the raw ilike substring count for "vodka" is
-- 467 rows; this function was returning only 23 of them. word_similarity()
-- is the pg_trgm function built for exactly this — "does the short query
-- match some substring/word-boundary-aligned portion of the longer text,"
-- rather than penalizing the target for simply being longer. Argument
-- order matters: word_similarity(search_term, product_name) scores how
-- well search_term matches within product_name, not the reverse.
--
-- PostgREST's REST filter syntax doesn't expose pg_trgm operators directly,
-- so this goes through an RPC function instead — the standard way to run
-- custom Postgres logic through the same anon-key REST API (POST
-- /rest/v1/rpc/search_products_fuzzy) the rest of the app already uses.
-- lower() on both sides makes this case-insensitive like the ilike search
-- it replaces.
--
-- 2026-08-02 fix: originally called word_similarity() directly, which is a
-- plain function call — it can't use idx_products_product_name_trgm, so
-- Postgres scored every row in the table by hand. Fine at the ~4,475 rows
-- this was built against; started hitting real statement timeouts once
-- this session's per-branch scraping grew the table to ~203,358 rows
-- (confirmed directly: the RPC started returning Postgres error 57014,
-- "canceling statement due to statement timeout" — not just slow). Fixed
-- by switching to pg_trgm's <% operator, which the GIN index does support,
-- so the index narrows candidates instead of a full-table scan. <%'s
-- threshold is a session setting rather than a function argument, hence
-- the set_config() call.
--
-- 2026-08-03 fix: fixing the timeout above didn't fully fix the map search
-- — confirmed directly: searching "steinlager" genuinely returned 0 rows
-- for Liquorland, despite Liquorland actually stocking it. Root cause: a
-- flat `limit 200` on raw matching rows, with no regard for which store
-- each row belongs to. A single Super Liquor branch alone can supply 10+
-- rows (one per pack-size variant of the same product), and with 130+
-- Super Liquor branches plus a dozen Thirsty Liquor branches all doing the
-- same thing, the 200-row cap filled up entirely with duplicate branches
-- of a few big chains before a chain with only one listing (Liquorland,
-- Big Barrel, Woolworths, ...) ever got a single row through — not a rare
-- edge case, this silently hid genuinely-in-stock results for any popular
-- product. Fixed by ranking matches within each store first (partitioned
-- by store_id when a row is tied to a confirmed branch, else store_name —
-- the same "confirmed branch vs. chain catalogue" distinction the app
-- already uses elsewhere) and keeping only each store's single best match,
-- *then* applying the limit — every store that has any match at all is
-- now guaranteed a slot, instead of a handful of chains crowding
-- everyone else out.
--
-- 2026-08-03 fix #2: that made the map look worse, not better — reported
-- as "red, grey and yellow everywhere". Confirmed directly: searching
-- "export" surfaced a $262.99 Teeling 18 Year whisky and a $130 Taylor's
-- tawny port as two of the results, neither of which has anything to do
-- with "export" — pure trigram-similarity noise. Forcing every store to
-- contribute its single best match (the fix above) means a store that
-- doesn't stock anything genuinely relevant now shows its best *available*
-- match no matter how weak, and a couple of wild-outlier prices like that
-- badly skew the map's three-way price banding for everyone (a $262
-- "export" drags the tier boundaries up, making mid-priced genuine matches
-- look artificially cheap by comparison). Raised the default threshold
-- 0.3 → 0.5: confirmed directly this drops both bogus matches above while
-- barely touching real coverage (141/143 rows retained for "export") and
-- real typo-tolerance still holds ("steinlger" → Steinlager, "garag" →
-- Garage Project). Known remaining limitation, not fixed by this: a very
-- short/generic typo can still occasionally out-score the intended brand
-- with a different, similarly-spelled one (e.g. "corana" surfaces
-- Corazón tequila over Corona beer for most stores) — an inherent
-- trade-off of trigram-based fuzzy search on a large, diverse catalog,
-- not something a global threshold alone can fully resolve.
--
-- 2026-08-03 fix #3: still went wrong for real — confirmed by actually
-- driving the live app (Playwright, not just curl): Liquorland showed grey
-- for "steinlager" despite genuinely stocking it. Cause: the app's own
-- map-search code separately restricted beer/RTD comparisons to 12-pack or
-- 24-pack listings only, to keep price comparison fair across stores — and
-- rn = 1 above hands back exactly one row per store with no awareness of
-- that rule, so a store whose single best-scoring match happened to be an
-- 18-pack lost its only candidate and fell back to grey.
--
-- 2026-08-03 fix #4: after three rounds of exactly this kind of
-- price-comparison edge case fighting the search, simplified the whole
-- feature at the source instead of patching around it again — the map
-- search no longer ranks or compares prices at all, it just marks a store
-- green if it stocks the searched product (see runNearbyMapSearch in
-- cheapie-prototype.html). With no price comparison or pack-size rule left
-- downstream, there's nothing for a single best-match-per-store to
-- conflict with, so this reverts to rn = 1 and drops the row cap back down
-- — simpler and faster, and correct by construction rather than by
-- catching every edge case a price ranking could hit.
-- 2026-08-12 fix: reported directly — "Steinlager Classic Bottles 24 x
-- 330mL" at $15.99 (a genuinely cheap real deal) never showed up in
-- either main search screen, even though the exact same store's other
-- Steinlager listings did. Root cause: rn = 1 keeps only ONE row per
-- store — the single best TEXT match for the search term — and Bottle-O
-- Kingsland alone had 7 different Steinlager pack sizes. Whichever one's
-- wording happened to score highest on word_similarity won that store's
-- only slot; every other pack size at that same store, including
-- whichever one was actually cheapest, was silently discarded before the
-- results ever reached the app. That's backwards for a price-comparison
-- tool — the whole point is surfacing the best deal, not the best-worded
-- listing. Raised to rn <= 10 so a store's real pack-size variety (single/
-- 6/12/15/18/24-pack/crate — genuinely up to ~7-10 for a popular product)
-- survives, while still bounding how many rows one giant chain (100+
-- branches) can flood in under the overall limit below, raised from 1000
-- to 4000 to match.
create or replace function search_products_fuzzy(search_term text, min_similarity float default 0.5)
returns setof products
language plpgsql
stable
as $$
begin
  perform set_config('pg_trgm.word_similarity_threshold', min_similarity::text, true);
  return query
    select (ranked.prod).*
    from (
      select
        prod,
        row_number() over (
          partition by coalesce(prod.store_id::text, prod.store_name)
          order by word_similarity(lower(search_term), lower(prod.product_name)) desc
        ) as rn
      from products prod
      where lower(search_term) <% lower(prod.product_name)
    ) ranked
    where ranked.rn <= 10
    limit 4000;
end;
$$;

grant execute on function search_products_fuzzy(text, float) to anon;

-- Self-check — run this block too and paste back what it prints. This is
-- deliberately NOT scoped to one product: it grabs 8 random real product
-- names from across the whole table (whatever happens to be in there,
-- any store, any category) and, for each, simulates a realistic typo by
-- swapping two adjacent letters partway through the name. score_self
-- should read ~1.0 (identical string), score_typo should read meaningfully
-- lower but still well above 0 — that's what "typo-tolerant, not exact
-- match" looks like as a number, for arbitrary products, not a cherry-
-- picked one. If this block itself errors, that error message is the
-- actual answer to "is pg_trgm enabled" — paste it back verbatim.
with sample_products as (
  select product_name from (
    select distinct product_name
    from products
    where product_name is not null and length(product_name) > 6
  ) distinct_names
  order by random()
  limit 8
),
with_typo as (
  select
    product_name,
    substr(product_name, 1, 2) || substr(product_name, 4, 1) || substr(product_name, 3, 1) || substr(product_name, 5) as typo_name
  from sample_products
)
select
  product_name,
  typo_name,
  round(word_similarity(lower(product_name), lower(product_name))::numeric, 3) as score_self,
  round(word_similarity(lower(typo_name), lower(product_name))::numeric, 3) as score_typo
from with_typo;
