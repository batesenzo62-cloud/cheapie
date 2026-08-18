"""
Cheapie — one-off: fix 2 Black Bull Liquor Hawera products mis-categorized
as "spirits" when they're genuinely beer.

Reported directly: clicking the Spirits category showed "Speights Summit
Ultra" (a lager) fanned out across many Black Bull branches via the
Hawera-fallback mechanism, since Hawera's own row for it is tagged
"spirits" in the database. Confirmed directly this is narrow, not a
systemic scraper bug — searched the whole products table for other common
beer-brand keywords under category=spirits (steinlager, heineken, export,
tui, monteith, corona) and every other hit was a real, correctly-tagged
spirit (Klipdrift EXPORT Brandy, WaiTUI Whisky, ...) — just these 2 rows
are genuinely wrong.

Delete this file after running once — it's a one-time data fix, not a
recurring job. Note: the next scheduled scrape.yml run may re-introduce
this if the root cause on Black Bull Hawera's own site (or this scraper's
parsing) hasn't changed — worth spot-checking again after a few days.

HOW TO RUN:
    export SUPABASE_URL="https://your-project-ref.supabase.co"
    export SUPABASE_KEY="your-service-role-or-secret-key"
    python3 fix_summit_ultra_category.py
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

STORE_ID = "bf139701-d11f-47c0-a410-0850e1f7315f"  # Black Bull Liquor Hawera
PRODUCT_NAMES = [
    "Speights Summit Ultra 12x330ml Bottles",
    "Speights Summit Ultra Lime 12x330ml Bottles",
]


def main():
    for name in PRODUCT_NAMES:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/products?select=id,product_name,category&store_id=eq.{STORE_ID}&product_name=eq.{requests.utils.quote(name)}",
            headers=HEADERS, timeout=20,
        )
        r.raise_for_status()
        rows = r.json()
        if not rows:
            print(f"  Not found: {name}")
            continue
        for row in rows:
            if row["category"] == "beer":
                print(f"  Already correct: {name}")
                continue
            resp = requests.patch(
                f"{SUPABASE_URL}/rest/v1/products?id=eq.{row['id']}",
                headers={**HEADERS, "Prefer": "return=minimal"},
                json={"category": "beer"},
                timeout=15,
            )
            if resp.status_code in (200, 204):
                print(f"  Fixed: {name} ({row['category']} -> beer)")
            else:
                print(f"  FAILED: {name}: {resp.status_code} {resp.text}")


if __name__ == "__main__":
    main()
