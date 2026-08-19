import requests
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
for url in ["https://www.liquorfy.co.nz/robots.txt", "https://www.liquorfy.co.nz/terms", "https://api.liquorfy.co.nz/robots.txt", "https://api.liquorfy.co.nz/docs", "https://api.liquorfy.co.nz/openapi.json"]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        print(f"=== {url} === status={r.status_code}")
        print(r.text[:2000])
    except Exception as e:
        print(f"=== {url} === error: {e}")
    print()
