"""One-off: directly re-verify right now whether New World's actual shop/
pricing page is blocked, since the user is reasonably asking why we can't
just fetch it like any other URL. Delete after use."""
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"}
url = "https://www.newworld.co.nz/shop/category/beer-wine-and-cider/beer"
r = requests.get(url, headers=HEADERS, timeout=20)
print("status:", r.status_code)
print("first 500 chars of body:")
print(r.text[:500])
print("\nserver header:", r.headers.get("server"))
print("cf-ray header present:", "cf-ray" in {k.lower(): v for k,v in r.headers.items()})
