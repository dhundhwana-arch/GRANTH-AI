// Gujarati folding for client-side (offline) search. Mirrors granth/gujarati.py `fold` + `tokenize`.
const FOLD = new Map([
  ['ઍ', 'એ'], ['ઑ', 'ઓ'], ['ૅ', 'ે'], ['ૉ', 'ો'], ['ઈ', 'ઇ'], ['ી', 'િ'], ['ઊ', 'ઉ'], ['ૂ', 'ુ'],
  ['ઁ', 'ં'], ['઼', ''], ['ઃ', ''], ['ૠ', 'ઋ'],
  ['૦', '0'], ['૧', '1'], ['૨', '2'], ['૩', '3'], ['૪', '4'], ['૫', '5'], ['૬', '6'], ['૭', '7'], ['૮', '8'], ['૯', '9'],
]);
const INVISIBLE = /[\u200b\u200c\u200d\u2060\ufeff\u00ad]/g;
const TOKEN = /[\u0A80-\u0AFF]+|[A-Za-z]+[0-9]*|[0-9]+(?:\.[0-9]+)?/g;
const STOP = new Set(['છે', 'અને', 'એટલે', 'શુ', 'શું', 'કે', 'તે', 'આ', 'એ', 'કોને', 'કહે', 'માટે', 'કયો', 'કઇ', 'કયુ', 'ના', 'નિ', 'નુ', 'નો'].map(fold));

export function fold(text) {
  let out = '';
  for (const ch of (text || '').normalize('NFC').replace(INVISIBLE, '')) out += FOLD.has(ch) ? FOLD.get(ch) : ch;
  return out.toLowerCase();
}

export function tokenize(text) {
  return fold(text).match(TOKEN) || [];
}

export function queryTerms(text) {
  const t = tokenize(text).filter((x) => !STOP.has(x) && x.length > 1);
  return [...new Set(t)];
}

export function searchKey(text) {
  return tokenize(text).join(' ');
}

// Strip one trailing case suffix so "પર્ણરંધ્રની" still finds "પર્ણરંધ્ર".
const SUFFIXES = ['ોમાંથી', 'ોમાં', 'માંથી', 'માં', 'નું', 'ની', 'ના', 'નો', 'ને', 'થી', 'ો', 'ા', 'ું', 'ી'].map(fold).sort((a, b) => b.length - a.length);
export function stemLite(tok) {
  for (const s of SUFFIXES) if (tok.length - s.length >= 3 && tok.endsWith(s)) return tok.slice(0, -s.length);
  return tok;
}

/** Search page records [{page_number, text}] ; every query term must occur on the page. */
export function searchPages(pages, query, limit = 20) {
  const terms = queryTerms(query).map(stemLite);
  if (!terms.length) return [];
  const hits = [];
  for (const p of pages) {
    const folded = p.folded || fold(p.text);
    let score = 0;
    let ok = true;
    for (const t of terms) {
      const n = folded.split(t).length - 1;
      if (!n) { ok = false; break; }
      score += n;
    }
    if (!ok) continue;
    const sentences = p.text.split(/(?<=[.!?।])\s+|\n+/).filter(Boolean);
    const snippet = sentences.find((s) => terms.every((t) => fold(s).includes(t)))
      || sentences.find((s) => terms.some((t) => fold(s).includes(t))) || '';
    hits.push({ page_number: p.page_number, score, snippet: snippet.slice(0, 240) });
  }
  hits.sort((a, b) => b.score - a.score || a.page_number - b.page_number);
  return hits.slice(0, limit);
}
