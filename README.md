# Cheapie data pipeline — starter scripts

Two scripts, because we found two different kinds of retailer websites during
the data spike:

## 1. `scrape_independent_stores.py` — works right now, no signup needed
Scrapes independent NZ liquor retailers (Vino Fino, and now also Thirsty
Liquor, Black Bull Liquor, Super Liquor, and Big Barrel — 47 of Big
Barrel's branches have their own per-branch site, scraped by the separate
scrape_bigbarrel_branches.py) that render prices
directly in server-side HTML, so this script works today with nothing to
set up beyond Python itself.

```
pip install -r requirements.txt
python scrape_independent_stores.py
```

Output: `independent_store_prices.csv`

## 2. `scrape_chain_stores_firecrawl.py` — needs your Firecrawl API key
Scrapes the big chains (New World, PAK'nSAVE) whose product listings
only appear after JavaScript runs.
Needs a free Firecrawl account — see the instructions inside the script
file itself.

```
export FIRECRAWL_API_KEY="fc-your-key-here"
python scrape_chain_stores_firecrawl.py
```

Output: `chain_store_prices.csv`

## Honest limitations right now
- These scripts run once and produce a CSV file. They don't yet update
  automatically or feed the app directly — that's the next phase, once we
  set up a real database (Supabase) and a scheduler to run these on a
  timer (e.g. nightly).
- I wrote the Firecrawl script based on their published API docs, but I
  haven't been able to run it myself (no API key, no internet access in
  my environment). If it errors on your first run, that's expected —
  just paste me the error and I'll fix it.
- Always check a site's terms of service before scraping it regularly,
  not just once for testing.

## What "next" looks like after this works
Once both scripts reliably produce a CSV of real prices, the next step is
wiring that CSV into a real database (Supabase) so the app can read from
it instead of the hardcoded sample data in the prototype — that's the
"set up real technical foundations" phase we talked about earlier.
