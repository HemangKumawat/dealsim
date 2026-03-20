// DealSim Service Worker
// Strategy: network-first for HTML + API, cache-first for static assets

const CACHE_VERSION = 'dealsim-v3';
const API_PATTERN = /\/api\//;

// Pages that should always try network first (so deploys take effect immediately)
const NETWORK_FIRST_PATHS = ['/', '/index.html', '/privacy.html'];

const APP_SHELL = [
  '/',
  '/index.html',
  '/tailwind.out.css',
  '/themes.css',
  '/print.css',
  '/toasts.js',
  '/achievements.js',
  '/celebrations.js',
  '/daily-challenge-card.js',
  '/engine-peek.js',
  '/gamification.js',
  '/learning-path.js',
  '/onboarding.js',
  '/quick-match.js',
  '/radar-chart.js',
  '/scenario-cards.js',
  '/score-trends.js',
  '/session-export.js',
  '/stats-bar.js',
  '/theme-switcher.js',
  '/manifest.json',
];

// Install: cache the app shell
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

// Activate: clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_VERSION)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

// Fetch handler
self.addEventListener('fetch', (event) => {
  // Only handle GET requests
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);
  const isNetworkFirst = API_PATTERN.test(url.pathname) ||
    NETWORK_FIRST_PATHS.includes(url.pathname);

  if (isNetworkFirst) {
    // Network-first: try network, fall back to cache
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_VERSION).then((cache) => cache.put(event.request, clone));
          return response;
        })
        .catch(() => caches.match(event.request))
    );
  } else {
    // Cache-first for static assets (JS, CSS, images)
    event.respondWith(
      caches.match(event.request).then(
        (cached) => cached || fetch(event.request).then((response) => {
          const clone = response.clone();
          caches.open(CACHE_VERSION).then((cache) => cache.put(event.request, clone));
          return response;
        })
      )
    );
  }
});
