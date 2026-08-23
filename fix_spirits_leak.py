"""One-off: immediate re-patch for products already re-inserted under
spirits by a scheduled scrape since the 2026-08-21 one-time fix — the
durable load_data_to_supabase.py fix (2026-08-24) prevents this going
forward, but doesn't retroactively fix rows already live right now.
Delete after use."""
import os, requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://gkkchssgamqfavomcnoq.supabase.co")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

NAMES = [
    "Jim Beam and Cola 4.8% 330ml 6pk cans",
    "Jim Beam and Cola Zero Sugar 330ml 18pk Cans",
    "Vok Ready to Serve Cocktail Lime Mojito 5% 2L",
    "Vok Ready to Serve Cocktail Limoncello Punch 2L",
    "Vok Ready to Serve Cocktail Pina Colada 5% 2L",
    "Vok Ready to Serve Pineapple Margarita 5% 2L",
]

for name in NAMES:
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/products",
        headers={**HEADERS, "Prefer": "return=representation,count=exact"},
        params={"category": "eq.spirits", "product_name": f"eq.{name}"},
        json={"category": "rtd"},
        timeout=30,
    )
    count_range = resp.headers.get("content-range", "")
    n = count_range.split("/")[-1] if "/" in count_range else "?"
    print(f"  {resp.status_code}, {n} rows: {name!r}")
