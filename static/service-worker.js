self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  clients.claim();
});

// CDN hosts to cache
const CDN_HOSTS = [
  'cdn.jsdelivr.net',
  'fonts.googleapis.com',
  'fonts.gstatic.com'
];

// Runtime cache untuk semua file di /static/ dan CDN
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Cache /static/ files (cache-first)
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.open("static-cache").then(async (cache) => {
        const cached = await cache.match(event.request);
        if (cached) return cached;
        const response = await fetch(event.request);
        cache.put(event.request, response.clone());
        return response;
      })
    );
    return;
  }

  // Cache CDN resources (stale-while-revalidate)
  if (CDN_HOSTS.includes(url.hostname)) {
    event.respondWith(
      caches.open("cdn-cache").then(async (cache) => {
        const cached = await cache.match(event.request);
        const fetchPromise = fetch(event.request).then((response) => {
          if (response.ok) cache.put(event.request, response.clone());
          return response;
        }).catch(() => cached);

        return cached || fetchPromise;
      })
    );
  }
});
