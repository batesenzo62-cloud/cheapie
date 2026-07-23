with open('cheapie-prototype.html', 'r') as f:
    content = f.read()

replacements = []

replacements.append((
    '''function quickSearch(term){
  document.getElementById('searchInput').value = term;
  doSearch(term);
}''',
    '''function quickSearch(term, category){
  document.getElementById('searchInput').value = term;
  doSearch(term, category);
}'''
))

replacements.append((
    '''async function fetchLiveProducts(category, query){
  let url = `${SUPABASE_URL}/rest/v1/products?category=eq.${category}&select=*&order=price.asc`;
  if(query && query.trim().length && query.toLowerCase() !== category){
    url += `&product_name=ilike.*${encodeURIComponent(query.trim())}*`;
  }''',
    '''async function fetchLiveProducts(category, query){
  let url = `${SUPABASE_URL}/rest/v1/products?select=*&order=price.asc`;
  if(category){
    url += `&category=eq.${category}`;
  }
  if(query && query.trim().length && query.toLowerCase() !== category){
    url += `&product_name=ilike.*${encodeURIComponent(query.trim())}*`;
  }'''
))

replacements.append((
    '''function mapDbRow(row){
  return {
    store: row.store_name,''',
    '''function mapDbRow(row){
  return {
    store: row.store_name,
    category: row.category,'''
))

replacements.append((
    '''    const subline = r.real
      ? `${r.store} · <span class="live-tag">Live</span>`''',
    '''    const subline = r.real
      ? `${r.store} · ${r.category ? r.category + ' · ' : ''}<span class="live-tag">Live</span>`'''
))

replacements.append((
    '''async function doSearch(term){
  const query = term || document.getElementById('searchInput').value || 'beer';
  const key = keyFor(query);

  document.getElementById('resultsTitle').textContent = query.length ? query : DATA[key].label;
  show('view-results');

  if(key === 'beer' || key === 'rtd'){
    document.getElementById('resultsSubtitle').textContent = 'Searching live database…';
    document.getElementById('resultsList').innerHTML = '';
    try{
      const rows = await fetchLiveProducts(key, query);
      console.log('DEBUG key=', key, 'query=', query, 'rows.length=', rows.length);
      if(rows && rows.length){
        document.getElementById('resultsSubtitle').textContent = rows.length + ' real products found in your database, sorted by price';
        renderResults(rows.map(mapDbRow), true);
        return;
      }
      document.getElementById('resultsSubtitle').textContent = 'No live matches — showing sample data instead';
    } catch(err){
      console.error(err);
      document.getElementById('resultsSubtitle').textContent = 'Could not reach the database — showing sample data instead';
    }
  }

  const data = DATA[key];
  if(key !== 'beer' && key !== 'rtd'){
    document.getElementById('resultsSubtitle').textContent = data.results.length + ' stores found near Hastings, sorted by price (sample data)';
  }
  renderResults(data.results, false);
}''',
    '''async function doSearch(term, forcedCategory){
  const query = term || document.getElementById('searchInput').value || '';
  const guessedKey = keyFor(query || 'beer');

  document.getElementById('resultsTitle').textContent = query.length ? query : DATA[guessedKey].label;
  show('view-results');
  document.getElementById('resultsSubtitle').textContent = 'Searching live database…';
  document.getElementById('resultsList').innerHTML = '';

  try{
    const rows = await fetchLiveProducts(forcedCategory || null, query);
    if(rows && rows.length){
      document.getElementById('resultsSubtitle').textContent = rows.length + ' real products found in your database, sorted by price';
      renderResults(rows.map(mapDbRow), true);
      return;
    }
  } catch(err){
    console.error(err);
  }

  const data = DATA[forcedCategory || guessedKey] || DATA['beer'];
  document.getElementById('resultsSubtitle').textContent = data.results.length + ' stores found near Hastings, sorted by price (sample data)';
  renderResults(data.results, false);
}'''
))

made = 0
for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        made += 1
    else:
        print("WARNING not found:", old[:50])

with open('cheapie-prototype.html', 'w') as f:
    f.write(content)

print(f"Applied {made} of {len(replacements)} replacements.")
