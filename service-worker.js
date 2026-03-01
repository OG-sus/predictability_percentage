// A simple, no-op service worker that exists only to make the site installable.
// This can be expanded later to add offline caching capabilities.

self.addEventListener('install', (event) => {
  // Perform install steps
});

self.addEventListener('fetch', (event) => {
  // This service worker doesn't intercept any requests.
  // It just exists to satisfy the PWA installability criteria.
});
