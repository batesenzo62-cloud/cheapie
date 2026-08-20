"""One-off: dump raw HTML around the 'Billy Maverick 6pk Cans' product card
on a live Bottle-O RTD page to find exactly why the scraper captures $3.50
instead of the real price. Delete after use."""
import sys, re
sys.path.insert(0, ".")
import scrape_bottleo_products as bo
import requests

base = bo.base_url("whangaparaoa")
depts = bo.get_departments(base)
dept_id = depts.get("rtd")
url = f"{base}/search?q%5B%5D=category%3A{dept_id}"
r = requests.get(url, headers=bo.HEADERS, timeout=20)
html = r.text

idx = html.find("Billy Maverick 6pk Cans")
print("found at index:", idx)
if idx == -1:
    idx = html.find("billy-maverick-rtd-billy-maverick-6pk-cans")
    print("found via URL slug at index:", idx)

# Print generous window before and after
start = max(0, idx - 400)
end = min(len(html), idx + 1200)
print(html[start:end])
