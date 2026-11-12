const CACHE_NAME = 'tagcheck-admin-20261112-equipment-feedback';
const APP_SHELL = [
  "./manutencao/",
  "./maintenance.js?v=20261104-complete",
  "./maintenance.css?v=20261104-upload",
  "./locale.js?v=20261112-equipment-status",
  "./theme.js?v=20261102-i18n",
  "./config.js?v=20260915-asset-categories",
  "./company-admin.js?v=20261104-complete",
  "./billing-production.js?v=20261104-complete",
  "./superadmin.js?v=20261104-complete",
  "./offline-store.js?v=20261006-storage-fallback",
  "./calibration.js?v=20261104-complete",
  "./customer-access.js?v=20261104-complete",
  "./app.js?v=20261112-equipment-feedback",
  "./offline-integration.js?v=20261104-complete",
  './',
  './index.html',
  './admin-layout.css?v=20261103-header',
  './billing-production.js?v=20261104-complete',
  './config.js',
  './company-admin.js',
  './superadmin.js',
  './billing.js',
  './offline-store.js',
  './offline-integration.js',
  './app.js',
  './theme.js?v=20261017',
  './customer-access.js',
  './calibration.js',
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
