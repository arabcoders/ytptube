import { useStorage } from '@vueuse/core'

const toast = useToast()
const AG_SEPARATOR = '.'

/**
 * Get value from object or function
 *
 * @param {Function|*} obj
 * @returns {*}
 */
const getValue = (obj) => 'function' === typeof obj ? obj() : obj

/**
 * Get value from object or function and return default value if it's undefined  or null
 *
 * @param {Object|Array} obj The object to get the value from.
 * @param {string} path The path to the value.
 * @param {*} defaultValue The default value to return if the path is not found.
 *
 * @returns {*} The value at the path or the default value.
 */
const ag = (obj, path, defaultValue = null) => {
  const keys = path.split(AG_SEPARATOR)
  let at = obj

  for (let key of keys) {
    if (typeof at === 'object' && null !== at && key in at) {
      at = at[key]
    } else {
      return getValue(defaultValue)
    }
  }

  return getValue(null === at ? defaultValue : at)
}

/**
 * Set value in object by path
 *
 * @param {Object} obj The object to set the value in.
 * @param {string} path The path to the value.
 * @param {*} value The value to set.
 *
 * @returns {Object} The object with the value set.
 */
const ag_set = (obj, path, value) => {
  const keys = path.split(AG_SEPARATOR)
  let at = obj

  while (keys.length > 0) {
    if (keys.length === 1) {
      if (typeof at === 'object' && at !== null) {
        at[keys.shift()] = value
      } else {
        throw new Error(`Cannot set value at this path (${path}) because it's not an object.`)
      }
    } else {
      const key = keys.shift()
      if (!at[key]) {
        at[key] = {}
      }
      at = at[key]
    }
  }

  return obj
}

/**
 * Wait for an element to be loaded in the DOM
 *
 * @param {string} sel The selector of the element.
 * @param {Function} callback The callback function.
 *
 * @returns {void}
 */
const awaitElement = (sel, callback) => {
  let interval = undefined
  let $elm = document.querySelector(sel)

  if ($elm) {
    callback($elm, sel)
    return
  }

  interval = setInterval(() => {
    let $elm = document.querySelector(sel)
    if ($elm) {
      clearInterval(interval)
      callback($elm, sel)
    }
  }, 200)
}

/**
 * Replace tags in text with values from context
 *
 * @param {string} text The text with tags
 * @param {object} context The context with values
 *
 * @returns {string} The text with replaced tags
 */
const r = (text, context = {}) => {
  const tagLeft = '{'
  const tagRight = '}'

  if (!text.includes(tagLeft) || !text.includes(tagRight)) {
    return text
  }

  const pattern = new RegExp(`${tagLeft}([\\w_.]+)${tagRight}`, 'g')
  const matches = text.match(pattern)

  if (!matches) {
    return text
  }

  let replacements = {}

  matches.forEach(match => replacements[match] = ag(context, match.slice(1, -1), ''))

  for (let key in replacements) {
    text = text.replace(new RegExp(key, 'g'), replacements[key])
  }

  return text
}

const copyText = (str, notify = true) => {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(str).then(() => {
      if (notify) {
        toast.success('Text copied to clipboard.')
      }
    }).catch((error) => {
      console.error('Failed to copy.', error)
      if (notify) {
        toast.error('Failed to copy to clipboard.')
      }
    })
    return
  }

  const el = document.createElement('textarea')
  el.value = str
  document.body.appendChild(el)
  el.select()
  document.execCommand('copy')
  document.body.removeChild(el)

  if (notify) {
    toast.success('Text copied to clipboard.')
  }
}

/**
 * Dispatch custom event.
 *
 * @param {string} eventName The name of the event.
 * @param {object} detail The detail object.
 *
 * @returns {Boolean} The return value of dispatchEvent.
 */
const dEvent = (eventName, detail = {}) => window.dispatchEvent(new CustomEvent(eventName, { detail }))

/**
 * Make pagination
 *
 * @param {number} current The current page.
 * @param {number} last The last page.
 * @param {number} delta The delta.
 *
 * @returns {Array} The pagination array.
 */
const makePagination = (current, last, delta = 5) => {
  let pagination = []

  if (last < 2) {
    return pagination
  }

  const strR = '-'.repeat(9 + `${last}`.length)

  const left = current - delta, right = current + delta + 1

  for (let i = 1; i <= last; i++) {
    if (i === 1 || i === last || (i >= left && i < right)) {
      if (i === left && i > 2) {
        pagination.push({
          page: 0, text: strR, selected: false,
        })
      }

      pagination.push({
        page: i, text: `Page #${i}`, selected: i === current
      })

      if (i === right - 1 && i < last - 1) {
        pagination.push({
          page: 0, text: strR, selected: false,
        })
      }
    }
  }

  return pagination
}

/**
 * Encodes a path string to be used in a URL
 *
 * @param {string} item - The path string to encode
 *
 * @returns {string} - The encoded path string
 */
const encodePath = item => {
  // -- manually encode #
  if (!item) {
    return item
  }

  item = item.replace(/#/g, '%23')
  return item.split('/').map(decodeURIComponent).map(encodeURIComponent).join('/')
}

/**
 * Request content from the API. This function will automatically add the API token to the request headers.
 * And prefix the URL with the API URL and path.
 *
 * @param {string} url - The URL to request
 * @param {RequestInit} options - The request options
 *
 * @returns {Promise<Response>} - The response from the API
 */
const request = (url, options = {}) => {
  const runtimeConfig = useRuntimeConfig()
  const token = useStorage('token', null)
  options = options || {}
  options.method = options.method || 'GET'
  options.headers = options.headers || {}

  if (token && undefined === options.headers['Authorization']) {
    options.headers['Authorization'] = 'Token ' + token.value
  }

  if (undefined === options.headers['Content-Type']) {
    if (!(options?.body instanceof FormData)) {
      options.headers['Content-Type'] = 'application/json'
    }
  }

  if (undefined === options.headers['Accept']) {
    options.headers['Accept'] = 'application/json'
  }

  if (url.startsWith('/')) {
    options.credentials = 'same-origin'
  }

  return fetch(url.startsWith('/') ? eTrim(runtimeConfig.public.domain, '/') + '/' + sTrim(url, '/') : url, options)
}

/**
 * Remove the ANSI colors from the text
 *
 * @param {string} text - The text to remove the colors from
 *
 * @returns {string} - The text without the colors.
 */
const removeANSIColors = text => text?.replace(/[\u001b\u009b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nqry=><]/g, '') ?? text

const dec2hex = dec => dec.toString(16).padStart(2, "0")
const makeId = len => Array.from(window.crypto.getRandomValues(new Uint8Array((len || 40) / 2)), dec2hex).join('')

const basename = (path, ext = '') => {
  if (!path) {
    return ''
  }
  const segments = path.replace(/\\/g, '/').split('/')
  let base = segments.pop()
  while (segments.length && base === '') {
    base = segments.pop()
  }
  if (ext && base.endsWith(ext) && base !== ext) {
    base = base.substring(0, base.length - ext.length)
  }
  return base
}

const dirname = filePath => {
  const lastIndex = Math.max(filePath.lastIndexOf('/'), filePath.lastIndexOf('\\'))
  if (-1 === lastIndex) {
    return '.'
  }
  if (0 === lastIndex) {
    return filePath[0]
  }
  return filePath.substring(0, lastIndex)
}

const iTrim = (str, delim, position = 'both') => {
  if (!str) {
    return str
  }

  if (!delim) {
    throw new Error('Delimiter is required')
  }

  if ("]" === delim) {
    delim = "\\]"
  }
  if ("\\" === delim) {
    delim = "\\\\"
  }

  if (['both', 'start'].includes(position)) {
    str = str.replace(new RegExp("^[" + delim + "]+", "g"), "")
  }

  if (['both', 'end'].includes(position)) {
    str = str.replace(new RegExp("[" + delim + "]+$", "g"), "")
  }

  return str
}

const eTrim = (str, delim) => iTrim(str, delim, 'end')
const sTrim = (str, delim) => iTrim(str, delim, 'start')

const ucFirst = str => (!str) ? str : str.charAt(0).toUpperCase() + str.slice(1)

/**
 * Get query parameters from the URL
 *
 * @param {string} url - The URL to get the query parameters from
 *
 * @returns {Object} - The query parameters
 */
const getQueryParams = (url = window.location.search) => Object.fromEntries(new URLSearchParams(url).entries())

/**
 * Make download URL.
 *
 * @param {Object} config
 * @param {Object} item
 * @param {string} base
 *
 * @returns {string} The download URL
 */
const makeDownload = (config, item, base = 'api/download') => {
  let baseDir = 'api/player/m3u8/video/';
  if ('m3u8' !== base) {
    baseDir = `${base}/`;
  }

  if (item.folder) {
    item.folder = item.folder.replace(/#/g, '%23');
    baseDir += item.folder + '/';
  }

  let url = `/${sTrim(baseDir, '/')}${encodePath(item.filename)}`;
  return ('m3u8' === base) ? url + '.m3u8' : url;
}

/**
 * Format a file size
 *
 * @param {number} bytes
 * @param {number} decimals
 *
 * @returns {string} The formatted file size
 */
const formatBytes = (bytes, decimals = 2) => {
  if (!+bytes) return '0 Bytes'

  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ['Bytes', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB']

  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`
}


/**
 * Convert options to JSON
 *
 * @param {string} opts
 *
 * @returns {Promise<string>}
 */
const convertCliOptions = async opts => {
  const response = await request('/api/yt-dlp/convert', {
    method: 'POST',
    body: JSON.stringify({ args: opts }),
  });

  const data = await response.json()
  if (200 !== response.status) {
    throw new Error(`Error: (${response.status}): ${data.error}`)
  }

  return data
}

export {
  ag_set,
  ag,
  awaitElement,
  copyText,
  dEvent,
  makePagination,
  request,
  r,
  encodePath,
  removeANSIColors,
  makeId,
  basename,
  iTrim,
  eTrim,
  sTrim,
  ucFirst,
  dirname,
  getQueryParams,
  makeDownload,
  formatBytes,
  convertCliOptions,
}
