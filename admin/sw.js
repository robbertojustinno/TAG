const CACHE_NAME = 'tagcheck-admin-v1-fresh-assets';

self.addEventListener('install', (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(
    keys.filter((key) => key.startsWith('tagcheck-admin-') && key !== CACHE_NAME)
      .map((key) => caches.delete(key))
  )).then(() => self.clients.claim()));
});

// Admin requires a connection. Always revalidate its HTML, CSS and JavaScript;
// leave API calls and authenticated responses outside the static cache.
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || request.headers.has('Authorization') ||
      url.origin !== self.location.origin || /\/api\//.test(url.pathname)) return;
  if (request.mode === 'navigate' || /\.(html|css|js)$/.test(url.pathname)) {
    event.respondWith(fetch(request, { cache: 'no-store' }).then((response) => {
      const headers = new Headers(response.headers);
      headers.set('Cache-Control', 'no-store');
      return new Response(response.body, {
        status: response.status, statusText: response.statusText, headers
      });
    }));
  }
});
