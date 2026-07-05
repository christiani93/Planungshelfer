// Service-Worker fuer Planungshelfer.
// Cached die App-Shell (CSS/JS/Icon) cache-first, Daten (HTML/API) network-first
// mit Cache-Fallback. Achtung: Aufgaben sind nicht offline editierbar —
// der Server muss laufen. Der Cache dient nur der Installierbarkeit als PWA
// und schnellem Start.

const CACHE_NAME = "planungshelfer-v1";
const APP_SHELL = [
  "/static/style.css",
  "/static/app.js",
  "/static/icon.svg",
  "/static/manifest.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Nur GET behandeln — POST/DELETE (Aufgaben anlegen/abhaken) nie cachen.
  if (event.request.method !== "GET") return;

  // Statisches: cache-first.
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(event.request).then((hit) => hit || fetch(event.request))
    );
    return;
  }

  // Dynamisches (HTML/API-State): network-first, Fallback auf Cache.
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
