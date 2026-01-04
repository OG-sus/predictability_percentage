// This is a basic service worker.
// It enables the "Add to Home Screen" functionality and provides a basic offline experience.

const CACHE_NAME = 'predictability-score-cache-v1';
const URLS_TO_CACHE = [
  '/calculator',
  // We would add paths to our CSS and JS files here if they were separate.
  // For now, caching the main calculator page is enough.
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Opened cache');
        return cache.addAll(URLS_TO_CACHE);
      })
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Cache hit - return response
        if (response) {
          return response;
        }
        // Not in cache - fetch from network
        return fetch(event.request);
      }
    )
  );
});
