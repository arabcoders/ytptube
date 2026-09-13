(function (root) {
    const browserApi = root.chrome || root.browser;
    let backgroundUrl = null;
    let loading = null;
    let requestedVisible = false;

    const resize = async blob => {
        if (typeof createImageBitmap !== 'function') {
            return blob;
        }

        try {
            const image = await createImageBitmap(blob);
            const maxDimension = 800;
            const scale = Math.min(1, maxDimension / Math.max(image.width, image.height));
            const canvas = document.createElement('canvas');
            canvas.width = Math.max(1, Math.round(image.width * scale));
            canvas.height = Math.max(1, Math.round(image.height * scale));
            const context = canvas.getContext('2d');
            if (!context) {
                image.close();
                return blob;
            }

            context.drawImage(image, 0, 0, canvas.width, canvas.height);
            image.close();
            return await new Promise(resolve => {
                canvas.toBlob(converted => resolve(converted || blob), 'image/jpeg', .78);
            });
        } catch (_) {
            return blob;
        }
    };

    const load = async () => {
        if (backgroundUrl) {
            return true;
        }
        if (loading) {
            return await loading;
        }

        loading = (async () => {
            const stored = await browserApi.storage.sync.get('instance_url');
            if (!stored.instance_url) {
                return false;
            }

            let auth;
            try {
                auth = YTPAuth.parse(await YTPAuth.getAuth());
            } catch (error) {
                console.error(error);
                return false;
            }

            let url;
            try {
                url = new URL(stored.instance_url);
            } catch (_) {
                return false;
            }
            url.pathname = '/api/random/background/';
            const headers = auth.header ? { Authorization: auth.header } : {};

            try {
                const response = await fetch(url, { headers });
                if (!response.ok) {
                    return false;
                }

                const image = await resize(await response.blob());
                backgroundUrl = URL.createObjectURL(image);
                document.documentElement.style.setProperty('--ytp-bg-image', `url(${backgroundUrl})`);
                return true;
            } catch (error) {
                console.error('Error fetching YTPTube background:', error);
                return false;
            }
        })();

        try {
            return await loading;
        } finally {
            loading = null;
        }
    };

    const setOpacity = opacity => {
        const value = Math.min(1, Math.max(0, Number(opacity)));
        document.body.style.opacity = String(Number.isFinite(value) ? value : .95);
    };

    const show = async (opacity = .95) => {
        requestedVisible = true;
        if (!await load()) {
            return false;
        }
        if (!requestedVisible) {
            return false;
        }

        document.documentElement.classList.add('ytp-bg-fanart');
        document.body.classList.add('ytp-with-background');
        setOpacity(opacity);
        return true;
    };

    const hide = () => {
        requestedVisible = false;
        document.documentElement.classList.remove('ytp-bg-fanart');
        document.body.classList.remove('ytp-with-background');
        document.body.style.removeProperty('opacity');
    };

    const init = async () => {
        const stored = await browserApi.storage.sync.get(['showBackground', 'backgroundOpacity']);
        if (stored.showBackground ?? true) {
            return await show(stored.backgroundOpacity ?? .95);
        }
        return false;
    };

    const destroy = () => {
        if (backgroundUrl) {
            URL.revokeObjectURL(backgroundUrl);
            backgroundUrl = null;
        }
    };

    addEventListener('pagehide', destroy, { once: true });
    root.YTPBackground = { init, show, hide, setOpacity };
})(typeof globalThis !== 'undefined' ? globalThis : window);
