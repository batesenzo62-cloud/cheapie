-- Cheapie — prevent duplicate products on repeated loads
-- Run in Supabase SQL Editor (Dashboard -> SQL Editor -> New query -> Run).
-- Safe to run now: confirmed zero duplicate (store_name, product_name)
-- pairs exist in the table as of this migration.

alter table products
  add constraint products_store_name_unique unique (store_name, product_name);
