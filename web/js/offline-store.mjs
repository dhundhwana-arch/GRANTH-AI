// Offline textbook library on IndexedDB (works in Android Chrome / WebView, Firefox, Safari).
// A book counts as "offline" ONLY after it has been written and read back successfully (verifyBook).
import { fold, searchPages, searchKey } from './textnorm.mjs';

const DB_NAME = 'granth-offline';
const DB_VERSION = 1;
export const PACKAGE_FORMAT = 'granth-offline-package/1';

function req(r) {
  return new Promise((resolve, reject) => { r.onsuccess = () => resolve(r.result); r.onerror = () => reject(r.error); });
}
function done(tx) {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error || new Error('transaction aborted'));
  });
}

export class OfflineError extends Error {
  constructor(code, message) { super(message); this.code = code; }
}

export async function openStore(idb = globalThis.indexedDB, name = DB_NAME) {
  if (!idb) throw new OfflineError('unsupported', 'IndexedDB is not available in this browser');
  const open = idb.open(name, DB_VERSION);
  open.onupgradeneeded = () => {
    const db = open.result;
    if (!db.objectStoreNames.contains('books')) db.createObjectStore('books', { keyPath: 'edition_id' });
    if (!db.objectStoreNames.contains('pages')) {
      const s = db.createObjectStore('pages', { keyPath: ['edition_id', 'page_number'] });
      s.createIndex('by_edition', 'edition_id');
    }
    if (!db.objectStoreNames.contains('progress')) db.createObjectStore('progress', { keyPath: 'edition_id' });
    if (!db.objectStoreNames.contains('answers')) db.createObjectStore('answers', { keyPath: 'key' });
  };
  const db = await req(open);
  return new Store(db);
}

export class Store {
  constructor(db) { this.db = db; }

  /** Write a downloaded package, then read it back. Throws (and removes partial data) if verification fails. */
  async saveBook(pkg) {
    if (!pkg || pkg.format !== PACKAGE_FORMAT) throw new OfflineError('bad-package', 'unknown package format');
    if (!pkg.edition || pkg.edition.permission_status !== 'AUTHORIZED') {
      throw new OfflineError('not-authorized', 'only authorized textbooks can be stored offline');
    }
    if (!Array.isArray(pkg.pages) || !pkg.pages.length) throw new OfflineError('bad-package', 'package has no pages');
    const id = pkg.edition.id;
    const bytes = new TextEncoder().encode(JSON.stringify(pkg)).length;
    try {
      const tx = this.db.transaction(['books', 'pages'], 'readwrite');
      const pages = tx.objectStore('pages');
      const old = await req(pages.index('by_edition').getAllKeys(id));
      for (const k of old) pages.delete(k);
      for (const p of pkg.pages) pages.put({ edition_id: id, page_number: p.page_number, text: p.text, folded: fold(p.text) });
      tx.objectStore('books').put({
        edition_id: id, edition: pkg.edition, chapters: pkg.chapters || [], vocabulary: pkg.vocabulary || [],
        page_count: pkg.pages.length, size_bytes: bytes, downloaded_at: new Date().toISOString(), verified: false,
      });
      await done(tx);
    } catch (e) {
      await this.deleteBook(id).catch(() => {});
      const quota = e && (e.name === 'QuotaExceededError' || /quota/i.test(String(e.message)));
      throw new OfflineError(quota ? 'quota' : 'write-failed', quota ? 'not enough storage space' : String(e && e.message || e));
    }
    const check = await this.verifyBook(id);
    if (!check.ok) {
      await this.deleteBook(id);
      throw new OfflineError('verify-failed', `stored ${check.pages} of ${pkg.pages.length} pages`);
    }
    return check;
  }

  async verifyBook(id) {
    const book = await this.getBook(id);
    if (!book) return { ok: false, pages: 0 };
    const n = await req(this.db.transaction('pages').objectStore('pages').index('by_edition').count(id));
    const first = await this.getPage(id, book.first_page || 1).catch(() => null);
    const ok = n === book.page_count && n > 0;
    if (ok && !book.verified) {
      const tx = this.db.transaction('books', 'readwrite');
      tx.objectStore('books').put({ ...book, verified: true });
      await done(tx);
    }
    return { ok, pages: n, expected: book.page_count, size_bytes: book.size_bytes, sample: first ? first.text.slice(0, 40) : null };
  }

  async listBooks() {
    return (await req(this.db.transaction('books').objectStore('books').getAll())).filter((b) => b.verified);
  }

  getBook(id) { return req(this.db.transaction('books').objectStore('books').get(id)); }

  async getPage(id, pageNumber) {
    const p = await req(this.db.transaction('pages').objectStore('pages').get([id, pageNumber]));
    if (!p) throw new OfflineError('no-page', 'page not stored offline');
    return p;
  }

  async getPages(id) {
    const rows = await req(this.db.transaction('pages').objectStore('pages').index('by_edition').getAll(id));
    return rows.sort((a, b) => a.page_number - b.page_number);
  }

  async searchBook(id, query) { return searchPages(await this.getPages(id), query); }

  chapterForPage(book, pageNumber) {
    return (book.chapters || []).find((c) => pageNumber >= c.page_start && pageNumber <= c.page_end) || null;
  }

  async deleteBook(id) {
    const tx = this.db.transaction(['books', 'pages', 'progress'], 'readwrite');
    const pages = tx.objectStore('pages');
    const keys = await req(pages.index('by_edition').getAllKeys(id));
    for (const k of keys) pages.delete(k);
    tx.objectStore('books').delete(id);
    tx.objectStore('progress').delete(id);
    await done(tx);
  }

  async setProgress(id, pageNumber) {
    const tx = this.db.transaction('progress', 'readwrite');
    const s = tx.objectStore('progress');
    const cur = (await req(s.get(id))) || { edition_id: id, pages_read: [] };
    if (!cur.pages_read.includes(pageNumber)) cur.pages_read.push(pageNumber);
    cur.last_page = pageNumber;
    cur.updated_at = new Date().toISOString();
    s.put(cur);
    await done(tx);
    return cur;
  }

  async getProgress(id) {
    const book = await this.getBook(id);
    const cur = (await req(this.db.transaction('progress').objectStore('progress').get(id))) || { pages_read: [], last_page: null };
    const total = book ? book.page_count : 0;
    return { last_page: cur.last_page || null, pages_read: cur.pages_read.length, page_count: total,
             percent: total ? Math.round((100 * cur.pages_read.length) / total) : 0 };
  }

  async storageUsage(storageManager = (globalThis.navigator && globalThis.navigator.storage)) {
    const books = await this.listBooks();
    const out = { books: books.length, book_bytes: books.reduce((a, b) => a + (b.size_bytes || 0), 0), usage: null, quota: null, low: false };
    if (storageManager && storageManager.estimate) {
      try {
        const e = await storageManager.estimate();
        out.usage = e.usage ?? null;
        out.quota = e.quota ?? null;
        out.low = !!(e.quota && e.usage / e.quota > 0.8);
      } catch (_) { /* estimate unsupported */ }
    }
    return out;
  }

  // ---- verified answers saved on the device for low-internet use -------------------------------
  static answerKey(question, scope) {
    return [searchKey(question), scope.edition_id || '', scope.chapter_id || '', scope.mode || 'auto', scope.marks || ''].join('|');
  }

  async saveAnswer(question, scope, result) {
    if (!result || result.status !== 'answered' || !result.verification || !result.verification.verified) return false;
    const tx = this.db.transaction('answers', 'readwrite');
    tx.objectStore('answers').put({ key: Store.answerKey(question, scope), question, scope, result, saved_at: new Date().toISOString() });
    await done(tx);
    return true;
  }

  async getAnswer(question, scope) {
    return (await req(this.db.transaction('answers').objectStore('answers').get(Store.answerKey(question, scope)))) || null;
  }
}

/** Download + store + verify. `fetchFn` is injectable for tests. */
export async function downloadBook(store, editionId, fetchFn = globalThis.fetch) {
  let res;
  try {
    res = await fetchFn(`/api/editions/${editionId}/package`);
  } catch (e) {
    throw new OfflineError('network', 'download failed - no connection');
  }
  if (!res.ok) throw new OfflineError('refused', `server refused the download (HTTP ${res.status})`);
  const pkg = await res.json();
  return store.saveBook(pkg);
}
