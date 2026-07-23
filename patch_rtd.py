with open('cheapie-prototype.html', 'r') as f:
    content = f.read()

replacements = [
    (
        "async function fetchLiveBeer(query){\n  let url = `${SUPABASE_URL}/rest/v1/products?category=eq.beer&select=*&order=price.asc`;\n  if(query && query.trim().length && query.toLowerCase() !== 'beer'){",
        "async function fetchLiveProducts(category, query){\n  let url = `${SUPABASE_URL}/rest/v1/products?category=eq.${category}&select=*&order=price.asc`;\n  if(query && query.trim().length && query.toLowerCase() !== category){"
    ),
    (
        "  if(key === 'beer'){",
        "  if(key === 'beer' || key === 'rtd'){"
    ),
    (
        "      const rows = await fetchLiveBeer(query);",
        "      const rows = await fetchLiveProducts(key, query);"
    ),
    (
        "  if(key !== 'beer'){",
        "  if(key !== 'beer' && key !== 'rtd'){"
    ),
]

made_changes = 0
for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        made_changes += 1
    else:
        print(f"WARNING: could not find this snippet (may already be patched):\n{old[:60]}...")

with open('cheapie-prototype.html', 'w') as f:
    f.write(content)

print(f"Applied {made_changes} of {len(replacements)} replacements.")
