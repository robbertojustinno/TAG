const CACHE_NAME = 'tagcheck-admin-offline-multiempresa-v1';
const APP_SHELL = [
  './',
  './index.html',
  './styles.css',
  './config.js',
  './company-admin.js',
  './superadmin.js',
  './offline-store.js',
  './offline-integration.js',
  './app.js',
  './public/logo.png',
  './public/favicon.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(key => key.startsWith('tagcheck-admin-') && key !== CACHE_NAME)
          .map(key => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);

  // Never cache API/authenticated data. Tenant data lives in the company-scoped
  // IndexedDB managed by offline-store.js, not in the shared Service Worker cache.
  if (request.method !== 'GET' || request.headers.has('Authorization') ||
      url.origin !== self.location.origin || /\/api\//.test(url.pathname)) return;

  const isShell = request.mode === 'navigate' ||
    /\.(html|css|js|png|svg|webp)$/.test(url.pathname);

  if (!isShell) return;

  event.respondWith(
    fetch(request, { cache: 'no-store' })
      .then(response => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(request, copy)).catch(() => null);
        return response;
      })
      .catch(async () => {
        const cached = await caches.match(request);
        if (cached) return cached;
        if (request.mode === 'navigate') return caches.match('./index.html');
        throw new Error('Recurso indisponível offline.');
      })
  );
});
