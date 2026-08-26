"""One-off: sanity check whether the 0-hit domain-guessing result means
"no more branches online" or "script bug" — test a few known-plausible
simple cases directly. Delete after use."""
import requests
HEADERS = {"User-Agent": "Mozilla/5.0"}
candidates = [
    "https://thirstyliquorkatikati.co.nz",
    "https://thirstyliquorhuntly.co.nz",
    "https://thirstyliquoroamaru.co.nz",
    "https://thirstyliquormtmaunganui.co.nz",
    "https://thirstyliquorrotorua.co.nz",
    "https://thirstyliquorhornby.co.nz",
    "https://thirstyliquortepuke.co.nz",
]
for url in candidates:
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        print(f"{url} -> status {r.status_code}, bytes {len(r.content)}")
    except Exception as e:
        print(f"{url} -> error: {e}")
