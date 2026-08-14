import requests

resp = requests.get("https://thirstyliquordunedin.co.nz", headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
print("HTTP", resp.status_code)
text = resp.text
for needle in ["George Street", "Main South Rd", "Concord", "Gordon Rd", "Mosgiel", "address"]:
    idx = text.lower().find(needle.lower())
    if idx != -1:
        print(f"'{needle}' found at {idx}: ...{text[max(0,idx-60):idx+80]}...")
    else:
        print(f"'{needle}' NOT found")
