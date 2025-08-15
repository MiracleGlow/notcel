self.addEventListener("install", e => {
  e.waitUntil(
    caches.open("nocel-cache").then(cache => {
      return cache.addAll(["/", "/static/styles.css"]);
    })
  );
});

self.addEventListener("fetch", e => {
  e.respondWith(
    caches.match(e.request).then(response => response || fetch(e.request))
  );
});
