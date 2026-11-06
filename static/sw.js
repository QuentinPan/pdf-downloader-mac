// PDF 下载器 Service Worker
// 保守策略：API 请求永远走网络（不缓存），静态壳走缓存优先，导航走网络优先回退缓存。
const CACHE = 'pdfdl-v1';
const SHELL = [
  '/',
  '/static/manifest.webmanifest',
  '/static/icon-192.png',
  '/static/icon-512.png',
  '/static/apple-touch-icon.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE)
      .then((c) => c.addAll(SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  // 永远不要缓存 API
  if (url.pathname.startsWith('/api/')) return;
  // 导航请求：网络优先，失败回退到缓存主页
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).catch(() => caches.match('/'))
    );
    return;
  }
  // 其余静态资源：缓存优先，缺失再走网络并回填
  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req).then((res) => {
        if (res && res.ok && url.origin === self.location.origin) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      });
    })
  );
});
