"""
One-off: restore the Sep 1 backup CSVs (backups/stores_backup_20260901-191508.csv,
backups/products_backup_20260901-191508.csv) into the new Supabase project after
the old one's disk-full crash. Not a permanent script.

stores.id is preserved exactly as backed up (products.store_id references it).
products.id is dropped — it's a generated identity column on the new table, and
nothing in the app depends on the old numeric ids.

Deliberately sequential, not parallel/chunked-matrix like the scrapers — the
whole reason this is needed is that hammering the database with heavy
concurrent writes crashed the old project. One script, one connection, modest
chunk size, small delay between chunks.

HOW TO RUN:
    export SUPABASE_URL="https://your-project-ref.supabase.co"
    export SUPABASE_KEY="your-service-role-key"
    python3 restore_backup_to_new_project.py
"""
import csv
import os
import time

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit("Set SUPABASE_URL and SUPABASE_KEY environment variables first.")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

CHUNK_SIZE = 2000
DELAY_BETWEEN_CHUNKS = 1.5


def post_chunk(endpoint, chunk, label):
    for attempt in range(1, 6):
        r = requests.post(endpoint, headers=HEADERS, json=chunk, timeout=120)
        if r.status_code in (200, 201):
            return
        if r.status_code >= 500 and attempt < 5:
            backoff = min(5 * (2 ** (attempt - 1)), 60)
            print(f"    {label} attempt {attempt} got {r.status_code}, retrying in {backoff}s...")
            time.sleep(backoff)
            continue
        raise SystemExit(f"{label} failed (status {r.status_code}): {r.text[:500]}")


def restore_stores():
    with open("backups/stores_backup_20260901-191508.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"Restoring {len(rows)} stores (id preserved)...")
    total = 0
    for i in range(0, len(rows), CHUNK_SIZE):
        chunk = rows[i:i + CHUNK_SIZE]
        post_chunk(f"{SUPABASE_URL}/rest/v1/stores", chunk, f"stores chunk {i // CHUNK_SIZE + 1}")
        total += len(chunk)
        print(f"  {total}/{len(rows)} stores done")
        time.sleep(DELAY_BETWEEN_CHUNKS)
    print("Stores restore complete.\n")


def restore_products():
    with open("backups/products_backup_20260901-191508.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row.pop("id", None)  # generated identity column on the new table
        # empty-string numeric/bool fields need to be real nulls, not ""
        for k, v in list(row.items()):
            if v == "":
                row[k] = None
    print(f"Restoring {len(rows)} products...")
    total = 0
    total_chunks = (len(rows) + CHUNK_SIZE - 1) // CHUNK_SIZE
    for i in range(0, len(rows), CHUNK_SIZE):
        chunk = rows[i:i + CHUNK_SIZE]
        chunk_num = i // CHUNK_SIZE + 1
        post_chunk(f"{SUPABASE_URL}/rest/v1/products", chunk, f"products chunk {chunk_num}/{total_chunks}")
        total += len(chunk)
        print(f"  chunk {chunk_num}/{total_chunks} done ({total}/{len(rows)} products)")
        time.sleep(DELAY_BETWEEN_CHUNKS)
    print("Products restore complete.")


def main():
    restore_stores()
    restore_products()
    print("\nDone. Backup fully restored to the new project.")


if __name__ == "__main__":
    main()
