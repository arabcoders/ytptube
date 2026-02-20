import { JSDOM } from 'jsdom'

const dom = new JSDOM('<!doctype html><html><body></body></html>', {
  url: 'http://localhost',
})

const { window } = dom

globalThis.window = window as unknown as Window & typeof globalThis
globalThis.document = window.document
globalThis.navigator = window.navigator
globalThis.HTMLElement = window.HTMLElement
globalThis.Node = window.Node
globalThis.CustomEvent = window.CustomEvent
globalThis.getComputedStyle = window.getComputedStyle
globalThis.requestAnimationFrame = window.requestAnimationFrame
globalThis.cancelAnimationFrame = window.cancelAnimationFrame
globalThis.localStorage = window.localStorage
globalThis.sessionStorage = window.sessionStorage
globalThis.Storage = window.Storage

if (!globalThis.crypto) {
  globalThis.crypto = window.crypto
}

if (!globalThis.btoa) {
  globalThis.btoa = window.btoa
}

if (!globalThis.atob) {
  globalThis.atob = window.atob
}

if (!globalThis.fetch) {
  globalThis.fetch = window.fetch.bind(window)
}

if (!globalThis.Headers) {
  globalThis.Headers = window.Headers
}

if (!globalThis.Request) {
  globalThis.Request = window.Request
}

if (!globalThis.Response) {
  globalThis.Response = window.Response
}

if (!globalThis.Notification) {
  globalThis.Notification = window.Notification
}
