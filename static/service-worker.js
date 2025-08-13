// service-worker.js — navigation-safe, static-only caching
const CACHE = 'van-checklist-v11';
const ASSETS = [
  '/manifest.json',
  '/static/styles.css?v=11',
  '/static/app.js'
  // You can add icons too, but not required for functionality:
  // '/static/icons/icon-192.png',
  // '/static/icons/icon-519.png'
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const req = event.request;

  // Always network for navigations so auth redirects work
  if (req.mode === 'navigate') {
    event.respondWith((async () => {
      try { return await fetch(req); }
      catch {
        return new Response(
          '<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">'+
          '<title>Offline</title><body><h1>Offline</h1><p>This page needs a connection. Try again when you are online.</p></body>',
          { headers: { 'Content-Type': 'text/html' } }
        );
      }
    })());
    return;
  }

  if (req.method !== 'GET') return;

  const isStatic = req.url.includes('/static/') || req.url.endsWith('/manifest.json');
  if (!isStatic) return;

  event.respondWith((async () => {
    const cached = await caches.match(req);
    if (cached) return cached;
    const res = await fetch(req);
    const cache = await caches.open(CACHE);
    cache.put(req, res.clone());
    return res;
  })());
});
