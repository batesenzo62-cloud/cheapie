"""
One-off diagnostic: does newworld.co.nz / paknsave.co.nz expose per-store
pricing via a URL param or cookie we could drive with Firecrawl, or does
it require real interactive store selection? New World and PAK'nSAVE are
independently owned/operated per-branch (unlike centrally-priced
Woolworths), and Liquorfy's data showed real per-branch price differences
for these chains — checking whether real per-branch scraping is feasible
before spending Firecrawl credits on it. Delete after use.
"""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        requests_seen = []
        page.on("request", lambda r: requests_seen.append(r.url) if "api" in r.url or "store" in r.url.lower() else None)

        print("Loading newworld.co.nz homepage...")
        try:
            await page.goto("https://www.newworld.co.nz/", wait_until="networkidle", timeout=45000)
        except Exception as e:
            print(f"goto error (may still have partially loaded): {e}")
        await page.wait_for_timeout(2000)

        print("Page title:", await page.title())
        text = await page.inner_text("body")
        print("Body text sample (first 1500 chars):")
        print(text[:1500])

        cookies = await page.context.cookies()
        store_cookies = [c for c in cookies if "store" in c["name"].lower()]
        print("\nCookies with 'store' in the name:")
        for c in store_cookies:
            print(f"  {c['name']} = {c['value']}")

        print("\nRequests seen with 'api' or 'store' in the URL (first 20):")
        for u in requests_seen[:20]:
            print(f"  {u}")

        # Try a known category URL directly, see what store context it defaults to
        print("\n\nLoading a category page directly...")
        try:
            await page.goto("https://www.newworld.co.nz/shop/category/beer-wine-and-cider/beer", wait_until="networkidle", timeout=45000)
        except Exception as e:
            print(f"goto error: {e}")
        await page.wait_for_timeout(2000)
        text2 = await page.inner_text("body")
        print(text2[:2000])

        await browser.close()

asyncio.run(main())
