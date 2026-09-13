if (typeof importScripts === 'function') {
    importScripts('i18n.js');
    importScripts('auth.js');
}

const str_keys = ["instance_url", "preset"]
const bool_keys = ["showContextMenu"]

if (typeof chrome === 'undefined') {
    let chrome = browser
}

const notify = message => chrome.notifications.create({
    "type": "basic",
    "iconUrl": chrome.runtime.getURL("icons/icon-128.png"),
    "title": t('extension_name'),
    "message": message,
});

const onMenuCreated = () => {
    if (chrome.runtime.lastError) {
        console.log(`error creating menu item. ${chrome.runtime.lastError}`);
    }
    syncContextMenu().then(_ => '').catch(console.error);
}

const shouldShowContextMenu = async () => {
    let item = await chrome.storage.sync.get("showContextMenu");
    return 'showContextMenu' in item ? item.showContextMenu : true;
};

const syncContextMenu = async () => {
    if (!chrome.contextMenus) {
        return;
    }

    let showContextMenu = await shouldShowContextMenu();
    const preset = (await getOption("preset")) || 'default';
    chrome.contextMenus.update("send-to-ytptube", {
        visible: showContextMenu,
        title: t('context_menu_preset', [preset])
    });
}

if (chrome.contextMenus) {
    chrome.contextMenus.create({
        id: "send-to-ytptube",
        title: t('context_menu_title'),
        contexts: ["link"]
    }, onMenuCreated);

    chrome.storage.onChanged.addListener((changes, areaName) => {
        if (areaName === 'sync' && (changes.showContextMenu || changes.preset)) {
            syncContextMenu().catch(console.error);
        }
    });
}

const getCurrentUrl = async () => (await chrome.tabs.query({ currentWindow: true, active: true }))[0].url

const getOption = async key => {
    let item = await chrome.storage.sync.get(key);
    if (str_keys.includes(key)) {
        return item[key] ?? '';
    }
    if (bool_keys.includes(key)) {
        return item[key] ?? false;
    }
}

const sendRequest = async (path, data) => {
    let instanceUrl = await getOption("instance_url");
    if (!instanceUrl) {
        throw new Error(t('instance_not_configured'));
    }

    if (instanceUrl.endsWith('/')) {
        instanceUrl = instanceUrl.slice(0, -1);
    }

    let headers = {};

    const auth = YTPAuth.parse(await YTPAuth.getAuth());
    if (auth.header) {
        headers['Authorization'] = auth.header;
    }

    const url = new URL(instanceUrl);
    url.pathname = path;

    const method = Object.keys(data).length > 0 ? 'POST' : 'GET';
    let opts = { method: method, headers: headers };

    if (data) {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(data);
    }

    console.debug(`Sending ${method} ${path} to '${instanceUrl}' (${auth.header ? 'with authentication' : 'without authentication'}).`);

    const req = await fetch(url, opts);
    return { status: req.status, statusText: req.statusText, data: req };
};

const sendUrl = async (user_url, preset = null) => {
    try {
        const requestData = { url: user_url };
        if (preset) {
            requestData.preset = preset;
        }

        console.debug('Sending request data:', requestData);

        const data = await sendRequest('/api/history', requestData);
        if ([200, 201, 202].includes(data.status)) {
            notify(t('request_success'));
            return { success: true, message: t('request_success') };
        }
        const errorMessage = t('request_failed_status', [data.status, data.statusText]);
        notify(errorMessage);
        return { success: false, message: errorMessage };
    } catch (e) {
        console.error(e);
        const errorMessage = t('request_failed_error', [e.message]);
        notify(errorMessage);
        return { success: false, message: errorMessage };
    }
};

if (chrome.contextMenus) {
    chrome.contextMenus.onClicked.addListener(async (info, _) => {
        if (info.menuItemId !== "send-to-ytptube") {
            return;
        }
        if (!info.linkUrl) {
            notify(t('no_link_url'));
            return;
        }

        // Reuse the popup selection; fall back to YTPTube's built-in default.
        const selectedPreset = (await getOption("preset")) || 'default';
        await sendUrl(info.linkUrl, selectedPreset);
    });
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.command !== "send-to-ytptube") {
        return;
    }

    (async () => {
        try {
            let url = message.url || await getCurrentUrl();

            if (!url) {
                await notify(t('no_url'));
                sendResponse({ success: false, message: t('no_url') });
                return;
            }

            const result = await sendUrl(url, message.preset);
            sendResponse(result);
        } catch (error) {
            console.error('Error in message handler:', error);
            sendResponse({ success: false, message: error.message });
        }
    })();

    return true;
});
