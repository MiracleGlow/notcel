self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  clients.claim();
});

// Runtime cache untuk semua file di /static/
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Jika file dari folder /static
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.open("static-cache").then(async (cache) => {
        const cached = await cache.match(event.request);
        if (cached) {
          return cached;
        }

        // Fetch dan simpan ke cache otomatis
        const response = await fetch(event.request);
        cache.put(event.request, response.clone());
        return response;
      })
    );
  }
});
