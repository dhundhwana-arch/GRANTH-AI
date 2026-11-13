import test from 'node:test';
import assert from 'node:assert/strict';
import { fold, searchKey, searchPages, queryTerms } from '../../web/js/textnorm.mjs';

test('fold matches the server-side folding for spelling variants', () => {
  assert.equal(fold('ઍસિડ'), fold('એસિડ'));
  assert.equal(fold('હરીતદ્રવ્ય'), fold('હરિતદ્રવ્ય'));
  assert.equal(fold('૧૨૩'), '123');
  assert.equal(searchKey('પ્રકાશસંશ્લેષણ  એટલે શું ?'), searchKey('પ્રકાશસંશ્લેષણ એટલે શું'));
});

test('query terms drop question words', () => {
  assert.deepEqual(queryTerms('પર્ણરંધ્ર એટલે શું?'), [fold('પર્ણરંધ્ર')]);
});

test('searchPages finds inflected and mis-spelled-vowel forms and returns snippets', () => {
  const pages = [
    { page_number: 1, text: 'લીલી વનસ્પતિ પોતાનો ખોરાક જાતે બનાવે છે.' },
    { page_number: 2, text: 'પર્ણની સપાટી પર આવેલાં સૂક્ષ્મ છિદ્રોને પર્ણરંધ્ર કહે છે. પર્ણરંધ્ર દ્વારા વાયુઓની આપ-લે થાય છે.' },
  ];
  const hits = searchPages(pages, 'પર્ણરંધ્રની');
  assert.equal(hits.length, 1);
  assert.equal(hits[0].page_number, 2);
  assert.match(hits[0].snippet, /પર્ણરંધ્ર/);
  assert.equal(searchPages(pages, 'જ્વાળામુખી').length, 0);
  assert.equal(searchPages(pages, '').length, 0);
});
