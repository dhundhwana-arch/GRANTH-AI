// Feature 5 logic tests against a real IndexedDB implementation (fake-indexeddb). Browser-level offline
// behaviour (service worker, network cut) is tested separately in tests/e2e/run_e2e.mjs.
import test from 'node:test';
import assert from 'node:assert/strict';
import { IDBFactory } from 'fake-indexeddb';
import { openStore, downloadBook, OfflineError, Store, PACKAGE_FORMAT } from '../../web/js/offline-store.mjs';

const pkg = (id = 7, status = 'APPROVED') => ({
  format: PACKAGE_FORMAT,
  edition: { id, title: 'નમૂના પુસ્તક', standard: 10, subject: 'વિજ્ઞાન', edition_label: '2026', permission_status: status },
  chapters: [{ id: 1, number: 1, title: 'પોષણ', page_start: 1, page_end: 2 }, { id: 2, number: 2, title: 'શ્વસન', page_start: 3, page_end: 3 }],
  pages: [
    { page_number: 1, text: 'લીલી વનસ્પતિ પોતાનો ખોરાક જાતે બનાવે છે.' },
    { page_number: 2, text: 'પર્ણના કોષોમાં આવેલા લીલા રંગના દ્રવ્યને હરિતદ્રવ્ય કહે છે.' },
    { page_number: 3, text: 'ખોરાકનું દહન થઈને ઊર્જા મુક્ત થવાની પ્રક્રિયાને શ્વસન કહે છે.' },
  ],
  vocabulary: [],
});
const fresh = () => openStore(new IDBFactory(), 'test-' + Math.random());
const okFetch = (p) => async () => ({ ok: true, status: 200, json: async () => p });

test('download stores the book, verifies it by reading back, and lists it', async () => {
  const s = await fresh();
  assert.deepEqual(await s.listBooks(), []);
  const check = await downloadBook(s, 7, okFetch(pkg()));
  assert.equal(check.ok, true);
  assert.equal(check.pages, 3);
  const books = await s.listBooks();
  assert.equal(books.length, 1);
  assert.equal(books[0].verified, true);
  assert.ok(books[0].size_bytes > 100);
});

test('a failed download never appears as an offline book', async () => {
  const s = await fresh();
  await assert.rejects(downloadBook(s, 7, async () => { throw new TypeError('Failed to fetch'); }), (e) => e instanceof OfflineError && e.code === 'network');
  await assert.rejects(downloadBook(s, 7, async () => ({ ok: false, status: 404, json: async () => ({}) })), (e) => e.code === 'refused');
  assert.deepEqual(await s.listBooks(), []);
});

test('unauthorized or malformed packages are refused', async () => {
  const s = await fresh();
  await assert.rejects(s.saveBook(pkg(7, 'UNKNOWN')), (e) => e.code === 'not-authorized');
  await assert.rejects(s.saveBook({ ...pkg(), format: 'x' }), (e) => e.code === 'bad-package');
  await assert.rejects(s.saveBook({ ...pkg(), pages: [] }), (e) => e.code === 'bad-package');
  assert.deepEqual(await s.listBooks(), []);
});

test('open pages, navigate, chapter info and local search work with no network function at all', async () => {
  const s = await fresh();
  await s.saveBook(pkg());
  const book = await s.getBook(7);
  assert.equal((await s.getPage(7, 2)).text.includes('હરિતદ્રવ્ય'), true);
  assert.equal(s.chapterForPage(book, 3).title, 'શ્વસન');
  await assert.rejects(s.getPage(7, 99), (e) => e.code === 'no-page');
  const hits = await s.searchBook(7, 'શ્વસન');
  assert.deepEqual(hits.map((h) => h.page_number), [3]);
  assert.deepEqual((await s.searchBook(7, 'હરીતદ્રવ્યની')).map((h) => h.page_number), [2]);
  assert.equal((await s.searchBook(7, 'જ્વાળામુખી')).length, 0);
});

test('reading progress is tracked', async () => {
  const s = await fresh();
  await s.saveBook(pkg());
  assert.equal((await s.getProgress(7)).percent, 0);
  await s.setProgress(7, 1);
  await s.setProgress(7, 2);
  await s.setProgress(7, 2);
  const p = await s.getProgress(7);
  assert.deepEqual([p.last_page, p.pages_read, p.page_count, p.percent], [2, 2, 3, 67]);
});

test('delete removes the book, its pages and progress; storage usage follows', async () => {
  const s = await fresh();
  await s.saveBook(pkg(7));
  await s.saveBook(pkg(8));
  const before = await s.storageUsage({ estimate: async () => ({ usage: 90, quota: 100 }) });
  assert.equal(before.books, 2);
  assert.ok(before.book_bytes > 0);
  assert.equal(before.low, true);                    // >80% used -> storage warning
  await s.deleteBook(7);
  assert.deepEqual((await s.listBooks()).map((b) => b.edition_id), [8]);
  await assert.rejects(s.getPage(7, 1));
  const after = await s.storageUsage(null);
  assert.equal(after.books, 1);
  assert.ok(after.book_bytes < before.book_bytes);
  assert.equal(after.low, false);
});

test('re-download replaces pages instead of duplicating them', async () => {
  const s = await fresh();
  await s.saveBook(pkg());
  const p2 = pkg();
  p2.pages = p2.pages.slice(0, 2);
  const check = await s.saveBook(p2);
  assert.equal(check.pages, 2);
  await assert.rejects(s.getPage(7, 3));
});

test('only verified answers are saved for low-internet reuse, keyed by edition/chapter/mode', async () => {
  const s = await fresh();
  const scope = { edition_id: 7, chapter_id: null, mode: 'auto', marks: null };
  const good = { status: 'answered', verification: { verified: true }, answer: { text: 'x' } };
  assert.equal(await s.saveAnswer('શ્વસન એટલે શું?', scope, { status: 'abstained', verification: { verified: false } }), false);
  assert.equal(await s.saveAnswer('શ્વસન એટલે શું?', scope, { ...good, verification: { verified: false } }), false);
  assert.equal(await s.saveAnswer('શ્વસન એટલે શું?', scope, good), true);
  assert.equal((await s.getAnswer('શ્વસન  એટલે શું ?', scope)).result.answer.text, 'x');
  assert.equal(await s.getAnswer('શ્વસન એટલે શું?', { ...scope, edition_id: 8 }), null);
  assert.equal(await s.getAnswer('શ્વસન એટલે શું?', { ...scope, mode: 'detailed' }), null);
  assert.notEqual(Store.answerKey('a', scope), Store.answerKey('a', { ...scope, chapter_id: 3 }));
});
