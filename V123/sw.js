const CACHE = 'esun-power-v123-static';
const STATIC = [
  './', './index.html', './manifest.webmanifest', './favicon.png',
  './favicon-192.png', './favicon-512.png', './logo-esun-power.png'
];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(c => c.addAll(STATIC)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const u = new URL(event.request.url);
  if (u.pathname.includes('/api/')) return;
  if (event.request.method !== 'GET' || u.origin !== self.location.origin) return;
  event.respondWith(fetch(event.request).then(r => {
    const copy = r.clone(); caches.open(CACHE).then(c => c.put(event.request, copy)); return r;
  }).catch(() => caches.match(event.request).then(r => r || caches.match('./index.html'))));
});
