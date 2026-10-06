// Service Worker for PWA
const CACHE_NAME = 'kiroku-journal-v4';
const urlsToCache = [
  '/static/manifest.json'
];

// インストール時にキャッシュを作成
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        return cache.addAll(urlsToCache);
      })
  );
  self.skipWaiting();
});

// ページ本体は更新を即反映するためネットワーク優先にする
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // 更新系リクエストと API は絶対に Cache Storage から返さない。
  // 日記保存後に古い /api/pages/... が表示されるのを防ぐ。
  if (request.method !== 'GET' ||
      (url.origin === self.location.origin && url.pathname.startsWith('/api/'))) {
    event.respondWith(fetch(request));
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() => caches.match(request))
    );
    return;
  }

  event.respondWith(
    caches.match(request)
      .then((response) => {
        return response || fetch(request);
      })
  );
});

// 古いキャッシュを削除
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});
