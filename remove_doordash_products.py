"""
Cheapie — one-off: remove DoorDash-sourced product rows.

The DoorDash scraper (scrape_blackbull_doordash.py, scrape_thirsty_
doordash.py) was removed — its coverage was real but too incomplete to
be worth it (only ever captured a partial slice of a branch's real
catalogue). This deletes the rows it already wrote, reverting those 13
branches to the same "no confirmed data" state as every other branch
without an independent website of its own.

Scoped to the exact store_ids the DoorDash scraper ever wrote to, not a
blanket "any row with doordash.com in its URL" delete — safer, and this
project has no other DoorDash-sourced data to worry about excluding.

Delete this file after running once — it's a one-time cleanup, not a
recurring job.

HOW TO RUN:
    export SUPABASE_URL="https://your-project-ref.supabase.co"
    export SUPABASE_KEY="your-service-role-or-secret-key"
    python3 remove_doordash_products.py
"""
import os
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit("Set SUPABASE_URL and SUPABASE_KEY environment variables first.")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# Every store_id the DoorDash scraper ever wrote to (Black Bull's 6
# confirmed branches + Thirsty Liquor's 7).
STORE_IDS = [
    "72722bbb-8ad9-4b0d-8f2a-d42841aea8ef",  # Black Bull Napier
    "b372a9db-560a-4143-a4e3-c67b1db65816",  # Black Bull Royal Oak
    "4de95caa-3df8-48f8-bfc8-e9a40097c78e",  # Black Bull Paraparaumu
    "37b6c687-1c7d-4991-8c36-ec42762d26ac",  # Black Bull Whitby
    "00cbb9f6-4151-4768-8ff2-0e831bbfebef",  # Black Bull Peachgrove Road
    "fb80a5e6-ed9f-4f7f-b5d7-5386f3b68298",  # Black Bull Main Steet
    "d1e06bd3-0d37-4e39-b259-1e5e5d190428",  # Thirsty Liquor Sliverdale
    "4a4142b5-d85a-4d66-a998-1b90e0ec3ab0",  # Thirsty Liquor Napier
    "b260a41d-c4ed-4d72-9744-3d7cebc7382d",  # Thirsty Liquor Takapuna
    "c4be313b-c117-426f-bc95-85548827492f",  # Thirsty Liquor Wordsworth
    "7865d1ab-e34f-4b6d-90e7-b82daf203b34",  # Thirsty Liquor Victoria Street
    "13825b74-2c9b-4564-9c79-f812767c90dc",  # Thirsty Liquor Papanui
    "5acc442a-6b52-46ec-b0e5-a43809b2bc84",  # Thirsty Liquor Remuera
]


def main():
    total_deleted = 0
    for store_id in STORE_IDS:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/products?select=id&store_id=eq.{store_id}&source_url=ilike.*doordash*",
            headers=HEADERS, timeout=20,
        )
        r.raise_for_status()
        count = len(r.json())
        if count == 0:
            continue
        resp = requests.delete(
            f"{SUPABASE_URL}/rest/v1/products?store_id=eq.{store_id}&source_url=ilike.*doordash*",
            headers={**HEADERS, "Prefer": "return=minimal"},
            timeout=30,
        )
        if resp.status_code in (200, 204):
            print(f"  {store_id}: deleted {count} rows")
            total_deleted += count
        else:
            print(f"  {store_id}: FAILED {resp.status_code} {resp.text}")

    print(f"\nDone. Deleted {total_deleted} DoorDash-sourced rows total.")


if __name__ == "__main__":
    main()
