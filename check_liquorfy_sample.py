"""
One-off diagnostic: fetch a few pages from liquorfy.co.nz (a competitor
price-comparison site) to inspect its structure and pull sample product
prices, before deciding whether it's worth scraping. Not part of the app —
delete after use, same as this project's other one-off check_*.py scripts.

HOW TO RUN:
    python3 check_liquorfy_sample.py
"""
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def main():
    for url in [
        "https://www.liquorfy.co.nz/",
        "https://www.liquorfy.co.nz/sitemap.xml",
    ]:
        print(f"=== {url} ===")
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            print(f"status={r.status_code} bytes={len(r.content)}")
            print(r.text[:6000])
        except Exception as e:
            print(f"error: {e}")
        print()


if __name__ == "__main__":
    main()
