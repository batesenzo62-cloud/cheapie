-- Cheapie — full schema rebuild for a fresh Supabase project
-- Run this ENTIRE script once in the new project's SQL Editor
-- (Dashboard -> SQL Editor -> New query -> paste all of this -> Run).
--
-- Reconstructed from every migration file in this repo (create_stores_table.sql,
-- add_unique_constraint.sql, add_price_per_litre_columns.sql, add_store_id_index.sql,
-- add_multibuy_columns.sql, add_multibuy_index.sql, add_category_price_index.sql,
-- enable_fuzzy_product_search.sql) plus the real column set confirmed directly
-- from backups/products_backup_20260901-191508.csv and stores_backup_20260901-191508.csv.

create extension if not exists pg_trgm;

-- ── stores ──────────────────────────────────────────────────────────────
create table if not exists stores (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  address text not null,
  latitude double precision not null,
  longitude double precision not null,
  region text
);

alter table stores enable row level security;
create policy "Public read access" on stores for select using (true);

-- ── products ────────────────────────────────────────────────────────────
create table if not exists products (
  id bigint generated always as identity primary key,
  product_name text not null,
  category text,
  store_name text,
  price numeric,
  was_price numeric,
  in_stock boolean,
  is_online boolean,
  source_url text,
  fetched_at timestamptz,
  store_id uuid references stores(id),
  unit_count integer default 1,
  unit_volume_ml numeric,
  price_per_litre numeric,
  multibuy_quantity integer,
  multibuy_total_price numeric,
  constraint products_store_name_unique unique (store_name, product_name)
);

grant select on public.products to anon, authenticated;
grant all on public.products to service_role;

-- ── indexes ─────────────────────────────────────────────────────────────
create index if not exists idx_products_store_id on products (store_id, price);
create index if not exists idx_products_category_price on products (category, price_per_litre nulls last, price);
create index if not exists idx_products_multibuy on products (multibuy_quantity) where multibuy_quantity is not null;
create index if not exists idx_products_product_name_trgm
  on products using gin (lower(product_name) gin_trgm_ops);
create index if not exists idx_products_category_name_price
  on products (category, lower(product_name), price_per_litre asc nulls last, price asc);

-- ── RPC: fuzzy product search (Nearby map search bar) ──────────────────
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
        ) as store_rn,
        row_number() over (
          partition by (
            case
              when lower(prod.store_name) like 'liquorland%' then 'Liquorland'
              when lower(prod.store_name) like 'super liquor%' then 'Super Liquor'
              when lower(prod.store_name) like 'big barrel%' then 'Big Barrel'
              when lower(prod.store_name) like 'black bull%' then 'Black Bull Liquor'
              when lower(prod.store_name) like 'vino fino%' then 'Vino Fino'
              when lower(prod.store_name) like 'thirsty liquor%' then 'Thirsty Liquor'
              when lower(prod.store_name) like 'bottle-o%' then 'Bottle-O'
              when lower(prod.store_name) like 'new world%' then 'New World'
              when lower(prod.store_name) like 'pak''nsave%' then 'PAK''nSAVE'
              when lower(prod.store_name) like 'woolworths%' then 'Woolworths'
              when lower(prod.store_name) like 'glengarry%' then 'Glengarry'
              when lower(prod.store_name) like 'liquor mart%' then 'Liquor Mart'
              else prod.store_name
            end
          )
          order by word_similarity(lower(search_term), lower(prod.product_name)) desc
        ) as chain_rn
      from products prod
      where lower(search_term) <% lower(prod.product_name)
    ) ranked
    where ranked.store_rn = 1 or (ranked.store_rn <= 10 and ranked.chain_rn <= 40)
    limit 4000;
end;
$$;

grant execute on function search_products_fuzzy(text, float) to anon;

-- ── RPC: category browse with fair per-listing representation ──────────
create or replace function browse_products_by_category(cat text, name_cap int default 5)
returns setof products
language sql
stable
as $$
  select p.*
  from (
    select distinct lower(product_name) as lname
    from products
    where category = cat
  ) names
  cross join lateral (
    select *
    from products p2
    where p2.category = cat and lower(p2.product_name) = names.lname
    order by p2.price_per_litre asc nulls last, p2.price asc
    limit name_cap
  ) p
  order by p.price_per_litre asc nulls last, p.price asc
  limit 6000;
$$;

grant execute on function browse_products_by_category(text, int) to anon;

-- Refresh planner statistics now that the tables/indexes exist, rather
-- than waiting for autovacuum once real data starts loading.
analyze products;
analyze stores;
