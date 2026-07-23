with open('cheapie-prototype.html', 'r') as f:
    content = f.read()

old = "      const rows = await fetchLiveProducts(key, query);"
new = "      const rows = await fetchLiveProducts(key, query);\n      console.log('DEBUG key=', key, 'query=', query, 'rows.length=', rows.length);"

if old in content:
    content = content.replace(old, new)
    with open('cheapie-prototype.html', 'w') as f:
        f.write(content)
    print("Debug line added.")
else:
    print("Could not find the target line.")
