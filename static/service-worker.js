const CACHE_NAME = 'stability-v1';
const ASSETS_TO_CACHE = [
  '/',
  '/calculator',
  '/static/css/style.css',
  'https://cdn.jsdelivr.net/npm/chart.js'
];

// Install: Cache the basic UI shell
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
});

// Fetch: Serve from cache if offline
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});