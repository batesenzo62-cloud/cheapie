import asyncio, json
from playwright.async_api import async_playwright
import requests

async def get_terms():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://www.liquorfy.co.nz/terms", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(1000)
        text = await page.inner_text("body")
        print("=== TERMS PAGE TEXT ===")
        print(text[:6000])
        await browser.close()

def get_openapi():
    r = requests.get("https://api.liquorfy.co.nz/openapi.json", timeout=20)
    spec = r.json()
    print("\n=== /products GET params ===")
    params = spec["paths"]["/products"]["get"].get("parameters", [])
    for p in params:
        print(f"  {p.get('name')}: required={p.get('required')} schema={p.get('schema')}")
    print("\n=== schemas relevant to product/price/store ===")
    for name, schema in spec.get("components", {}).get("schemas", {}).items():
        if any(k in name for k in ["Product", "Price", "Store"]):
            print(f"--- {name} ---")
            print(json.dumps(schema, indent=None)[:1500])
            print()

asyncio.run(get_terms())
get_openapi()
