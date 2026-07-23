with open('cheapie-prototype.html', 'r') as f:
    content = f.read()

old = """      apikey: SUPABASE_ANON_KEY,
      Authorization: `Bearer ${SUPABASE_ANON_KEY}`"""
new = "      apikey: SUPABASE_ANON_KEY"

if old in content:
    content = content.replace(old, new)
    with open('cheapie-prototype.html', 'w') as f:
        f.write(content)
    print("Fixed successfully.")
else:
    print("Could not find the exact text - may already be fixed or differ slightly.")
