const CACHE_NAME = 'tagcheck-campo-offline-v1';
const ASSETS = ['./', './index.html', './styles.css', './app.js', './manifest.webmanifest', './public/logo.png', './public/favicon.png'];
self.addEventListener('install', e => { e.waitUntil(caches.open(CACHE_NAME).then(c => c.addAll(ASSETS))); self.skipWaiting(); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))))); self.clients.claim(); });
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (url.origin !== location.origin) return;
  e.respondWith(caches.match(e.request).then(cached => cached || fetch(e.request).then(res => { const copy = res.clone(); caches.open(CACHE_NAME).then(c => c.put(e.request, copy)); return res; }).catch(() => caches.match('./index.html'))));
});
