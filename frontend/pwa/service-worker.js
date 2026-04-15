// PremiumPOS Service Worker
const CACHE_NAME = 'premiumpos-v1.0.0';
const OFFLINE_CACHE = 'premiumpos-offline-v1';

// Cache qilinadigan fayllar
const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/shared/login.html',
    '/shared/offline.html',
    '/app/pos.html',
    '/app/kitchen.html',
    '/app/admin.html',
    '/styles/main.css',
    '/styles/pages/pos.css',
    '/styles/pages/kitchen.css',
    '/styles/pages/admin.css',
    '/js/core/api.js',
    '/js/core/auth.js',
    '/js/core/socket.js',
    '/js/core/state.js',
    '/js/modules/pos.js',
    '/js/modules/kitchen.js',
    '/js/modules/admin.js',
    '/js/ui/toast.js',
    '/js/ui/modal.js',
    '/js/utils/formatter.js',
    '/js/utils/helpers.js',
    '/assets/icons/logo.svg',
    '/assets/icons/icon-192x192.png',
    '/assets/icons/icon-512x512.png'
];

// Service Worker o'rnatish
self.addEventListener('install', (event) => {
    console.log('[SW] Installing...');
    
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('[SW] Caching static assets');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => {
                return self.skipWaiting();
            })
    );
});

// Service Worker faollashtirish
self.addEventListener('activate', (event) => {
    console.log('[SW] Activating...');
    
    event.waitUntil(
        caches.keys()
            .then((cacheNames) => {
                return Promise.all(
                    cacheNames.map((cacheName) => {
                        if (cacheName !== CACHE_NAME && cacheName !== OFFLINE_CACHE) {
                            console.log('[SW] Deleting old cache:', cacheName);
                            return caches.delete(cacheName);
                        }
                    })
                );
            })
            .then(() => {
                return self.clients.claim();
            })
    );
});

// Fetch so'rovlarini ushlash
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    
    // API so'rovlarini cache qilmaslik
    if (url.pathname.startsWith('/api/')) {
        return networkFirst(event);
    }
    
    // WebSocket so'rovlarini o'tkazib yuborish
    if (url.pathname.startsWith('/ws')) {
        return;
    }
    
    // Statik fayllar uchun cache first
    if (STATIC_ASSETS.some(asset => url.pathname.endsWith(asset))) {
        return cacheFirst(event);
    }
    
    // Boshqa so'rovlar uchun network first
    return networkFirst(event);
});

// Cache first strategiyasi
function cacheFirst(event) {
    event.respondWith(
        caches.match(event.request)
            .then((cachedResponse) => {
                if (cachedResponse) {
                    return cachedResponse;
                }
                
                return fetch(event.request)
                    .then((response) => {
                        if (!response || response.status !== 200) {
                            return response;
                        }
                        
                        const responseToCache = response.clone();
                        caches.open(CACHE_NAME)
                            .then((cache) => {
                                cache.put(event.request, responseToCache);
                            });
                        
                        return response;
                    })
                    .catch(() => {
                        // Offline fallback
                        if (event.request.mode === 'navigate') {
                            return caches.match('/shared/offline.html');
                        }
                        return null;
                    });
            })
    );
}

// Network first strategiyasi
function networkFirst(event) {
    event.respondWith(
        fetch(event.request)
            .then((response) => {
                if (!response || response.status !== 200) {
                    return response;
                }
                
                const responseToCache = response.clone();
                caches.open(CACHE_NAME)
                    .then((cache) => {
                        cache.put(event.request, responseToCache);
                    });
                
                return response;
            })
            .catch(() => {
                return caches.match(event.request)
                    .then((cachedResponse) => {
                        if (cachedResponse) {
                            return cachedResponse;
                        }
                        
                        if (event.request.mode === 'navigate') {
                            return caches.match('/shared/offline.html');
                        }
                        
                        return new Response(JSON.stringify({ 
                            error: 'Offline', 
                            message: 'Internet aloqasi yo\'q' 
                        }), {
                            status: 503,
                            headers: { 'Content-Type': 'application/json' }
                        });
                    });
            })
    );
}

// Offline ma'lumotlarni saqlash
self.addEventListener('sync', (event) => {
    if (event.tag === 'sync-orders') {
        event.waitUntil(syncOfflineOrders());
    } else if (event.tag === 'sync-payments') {
        event.waitUntil(syncOfflinePayments());
    }
});

// Offline buyurtmalarni sinxronizatsiya qilish
async function syncOfflineOrders() {
    console.log('[SW] Syncing offline orders...');
    
    const cache = await caches.open(OFFLINE_CACHE);
    const requests = await cache.keys();
    
    for (const request of requests) {
        try {
            const response = await fetch(request);
            if (response.ok) {
                await cache.delete(request);
            }
        } catch (error) {
            console.error('[SW] Failed to sync order:', error);
        }
    }
}

// Offline to'lovlarni sinxronizatsiya qilish
async function syncOfflinePayments() {
    console.log('[SW] Syncing offline payments...');
    // To'lov sinxronizatsiyasi logikasi
}

// Push notification
self.addEventListener('push', (event) => {
    const data = event.data?.json() || {};
    
    const options = {
        body: data.body || 'Yangi bildirishnoma',
        icon: '/assets/icons/icon-192x192.png',
        badge: '/assets/icons/badge-72x72.png',
        vibrate: [200, 100, 200],
        data: data.data || {},
        actions: data.actions || [],
        tag: data.tag || 'default',
        renotify: true
    };
    
    event.waitUntil(
        self.registration.showNotification(
            data.title || 'PremiumPOS',
            options
        )
    );
});

// Notification bosilganda
self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    
    const url = event.notification.data?.url || '/';
    
    event.waitUntil(
        clients.matchAll({ type: 'window' })
            .then((clientList) => {
                for (const client of clientList) {
                    if (client.url.includes(url) && 'focus' in client) {
                        return client.focus();
                    }
                }
                if (clients.openWindow) {
                    return clients.openWindow(url);
                }
            })
    );
});