# patch script
with open('load_data_to_supabase.py', 'r') as f:
    content = f.read()

old = '''def parse_price(raw):
    if not raw:
        return None
    cleaned = re.sub(r"[^0-9.]", "", str(raw))
    return float(cleaned) if cleaned else None'''

new = '''def parse_price(raw):
    if not raw:
        return None
    cleaned = re.sub(r"[^0-9.]", "", str(raw))
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None'''

if old in content:
    content = content.replace(old, new)
    with open('load_data_to_supabase.py', 'w') as f:
        f.write(content)
    print("Fixed successfully.")
else:
    print("Could not find the exact text to replace.")
