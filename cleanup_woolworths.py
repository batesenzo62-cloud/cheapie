"""One-off: remove Woolworths entirely per direct request — it's the only
supermarket chain with no real store-location data at all (can't map
prices to real branches), and won't be pursued via Firecrawl going
forward. Deletes existing Woolworths product rows. Delete this script
after use."""
import os, requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://gkkchssgamqfavomcnoq.supabase.co")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Prefer": "return=representation,count=exact",
}

resp = requests.delete(
    f"{SUPABASE_URL}/rest/v1/products",
    headers=HEADERS,
    params={"store_name": "ilike.*woolworths*"},
    timeout=60,
)
print("status:", resp.status_code)
cr = resp.headers.get("content-range", "")
print("deleted:", cr.split("/")[-1] if "/" in cr else "?")
