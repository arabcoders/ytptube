// noinspection JSUnresolvedReference

const str_keys = ["instance_url", "auth"]
let storedOriginPattern = null;

if (typeof chrome === 'undefined') {
    let chrome = browser
}

const notify = (message, no_inline) => {
    if (!no_inline) {
        document.querySelector('#error_msg').innerText = message;
    }

    chrome.notifications.create({
        "type": "basic",
        "iconUrl": chrome.runtime.getURL("icons/icon-128.png"),
        "title": t('extension_name'),
        "message": message,
    });
}

const buildOriginPattern = (instanceUrl) => {
    try {
        const url = new URL(instanceUrl);
        return `${url.protocol}//${url.host}/*`;
    } catch (error) {
        return null;
    }
};

const ensureOriginPermission = async (originPattern) => {
    if (!originPattern) {
        return false;
    }

    if (!chrome.permissions || !chrome.permissions.request) {
        return true;
    }

    return await chrome.permissions.request({ origins: [originPattern] });
};

const removeOriginPermission = async (originPattern) => {
    if (!originPattern) {
        return;
    }

    const hasPermission = await chrome.permissions.contains({ origins: [originPattern] });
    if (!hasPermission) {
        return;
    }

    await chrome.permissions.remove({ origins: [originPattern] });
};

const readJson = async response => {
    try {
        return await response.json();
    } catch (_) {
        return {};
    }
};

const testConfig = async (requestPermission = true) => {
    document.querySelector('#error_msg').innerText = "";

    let instance_url = document.querySelector("#instance_url").value.trim();
    if (!instance_url) {
        notify(t('valid_instance_url'));
        return false;
    }

    if (instance_url.endsWith('/')) {
        instance_url = instance_url.slice(0, -1);
    }

    document.querySelector("#instance_url").value = instance_url;

    const originPattern = buildOriginPattern(instance_url);
    if (!originPattern) {
        notify(t('valid_instance_url'));
        return false;
    }

    if (requestPermission) {
        const granted = await ensureOriginPermission(originPattern);
        if (!granted) {
            notify(t('permission_denied'));
            return false;
        }
    }

    const authValue = document.querySelector("#auth").value;
    let auth;
    try {
        auth = YTPAuth.parse(authValue);
    } catch (error) {
        notify(error.message);
        return false;
    }

    try {
        const headers = auth.header ? { Authorization: auth.header } : {};
        let req = await fetch(`${instance_url}/api/auth/status`, {
            method: 'GET',
            headers
        });

        // Older YTPTube versions predate the full authentication API.
        if (req.status === 404) {
            req = await fetch(`${instance_url}/api/ping`, {
                method: 'GET',
                headers
            });

            if (req.status === 200) {
                notify(t('connection_success'), true);
                return true;
            }
        }

        const json = await readJson(req);
        if (200 === req.status && (json.disabled === true || json.authenticated === true)) {
            notify(t('connection_success'), true);
            return true;
        }

        const errorCode = String(json.error || json.code || '');
        const message = (json.setup_required === true || errorCode === 'setup_required') ? t('setup_required') :
            (json.authenticated === false || req.status === 401 || /invalid|missing credential/i.test(errorCode) ? t('invalid_credentials') : (json.error ?? t('auth_check_failed')));
        notify(message);
    } catch (e) {
        notify(t('error_prefix', [e]));
    }
    return false;
}

document.addEventListener("DOMContentLoaded", () => {
    initializeDocumentLocale();
    YTPTheme.init(document.querySelector('#theme-toggle'));
    function onError(error) {
        console.log(`Error: ${error}`);
    }

    const markEdited = event => {
        event.currentTarget.dataset.userEdited = 'true';
    };
    const backgroundOpacity = document.querySelector('#backgroundOpacity');
    const backgroundOpacityValue = document.querySelector('#backgroundOpacityValue');
    const backgroundOpacityField = document.querySelector('#backgroundOpacityField');
    const showBackground = document.querySelector('#showBackground');
    const shellOpacity = () => 1 - Number(backgroundOpacity.value) / 100;
    const updateOpacityValue = () => {
        backgroundOpacityValue.value = `${backgroundOpacity.value}%`;
        if (document.body.classList.contains('ytp-with-background')) {
            YTPBackground.setOpacity(shellOpacity());
        }
    };
    const updateBackgroundPreview = async () => {
        backgroundOpacityField.hidden = !showBackground.checked;
        if (showBackground.checked) {
            await YTPBackground.show(shellOpacity());
        } else {
            YTPBackground.hide();
        }
    };
    backgroundOpacity.addEventListener('input', updateOpacityValue);
    showBackground.addEventListener('change', updateBackgroundPreview);
    updateOpacityValue();

    document.querySelectorAll('#instance_url, #auth, #showContextMenu, #showBackground, #backgroundOpacity')
        .forEach(input => input.addEventListener('input', markEdited));
    document.querySelectorAll('#showContextMenu, #showBackground')
        .forEach(input => input.addEventListener('change', markEdited));

    const setIfUntouched = (selector, value) => {
        const input = document.querySelector(selector);
        if (input.dataset.userEdited !== 'true') {
            input.value = value;
        }
    };

    chrome.storage.sync.get(str_keys).then(async r => {
        setIfUntouched("#instance_url", r.instance_url || "");
        setIfUntouched("#auth", await YTPAuth.getAuth());
    }, onError);

    chrome.storage.sync.get(["showContextMenu", "showBackground", "backgroundOpacity", "instance_origin"]).then(async r => {
        const showContextMenu = document.querySelector("#showContextMenu");
        showContextMenu.closest('.ytp-check').classList.toggle('is-hidden', !chrome.contextMenus);
        if (showContextMenu.dataset.userEdited !== 'true') {
            showContextMenu.checked = r.showContextMenu || false;
        }
        if (showBackground.dataset.userEdited !== 'true') {
            showBackground.checked = r.showBackground ?? true;
        }
        if (backgroundOpacity.dataset.userEdited !== 'true') {
            backgroundOpacity.value = Math.round((1 - (r.backgroundOpacity ?? .95)) * 100);
            updateOpacityValue();
        }
        storedOriginPattern = r.instance_origin || null;
        await updateBackgroundPreview();
    }, onError);
});

document.getElementById("ytptube_options").addEventListener("submit", async e => {
    e.preventDefault();

    document.querySelector('#error_msg').innerText = "";
    let instance_url = document.querySelector("#instance_url").value.trim();
    if (!instance_url) {
        notify(t('valid_instance_url'));
        return false;
    }

    if (instance_url.endsWith('/')) {
        instance_url = instance_url.slice(0, -1);
    }

    const newOriginPattern = buildOriginPattern(instance_url);
    if (!newOriginPattern) {
        notify(t('valid_instance_url'));
        return false;
    }

    if (!await ensureOriginPermission(newOriginPattern)) {
        notify(t('permission_denied'));
        return false;
    }

    const data = {
        instance_url,
        auth: document.querySelector("#auth").value,
        showContextMenu: document.querySelector("#showContextMenu").checked,
        showBackground: document.querySelector("#showBackground").checked,
        backgroundOpacity: 1 - Number(document.querySelector("#backgroundOpacity").value) / 100,
        instance_origin: newOriginPattern
    };

    try {
        const previous = await chrome.storage.sync.get(["instance_url", "auth"]);
        const previousAuth = await YTPAuth.getAuth();
        const sourceChanged = (previous.instance_url || '') !== instance_url || previousAuth !== data.auth;

        await chrome.storage.sync.set(data);
        if (sourceChanged) {
            await chrome.storage.sync.remove("presets");
        }
        if (data.auth) {
            await chrome.storage.sync.remove(["username", "password"]);
        }

        if (storedOriginPattern && storedOriginPattern !== newOriginPattern) {
            await removeOriginPermission(storedOriginPattern);
        }
        storedOriginPattern = newOriginPattern;
        if (chrome.contextMenus) {
            chrome.contextMenus.update("send-to-ytptube", { visible: data.showContextMenu });
        }

        if (!await testConfig(false)) {
            return;
        }

        notify(t('options_saved'), true);
    } catch (error) {
        notify(t('unable_save', [error.message]));
    }
});

document.getElementById("test_config").addEventListener("click", async e => {
    e.preventDefault();
    await testConfig();
});

document.getElementById("toggle_auth").addEventListener("click", e => {
    const input = document.getElementById("auth");
    const visible = input.type === "text";
    input.type = visible ? "password" : "text";
    e.currentTarget.textContent = visible ? t('show') : t('hide');
    e.currentTarget.setAttribute("aria-pressed", String(!visible));
    e.currentTarget.setAttribute("aria-label", t(visible ? 'show_auth' : 'hide_auth'));
});
