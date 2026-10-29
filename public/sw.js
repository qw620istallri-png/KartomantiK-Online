// Service worker of the installed app (PWA). The page always comes from the
// network when it can, so a new release shows up on the next load; the
// versioned files (?v=) never change and are kept; the cache is only a
// fallback for a flaky connection. A new release changes VERSION, which makes
// the browser install this worker again: the page then offers a reload
// (never forced, and never in the middle of a game).
const VERSION = "20261029-rules-beta-141-4";
const CACHE = `kko-${VERSION}`;
const SHELL = ["./", "manifest.webmanifest", "icons/icon-192.png", "icons/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).catch(() => {}));
  // the very first install has nothing to replace: take over at once
  if (!self.registration.active) self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter((name) => name.startsWith("kko-") && name !== CACHE).map((name) => caches.delete(name)));
    await self.clients.claim();
  })());
});

self.addEventListener("message", (event) => {
  if (event.data?.type === "skip-waiting") self.skipWaiting();
});

async function networkFirst(request, fallbackUrl) {
  const cache = await caches.open(CACHE);
  try {
    // straight from the server: no HTTP cache on the way may hand back an old page
    const response = await fetch(request, { cache: "no-store" });
    if (response.ok) cache.put(fallbackUrl || request, response.clone());
    return response;
  } catch (error) {
    const cached = await cache.match(fallbackUrl || request);
    if (cached) return cached;
    throw error;
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(CACHE);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) cache.put(request, response.clone());
  return response;
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  // card art and other hosts stay with the browser's own cache; the version check
  // (sw.js) always goes straight to the server
  if (url.origin !== self.location.origin || url.pathname.endsWith("/sw.js")) return;
  if (request.mode === "navigate") {
    event.respondWith(networkFirst(request, "./"));
  } else if (url.searchParams.has("v")) {
    event.respondWith(cacheFirst(request));
  } else {
    event.respondWith(networkFirst(request));
  }
});
