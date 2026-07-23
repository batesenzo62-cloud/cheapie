with open('cheapie-prototype.html', 'r') as f:
    content = f.read()

replacements = [
    ("onclick=\"quickSearch('Beer')\"", "onclick=\"quickSearch('Beer','beer')\""),
    ("onclick=\"quickSearch('RTD')\"", "onclick=\"quickSearch('RTD','rtd')\""),
]

made = 0
for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        made += 1
    else:
        print("WARNING not found:", old)

with open('cheapie-prototype.html', 'w') as f:
    f.write(content)

print(f"Applied {made} of {len(replacements)} replacements.")
