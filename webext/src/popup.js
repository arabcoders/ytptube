// noinspection JSUnresolvedReference

const $ = s => document.querySelector(s)

if (typeof chrome === 'undefined') {
    let chrome = browser;
}

const getOption = async (key, default_data) => {
    let item = await chrome.storage.sync.get(key);
    return Object.prototype.hasOwnProperty.call(item, key) ? item[key] : default_data;
}

const defaultPreset = { name: 'default', default: true, priority: 0 };
let presetItems = [];
let selectedPreset = 'default';
let onlyCustomPresets = false;

const notify = message => chrome.notifications.create({
    "type": "basic",
    "iconUrl": chrome.runtime.getURL("icons/icon-128.png"),
    "title": t('extension_name'),
    "message": message
});

const showLoading = (isLoading) => {
    const submitBtn = $('#submit-btn')

    if (isLoading) {
        submitBtn.disabled = true
        submitBtn.classList.add('is-loading')
    } else {
        submitBtn.disabled = false
        submitBtn.classList.remove('is-loading')
    }
}

const showStatusMessage = (message, isSuccess = true) => {
    const statusDiv = $('#status-message')
    statusDiv.textContent = message
    statusDiv.className = `ytp-status ${isSuccess ? 'is-success' : 'is-danger'}`
    statusDiv.classList.remove('is-hidden')

    // Hide the message after 3 seconds
    setTimeout(() => {
        statusDiv.classList.add('is-hidden')
    }, 3000)
}

$("#ytptube_popup").addEventListener("submit", async (e) => {
    e.preventDefault()
    const url = $('#user_url').value
    const preset = $('#preset').value || 'default'
    if (!url) {
        showStatusMessage(t('url_required'), false)
        return
    }

    showLoading(true)

    try {
        const response = await chrome.runtime.sendMessage({ command: 'send-to-ytptube', url: url, preset: preset })

        if (response && response.success) {
            showStatusMessage(t('request_success'), true)
        } else {
            showStatusMessage(response?.message || t('request_failed'), false)
        }
    } catch (error) {
        showStatusMessage(t('error_sending'), false)
        console.error('Error:', error)
    } finally {
        showLoading(false)
    }
})

const getCurrentUrl = async () => (await chrome.tabs.query({ currentWindow: true, active: true }))[0].url

addEventListener('DOMContentLoaded', async _ => {
    initializeDocumentLocale()
    await YTPTheme.init($('#theme-toggle'))
    await YTPBackground.init()
    let url = await getCurrentUrl()

    if (url && !url.startsWith('http')) {
        url = ""
    }

    $('#user_url').value = url || ''

    selectedPreset = await getOption("preset", 'default')
    onlyCustomPresets = await getOption("onlyCustomPresets", false)
    await loadPresetCache(false)
    renderPresets()
})

$('#go-to-options').addEventListener('click', function () {
    if (chrome.runtime.openOptionsPage) {
        chrome.runtime.openOptionsPage();
    } else {
        window.open(chrome.runtime.getURL('options.html'));
    }
});

$('#preset').addEventListener('change', async e => {
    selectedPreset = e.target.value
    await chrome.storage.sync.set({ preset: selectedPreset })
})

$('#toggle-presets').addEventListener('click', async () => {
    onlyCustomPresets = !onlyCustomPresets
    await chrome.storage.sync.set({ onlyCustomPresets })
    renderPresets()
})

$('#refresh-presets').addEventListener('click', async () => {
    const button = $('#refresh-presets')
    button.disabled = true
    try {
        await loadPresetCache(true)
        renderPresets()
        showStatusMessage(t('presets_refreshed'))
    } catch (error) {
        console.error(error)
        showStatusMessage(t('unable_refresh'), false)
    } finally {
        button.disabled = false
    }
})

const getPresets = async () => {
    const instanceUrl = await getOption("instance_url");
    if (!instanceUrl) {
        return []
    }

    let headers = {};

    let auth;
    try {
        auth = YTPAuth.parse(await YTPAuth.getAuth());
    } catch (error) {
        console.error(error)
        return null
    }
    if (auth.header) {
        headers['Authorization'] = auth.header;
    }

    const url = new URL(instanceUrl);
    url.pathname = '/api/presets/';
    url.search = 'per_page=100';

    try {
        const req = await fetch(url, { method: 'GET', headers: { ...headers, 'Accept': 'application/json' } });
        if (200 !== req.status) {
            console.error(`Error fetching presets from YTPTube: ${req.status}`)
            return null
        }

        const data = await req.json()
        const items = Array.isArray(data.items) ? data.items : data
        return Array.isArray(items) ? items.filter(p => p && p.name).map(p => ({
            name: p.name,
            default: p.default === true,
            priority: Number.isFinite(p.priority) ? p.priority : 0,
            description: p.description || ''
        })) : []
    } catch (error) {
        console.error('Error fetching presets from YTPTube:', error)
        return null
    }
};

const normalizePresets = items => {
    if (!Array.isArray(items)) {
        return []
    }

    // The old cache stored names only. Treat those entries as server presets.
    return items.filter(item => typeof item === 'string' || (item && item.name)).map(item =>
        typeof item === 'string' ? { name: item, default: item === 'default', priority: 0 } : item
    )
}

const loadPresetCache = async force => {
    const cache = await getOption('presets', { items: [], last_updated: 0 })
    if (force || Date.now() - cache.last_updated > 1000 * 60 * 60) {
        const freshPresets = await getPresets()
        if (freshPresets !== null) {
            cache.items = freshPresets
            cache.last_updated = Date.now()
        }
        await chrome.storage.sync.set({ presets: cache })
    }
    presetItems = normalizePresets(cache.items ?? cache.presets)
}

const renderPresets = async () => {
    const s = $('#preset')
    while (s.firstChild) {
        s.removeChild(s.lastChild)
    }

    const visibleItems = onlyCustomPresets ? presetItems.filter(p => !p.default) : [...presetItems]
    const customItems = visibleItems.filter(p => !p.default)
    const builtInItems = visibleItems.filter(p => p.default)

    appendPresetGroup(s, t('custom_presets'), customItems)
    appendPresetGroup(s, t('default_presets'), builtInItems)
    if (customItems.length === 0 && builtInItems.length === 0) {
        appendPreset(s, defaultPreset, selectedPreset)
    }

    const selected = [...s.options].find(option => option.value === selectedPreset)
    if (selected) {
        selected.selected = true
    } else {
        s.options[0].selected = true
        selectedPreset = s.options[0].value
        await chrome.storage.sync.set({ preset: selectedPreset })
    }

    const toggle = $('#toggle-presets')
    toggle.textContent = onlyCustomPresets ? t('show_all') : t('custom_only')
    toggle.classList.toggle('is-active', onlyCustomPresets)
}

const appendPreset = (select, preset, selectedPreset) => {
    const option = document.createElement('option')
    option.value = preset.name
    option.textContent = preset.name
    if (preset.description) {
        option.title = preset.description
    }
    option.selected = preset.name === selectedPreset
    select.appendChild(option)
}

const appendPresetGroup = (select, label, presets) => {
    if (presets.length === 0) {
        return
    }

    const group = document.createElement('optgroup')
    group.label = label
    presets
        .sort((a, b) => (b.priority || 0) - (a.priority || 0) || a.name.localeCompare(b.name))
        .forEach(preset => appendPreset(group, preset, null))
    select.appendChild(group)
}
