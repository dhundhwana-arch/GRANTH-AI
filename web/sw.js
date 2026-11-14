// GRANTH-AI service worker: app shell works without a connection. API calls are never cached here
// (verified answers and downloaded books live in IndexedDB, managed by the page).
const VERSION = 'granth-shell-v2';
const SHELL = ['/', '/index.html', '/styles.css', '/manifest.webmanifest', '/icon.svg', '/js/app.js', '/js/textnorm.mjs',
  '/js/offline-store.mjs', '/js/voice.mjs', '/js/imageprep.mjs', '/fonts/NotoSansGujarati-400.ttf', '/fonts/NotoSansGujarati-700.ttf'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== VERSION && k !== 'granth-vendor-v1').map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin || url.pathname.startsWith('/api/')) return;
  if (url.pathname.startsWith('/vendor/')) {          // large OCR engine files: cache on first use
    e.respondWith(caches.open('granth-vendor-v1').then(async (c) => {
      const hit = await c.match(e.request);
      if (hit) return hit;
      const res = await fetch(e.request);
      if (res.ok) c.put(e.request, res.clone());
      return res;
    }));
    return;
  }
  e.respondWith((async () => {
    const cache = await caches.open(VERSION);
    try {
      const res = await fetch(e.request);
      if (res.ok) cache.put(e.request, res.clone());
      return res;
    } catch (err) {
      const hit = await cache.match(e.request) || (e.request.mode === 'navigate' ? await cache.match('/index.html') : null);
      if (hit) return hit;
      throw err;
    }
  })());
});
