"""One-off: try to verify one New World price directly against the source. Delete after use."""
import requests
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
url = "https://www.newworld.co.nz/shop/product/5005625_ea_000?name=haagen-german-style-lager-bottles-12-x-330ml"
try:
    r = requests.get(url, headers=HEADERS, timeout=20)
    print(f"status={r.status_code} bytes={len(r.content)}")
    print(r.text[:1500])
except Exception as e:
    print(f"error: {e}")
