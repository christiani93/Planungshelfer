// Service-Worker fuer Planungshelfer.
// Cached die App-Shell (CSS/JS/Icon) cache-first, Daten (HTML/API) network-first
// mit Cache-Fallback. Achtung: Aufgaben sind nicht offline editierbar —
// der Server muss laufen. Der Cache dient nur der Installierbarkeit als PWA
// und schnellem Start.

const CACHE_NAME = "planungshelfer-v5";
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

// ---------------------------------------------------------------- Web-Push
self.addEventListener("push", (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) { data = {}; }
  const title = data.title || "Planungshelfer";
  const isConfirm = data.kind === "confirm";
  const options = {
    body: data.body || "",
    icon: "/static/icon.svg",
    badge: "/static/icon.svg",
    tag: data.tag || "planungshelfer",
    renotify: true,
    requireInteraction: isConfirm, // Bestaetigung soll stehen bleiben
    data: { reminder_id: data.reminder_id || null, kind: data.kind || "info" },
    actions: isConfirm
      ? [
          { action: "confirm", title: "Ja ✅" },
          { action: "dismiss", title: "Nein" },
        ]
      : [],
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  const notif = event.notification;
  const rid = notif.data && notif.data.reminder_id;
  notif.close();

  // Debug: exakten action-Wert an den Server melden (zum Diagnostizieren,
  // was ein Button-Tipp wirklich sendet).
  event.waitUntil(
    fetch("/api/push/click", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: event.action || "(body)", id: rid }),
    }).catch(() => {})
  );

  if (event.action === "dismiss") {
    if (rid) {
      event.waitUntil(
        fetch(`/api/reminders/${rid}/decline`, {
          method: "POST",
          credentials: "same-origin",
        }).catch(() => {})
      );
    }
    return;
  }

  if (event.action === "confirm" && rid) {
    // Folge-Erinnerung serverseitig anlegen (Session-Cookie wird mitgesendet).
    event.waitUntil(
      fetch(`/api/reminders/${rid}/confirm`, {
        method: "POST",
        credentials: "same-origin",
      }).catch(() => {})
    );
    return;
  }

  // Klick auf den Body: App oeffnen / fokussieren (dort erscheint das
  // Ja/Nein-Banner, falls eine Bestaetigung aussteht).
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        if ("focus" in client) return client.focus();
      }
      return self.clients.openWindow("/");
    })
  );
});
