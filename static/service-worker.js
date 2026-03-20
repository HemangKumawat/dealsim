// DealSim Service Worker
// Strategy: cache-first for app shell, network-first for API calls

const CACHE_VERSION = 'dealsim-v1';
const API_PATTERN = /\/api\//;

const APP_SHELL = [
  '/',
  '/index.html',
  '/themes.css',
  '/achievements.js',
  '/celebrations.js',
  '/daily-challenge-card.js',
  '/engine-peek.js',
  '/gamification.js',
  '/learning-path.js',
  '/quick-match.js',
  '/radar-chart.js',
  '/scenario-cards.js',
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

// Fetch: network-first for API, cache-first for everything else
self.addEventListener('fetch', (event) => {
  // Only handle GET requests
  if (event.request.method !== 'GET') return;

  if (API_PATTERN.test(event.request.url)) {
    // Network-first for API calls — fall back to cache if offline
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
    // Cache-first for app shell assets
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
