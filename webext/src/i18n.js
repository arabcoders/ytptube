(function (root) {
    const api = root.chrome || root.browser;
    const messages = api && api.i18n;

    const t = (key, substitutions) => {
        if (!messages || typeof messages.getMessage !== 'function') {
            console.warn(`i18n unavailable for ${key}`);
            return `[Missing translation: ${key}]`;
        }
        const normalized = Array.isArray(substitutions)
            ? substitutions.map(String)
            : substitutions === undefined ? undefined : String(substitutions);
        const value = normalized === undefined
            ? messages.getMessage(key)
            : messages.getMessage(key, normalized);
        if (!value) {
            console.warn(`Missing translation: ${key}`);
            return `[Missing translation: ${key}]`;
        }
        return value;
    };

    const translateDom = (rootNode = document) => {
        rootNode.querySelectorAll('[data-i18n]').forEach(element => {
            element.textContent = t(element.dataset.i18n);
        });
        rootNode.querySelectorAll('[data-i18n-title]').forEach(element => {
            element.title = t(element.dataset.i18nTitle);
        });
        rootNode.querySelectorAll('[data-i18n-placeholder]').forEach(element => {
            element.placeholder = t(element.dataset.i18nPlaceholder);
        });
        rootNode.querySelectorAll('[data-i18n-aria-label]').forEach(element => {
            element.setAttribute('aria-label', t(element.dataset.i18nAriaLabel));
        });
    };

    const initializeDocumentLocale = () => {
        if (typeof document === 'undefined') return;
        const language = messages && messages.getUILanguage ? messages.getUILanguage() : 'en';
        document.documentElement.lang = language;
        document.documentElement.dir = t('@@bidi_dir') === 'rtl' ? 'rtl' : 'ltr';
        translateDom();
    };

    root.t = t;
    root.translateDom = translateDom;
    root.initializeDocumentLocale = initializeDocumentLocale;
    if (typeof document !== 'undefined') {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initializeDocumentLocale, { once: true });
        } else {
            initializeDocumentLocale();
        }
    }
})(typeof globalThis !== 'undefined' ? globalThis : window);
