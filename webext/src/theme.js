(function (root) {
    const browserApi = root.chrome || root.browser;

    const apply = theme => {
        if (theme === 'dark' || theme === 'light') {
            document.documentElement.dataset.theme = theme;
        } else {
            delete document.documentElement.dataset.theme;
        }
    };

    const effectiveTheme = () => window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';

    const init = async button => {
        const stored = await browserApi.storage.sync.get('theme');
        let theme = stored.theme === 'dark' || stored.theme === 'light' ? stored.theme : 'system';
        apply(theme);
        updateButton(button, theme);

        button.addEventListener('click', async () => {
            const next = theme === 'system' ? 'light' : theme === 'light' ? 'dark' : 'system';
            theme = next;
            apply(next);
            await browserApi.storage.sync.set({ theme: next });
            updateButton(button, next);
        });
    };

    const updateButton = (button, theme) => {
        const label = (root.t || (key => key))(`theme_${theme}`);
        button.textContent = (root.t || (key => key))('theme_button', [label]);
        button.title = (root.t || (key => key))('theme_title', [label]);
    };

    root.YTPTheme = { init };
})(typeof globalThis !== 'undefined' ? globalThis : window);
