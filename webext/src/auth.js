// Shared authentication parsing and storage migration helpers.
(function (root) {
    const browserApi = root.chrome || root.browser;
    const encodeBase64Utf8 = value => {
        const bytes = new TextEncoder().encode(value);
        let binary = '';
        bytes.forEach(byte => binary += String.fromCharCode(byte));
        return btoa(binary);
    };

    const parse = value => {
        if (!value) {
            return { value: '', header: null };
        }
        if (value.startsWith('ytp_')) {
            return { value, header: `Bearer ${value}` };
        }

        const separator = value.indexOf(':');
        if (separator > 0) {
            return { value, header: `Basic ${encodeBase64Utf8(value)}` };
        }
        throw new Error((root.t || (key => key))('auth_parse_error'));
    };

    const getAuth = async () => {
        const stored = await browserApi.storage.sync.get(['auth', 'username', 'password']);
        if (stored.auth) {
            return stored.auth;
        }
        if (stored.username && stored.password) {
            return `${stored.username}:${stored.password}`;
        }
        return '';
    };

    root.YTPAuth = { parse, getAuth };
})(typeof globalThis !== 'undefined' ? globalThis : window);
