export type PlayerRequestGuard = {
  ready: () => void;
  stop: () => void;
};

export function guardPlayerRequests(
  mediaUrl: string,
  scriptUrl: string,
  onFallback: () => void,
  signal: AbortSignal,
): Promise<PlayerRequestGuard | null> {
  if (!window.isSecureContext || !navigator.serviceWorker || signal.aborted) {
    return Promise.resolve(null);
  }

  const container = navigator.serviceWorker;
  const script = new URL(scriptUrl, window.location.href);
  const media = new URL(mediaUrl, window.location.href);
  return new Promise((resolve) => {
    const channel = new MessageChannel();
    let worker: ServiceWorker | null = null;
    let settled = false;
    let closed = false;
    let notified = false;
    const notify = () => {
      if (notified || closed) return;
      notified = true;
      onFallback();
    };
    const close = (type: 'ready' | 'stop') => {
      if (closed) return;
      closed = true;
      window.clearTimeout(timer);
      container.removeEventListener('controllerchange', control);
      signal.removeEventListener('abort', abort);
      channel.port1.postMessage({ type });
      channel.port1.close();
      channel.port2.close();
    };
    const abort = () => {
      close('stop');
      if (!settled) {
        settled = true;
        resolve(null);
      }
    };
    const control = () => {
      if (closed) return;
      if (worker && worker !== container.controller) {
        if (settled) notify();
        abort();
        return;
      }
      if (worker || container.controller?.scriptURL !== script.href) return;
      worker = container.controller;
      try {
        worker.postMessage({ type: 'player-startup', url: media.href }, [channel.port2]);
      } catch {
        abort();
      }
    };
    const timer = window.setTimeout(abort, 3000);
    channel.port1.onmessage = (event: MessageEvent) => {
      if (closed) return;
      if (event.data?.type === 'armed' && !settled) {
        settled = true;
        window.clearTimeout(timer);
        resolve({ ready: () => close('ready'), stop: () => close('stop') });
      } else if (event.data?.type === 'fallback' && settled) {
        notify();
      }
    };
    container.addEventListener('controllerchange', control);
    signal.addEventListener('abort', abort, { once: true });
    void container
      .register(script.href, { scope: new URL('.', script).pathname, updateViaCache: 'none' })
      .then(control, () => {
        if (!worker) abort();
      });
    control();
  });
}
