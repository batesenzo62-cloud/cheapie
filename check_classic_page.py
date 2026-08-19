import requests
from bs4 import BeautifulSoup

resp = requests.get("https://blackbullliquorhawera.co.nz/Shop-Online/classic", headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
soup = BeautifulSoup(resp.text, "html.parser")
names = [el.get_text(strip=True) for el in soup.select("h2") if el.get_text(strip=True)]
print(f"HTTP {resp.status_code}, found {len(names)} h2 product names")
for n in names:
    print(" ", n)
