const guards = new Map();
const MAX_REQUESTS = 16;
const MAX_AGE = 60_000;

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('message', (event) => {
  const port = event.ports?.[0];
  const clientId = event.source?.id;
  if (
    event.data?.type !== 'player-startup' ||
    typeof event.data.url !== 'string' ||
    typeof clientId !== 'string' ||
    !clientId ||
    !port
  ) {
    return;
  }

  let url;
  try {
    url = new URL(event.data.url);
  } catch {
    return;
  }

  const base = new URL('api/player/media/', self.location.href);
  const parts = url.pathname.slice(base.pathname.length).split('/');
  if (
    url.origin !== base.origin ||
    !url.pathname.startsWith(base.pathname) ||
    parts.length !== 2 ||
    !parts[0] ||
    parts[1] !== 'file'
  ) {
    return;
  }

  const now = Date.now();
  for (const [key, guard] of guards) {
    if (now - guard.created >= MAX_AGE) {
      guard.port.close();
      guards.delete(key);
    }
  }

  const key = `${clientId}\n${url.href}`;
  guards.get(key)?.port.close();
  const guard = { port, created: now, count: 0, blocked: false };
  guards.set(key, guard);
  port.onmessage = (message) => {
    if (message.data?.type !== 'ready' && message.data?.type !== 'stop') {
      return;
    }

    // Stopping a failed startup keeps queued requests blocked; playable media releases the guard.
    if (guards.get(key) === guard && (message.data.type === 'ready' || !guard.blocked)) {
      guards.delete(key);
    }
    port.close();
  };
  port.postMessage({ type: 'armed' });
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') {
    return;
  }

  const guard = guards.get(`${event.clientId}\n${event.request.url}`);
  if (!guard) {
    return;
  }

  if (guard.count < MAX_REQUESTS) {
    guard.count += 1;
    event.respondWith(fetch(event.request));
    return;
  }

  event.respondWith(Response.error());
  if (!guard.blocked) {
    guard.blocked = true;
    guard.port.postMessage({ type: 'fallback' });
  }
});
