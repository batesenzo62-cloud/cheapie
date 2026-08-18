import requests

pages = [
    ("beer-cider", "https://blackbullliquorhawera.co.nz/Shop-Online/beer-cider"),
    ("spirits", "https://blackbullliquorhawera.co.nz/Shop-Online/spirits"),
    ("bourbon", "https://blackbullliquorhawera.co.nz/Shop-Online/bourbon"),
]

for name, url in pages:
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    count = resp.text.count("Summit Ultra")
    print(f"{name}: HTTP {resp.status_code}, 'Summit Ultra' appears {count} times")
    idx = resp.text.find("Summit Ultra")
    if idx != -1:
        print(f"  context: ...{resp.text[max(0,idx-100):idx+150]}...")
