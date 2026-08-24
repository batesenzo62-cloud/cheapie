"""One-off: the generic "Bottle-O" fallback catalogue used to be Kingsland's
own real prices, duplicated under the generic name. That's now replaced by
a real national-site scrape (scrape_national_catalog()), but the old rows
never got deleted — load_data_to_supabase.py only upserts, it doesn't
remove rows a scrape stops producing. Deletes every generic "Bottle-O" row
NOT from today's fresh national-catalogue run, so only real national data
remains. Delete this script after use."""
import os, requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://gkkchssgamqfavomcnoq.supabase.co")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation,count=exact",
}

resp = requests.delete(
    f"{SUPABASE_URL}/rest/v1/products",
    headers=HEADERS,
    params={"store_name": "eq.Bottle-O", "fetched_at": "lt.2026-08-24T06:00:00"},
    timeout=60,
)
print("status:", resp.status_code)
cr = resp.headers.get("content-range", "")
print("deleted:", cr.split("/")[-1] if "/" in cr else "?")
