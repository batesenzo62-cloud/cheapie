"""
One-off test fixture — NOT a real scraper. Writes a small, real 15-row
sample (Big Barrel Albert, Palmerston North) to independent_store_prices.csv
so load_data_to_supabase.py can be tested against a single, small, easily
verified store before trusting it against the full Big Barrel/Liquorland
per-branch scrapes. Real data, captured directly from a live scrape run —
not synthetic. Delete this file once the upsert/one-store checks are done.
"""
import csv

ROWS = [
    {"store": "Big Barrel Albert, Palmerston North", "category": "beer", "product_name": "Panhead Pickup Hazy IPA 6pack Cans 330ml", "price": "$24.99", "was_price": "", "in_stock": "True", "url": "https://albert.bigbarrel.co.nz/en/panhead-pickup-hazy-ipa-6pack-cans-330ml", "fetched_at": "2026-09-01 19:18", "store_id": "0c9461d6-1f7d-4a00-b1e4-11b34a86cca1"},
    {"store": "Big Barrel Albert, Palmerston North", "category": "beer", "product_name": "ABC Empty Crate", "price": "$7.00", "was_price": "", "in_stock": "True", "url": "https://albert.bigbarrel.co.nz/en/abc-empty-crate", "fetched_at": "2026-09-01 19:18", "store_id": "0c9461d6-1f7d-4a00-b1e4-11b34a86cca1"},
    {"store": "Big Barrel Albert, Palmerston North", "category": "beer", "product_name": "Asahi 0% 6pk 330ml", "price": "$16.99", "was_price": "", "in_stock": "True", "url": "https://albert.bigbarrel.co.nz/en/asahi-0-6pk-330ml", "fetched_at": "2026-09-01 19:18", "store_id": "0c9461d6-1f7d-4a00-b1e4-11b34a86cca1"},
    {"store": "Big Barrel Albert, Palmerston North", "category": "beer", "product_name": "Asahi 6pk Big Cans 500ml", "price": "$28.99", "was_price": "", "in_stock": "True", "url": "https://albert.bigbarrel.co.nz/en/asahi-6pk-big-cans-500ml", "fetched_at": "2026-09-01 19:18", "store_id": "0c9461d6-1f7d-4a00-b1e4-11b34a86cca1"},
    {"store": "Big Barrel Albert, Palmerston North", "category": "beer", "product_name": "Asahi Nama Joki 6pack Cans 340ml", "price": "$18.99", "was_price": "", "in_stock": "True", "url": "https://albert.bigbarrel.co.nz/en/asahi-nama-joki-6pack-cans-340ml", "fetched_at": "2026-09-01 19:18", "store_id": "0c9461d6-1f7d-4a00-b1e4-11b34a86cca1"},
    {"store": "Big Barrel Albert, Palmerston North", "category": "beer", "product_name": "Asahi Super Dry 12pk Bottles 330ml", "price": "$29.99", "was_price": "", "in_stock": "True", "url": "https://albert.bigbarrel.co.nz/en/asahi-super-dry-12pk-bottles-330ml", "fetched_at": "2026-09-01 19:18", "store_id": "0c9461d6-1f7d-4a00-b1e4-11b34a86cca1"},
    {"store": "Big Barrel Albert, Palmerston North", "category": "beer", "product_name": "Asahi Super Dry 12pk Cans 330ml", "price": "$29.99", "was_price": "", "in_stock": "True", "url": "https://albert.bigbarrel.co.nz/en/asahi-super-dry-12pk-cans-330ml", "fetched_at": "2026-09-01 19:18", "store_id": "0c9461d6-1f7d-4a00-b1e4-11b34a86cca1"},
    {"store": "Big Barrel Albert, Palmerston North", "category": "beer", "product_name": "Bad Monkey 4Cpk Cans 500ml", "price": "$17.99", "was_price": "", "in_stock": "True", "url": "https://albert.bigbarrel.co.nz/en/bad-monkey-4cpk-cans-500ml", "fetched_at": "2026-09-01 19:18", "store_id": "0c9461d6-1f7d-4a00-b1e4-11b34a86cca1"},
    {"store": "Big Barrel Albert, Palmerston North", "category": "beer", "product_name": "Balter Easy Hazy 4pk Cans 375ml", "price": "$18.99", "was_price": "", "in_stock": "True", "url": "https://albert.bigbarrel.co.nz/en/balter-easy-hazy-4pk-cans-375ml", "fetched_at": "2026-09-01 19:18", "store_id": "0c9461d6-1f7d-4a00-b1e4-11b34a86cca1"},
    {"store": "Big Barrel Albert, Palmerston North", "category": "beer", "product_name": "Balter XPA 4pk Cans 375ml", "price": "$18.99", "was_price": "", "in_stock": "True", "url": "https://albert.bigbarrel.co.nz/en/balter-xpa-4pk-cans-375ml", "fetched_at": "2026-09-01 19:18", "store_id": "0c9461d6-1f7d-4a00-b1e4-11b34a86cca1"},
    {"store": "Big Barrel Albert, Palmerston North", "category": "beer", "product_name": "Becks Lager 12pk Bottles 330ml", "price": "$29.99", "was_price": "", "in_stock": "True", "url": "https://albert.bigbarrel.co.nz/en/becks-lager-12pk-bottles-330ml", "fetched_at": "2026-09-01 19:18", "store_id": "0c9461d6-1f7d-4a00-b1e4-11b34a86cca1"},
    {"store": "Big Barrel Albert, Palmerston North", "category": "beer", "product_name": "Behemoth Hopped Up On Pils 6pack Cans 330ml", "price": "$22.99", "was_price": "", "in_stock": "True", "url": "https://albert.bigbarrel.co.nz/en/behemoth-hopped-up-on-pils-6pack-cans-330ml", "fetched_at": "2026-09-01 19:18", "store_id": "0c9461d6-1f7d-4a00-b1e4-11b34a86cca1"},
    {"store": "Big Barrel Albert, Palmerston North", "category": "beer", "product_name": "Behemoth NonAlc Zero Beer 6pack 330ml Cans", "price": "$21.99", "was_price": "", "in_stock": "True", "url": "https://albert.bigbarrel.co.nz/en/behemoth-nonalc-zero-beer-6pack-330ml-cans", "fetched_at": "2026-09-01 19:18", "store_id": "0c9461d6-1f7d-4a00-b1e4-11b34a86cca1"},
    {"store": "Big Barrel Albert, Palmerston North", "category": "beer", "product_name": "Behemoth Something Hazy 6pack Cans 330ml", "price": "$24.99", "was_price": "", "in_stock": "True", "url": "https://albert.bigbarrel.co.nz/en/behemoth-something-hazy-6pack-cans-330ml", "fetched_at": "2026-09-01 19:18", "store_id": "0c9461d6-1f7d-4a00-b1e4-11b34a86cca1"},
    {"store": "Big Barrel Albert, Palmerston North", "category": "beer", "product_name": "Behemoth Something Hoppy IPA 6pack Cans 330ml", "price": "$24.99", "was_price": "", "in_stock": "True", "url": "https://albert.bigbarrel.co.nz/en/behemoth-something-hoppy-ipa-6pack-cans-330ml", "fetched_at": "2026-09-01 19:18", "store_id": "0c9461d6-1f7d-4a00-b1e4-11b34a86cca1"},
]

fieldnames = ["store", "category", "product_name", "price", "was_price", "in_stock", "url", "fetched_at", "store_id"]
with open("independent_store_prices.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(ROWS)

print(f"Wrote {len(ROWS)} test rows to independent_store_prices.csv")
