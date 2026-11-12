// Offline support for X-ray Mirror.
// The page itself is fetched fresh whenever there is a connection, so updates arrive; everything else is served from the cache once saved.
// Bump the version when files under vendor/ change.
const CACHE = 'xray-mirror-v1';

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil((async () => {
  for (const k of await caches.keys()) if (k.startsWith('xray-mirror-') && k !== CACHE) await caches.delete(k);
  await self.clients.claim();
})()));

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url), same = url.origin === location.origin;
  const model = url.hostname === 'storage.googleapis.com' && url.pathname.startsWith('/mediapipe-models/');
  if (!same && !model) return;
  const page = same && (req.mode === 'navigate' || url.pathname.endsWith('/') || url.pathname.endsWith('/index.html'));
  e.respondWith(page ? networkFirst(req) : cacheFirst(req));
});

async function keep(req, res) {
  if (res && res.status === 200) { const c = await caches.open(CACHE); await c.put(req, res.clone()); }
  return res;
}
async function networkFirst(req) {
  try { return await keep(req, await fetch(req)); }
  catch (err) { const hit = await caches.match(req, { ignoreSearch: true }); if (hit) return hit; throw err; }
}
async function cacheFirst(req) {
  return await caches.match(req) || keep(req, await fetch(req));
}
