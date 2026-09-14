const CACHE_NAME = 'tagcheck-viewer-v10-fresh-assets';
const APP_SHELL = [
  './',
  './index.html',
  './styles.css',
  './app.js',
  './config.js',
  './manifest.webmanifest',
  './public/icons/icon.svg',
  './public/icons/icon-192.png',
  './public/icons/icon-512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL.map((url) => new Request(url, { cache: 'reload' })))));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key.startsWith('tagcheck-viewer-') && key !== CACHE_NAME).map((key) => caches.delete(key)))).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  // A shared URL cache must never supply another session's company response.
  if (event.request.headers.has('Authorization')) {
    event.respondWith(fetch(event.request));
    return;
  }
  const isSameOrigin = url.origin === self.location.origin;
  const isAppShell = isSameOrigin && (url.pathname.endsWith('/') || url.pathname.endsWith('/index.html') || /\.(css|js|webmanifest|png|svg)$/.test(url.pathname));
  const isApiRequest = isSameOrigin && /\/api\//.test(url.pathname);

  if (isAppShell) {
    event.respondWith(
      fetch(event.request, { cache: 'no-store' })
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy)));
          }
          const headers = new Headers(response.headers);
          headers.set('Cache-Control', 'no-store');
          return new Response(response.body, {
            status: response.status, statusText: response.statusText, headers
          });
        })
        .catch(async () => {
          const cache = await caches.open(CACHE_NAME);
          const cached = await cache.match(event.request);
          if (cached) return cached;
          if (event.request.mode === 'navigate') return cache.match('./index.html');
          return Response.error();
        })
    );
    return;
  }

  if (isApiRequest) {
    event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => {
        if (isSameOrigin) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        }
        return response;
      });
    })
  );
});
