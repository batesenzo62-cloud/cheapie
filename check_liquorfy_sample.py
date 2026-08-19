"""
One-off diagnostic: liquorfy.co.nz (a competitor liquor price-comparison
site) is a client-side React SPA with no data in its static HTML, so this
renders it with Playwright and logs every XHR/fetch response it makes while
loading and searching, to find its underlying API and pull a few sample
product prices before deciding whether the site is worth scraping and
whether its prices are trustworthy. Not part of the app — delete after use,
same as this project's other one-off check_*.py scripts.

HOW TO RUN:
    python3 check_liquorfy_sample.py
"""
import asyncio
import json
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        responses = []

        async def on_response(resp):
            ct = resp.headers.get("content-type", "")
            if "json" in ct:
                try:
                    body = await resp.text()
                except Exception:
                    body = None
                responses.append({"url": resp.url, "status": resp.status, "body": body})

        page.on("response", lambda r: asyncio.create_task(on_response(r)))

        print("Loading homepage...")
        await page.goto("https://www.liquorfy.co.nz/", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)

        # Try a search if there's a search input on the page.
        for selector in ["input[type=search]", "input[placeholder*=earch]", "input[type=text]"]:
            try:
                el = await page.query_selector(selector)
                if el:
                    print(f"Found search input via {selector}, typing 'Steinlager'...")
                    await el.fill("Steinlager")
                    await page.wait_for_timeout(2500)
                    break
            except Exception:
                pass

        print(f"\nCaptured {len(responses)} JSON responses:\n")
        for r in responses:
            print(f"--- {r['status']} {r['url']} ---")
            if r["body"]:
                print(r["body"][:3000])
            print()

        print("\n=== Page title ===")
        print(await page.title())

        print("\n=== Visible text sample (first 3000 chars of body innerText) ===")
        text = await page.inner_text("body")
        print(text[:3000])

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
