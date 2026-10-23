"""One-off: check the new Supabase project's health from GitHub Actions'
network path, since the local sandbox is hanging/failing to resolve it.
Not a permanent script."""
import requests

r = requests.get(
    "https://ipeehclwjsmiykyyythc.supabase.co/rest/v1/products",
    headers={"apikey": "sb_publishable_-sFams7w7fCnQbVWt0UCaw_RzIlJ-Iu"},
    params={"select": "count"},
    timeout=20,
)
print("status:", r.status_code)
print("body:", r.text[:500])
