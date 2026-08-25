"""One-off: /super-specials products all show was=None despite being a
dedicated specials page — check the raw HTML around one item's price
block directly to find the actual markup. Also check a regular category
page for bundle/multi-buy promotional text ("2 for $X", "any 3 for $Y")
that our simple was/now scraper doesn't capture at all. Delete after use."""
import requests
from bs4 import BeautifulSoup
import re

HEADERS = {"User-Agent": "Mozilla/5.0"}
base = "https://alexandra.superliquor.co.nz"

r = requests.get(base + "/super-specials", headers=HEADERS, timeout=20)
soup = BeautifulSoup(r.text, "html.parser")
item = soup.select_one("div.item-box")
print("=== raw HTML of one item-box on /super-specials ===")
print(item.prettify()[:3000])

print("\n\n=== searching regular category page for bundle/multi-buy text ===")
r2 = requests.get(base + "/beer", headers=HEADERS, timeout=20)
text = r2.text
patterns = [r'\b\d+\s+for\s+\$?\d+', r'any\s+\d+\s+for', r'mix\s*(?:&|and)?\s*match', r'buy\s+\d+.{0,20}save']
for pat in patterns:
    matches = re.findall(pat, text, re.I)
    print(f"pattern {pat!r}: {matches[:10]}")
