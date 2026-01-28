import type { StoreItem } from "./store"

export type Event = {
  id: string
  created_at: string
  event: string
  title: string | null
  message: string | null
  data: Record<string, unknown>
}

export type EventPayload<T> = Event & { data: T }

export type WebSocketEnvelope<T = unknown> = {
  event: string
  data: T
}

export type WSEP = {
  connect: null
  disconnect: null
  connect_error: { message?: string }
  connected: EventPayload<{ sid: string }>
  item_added: EventPayload<StoreItem>
  item_updated: EventPayload<StoreItem>
  item_cancelled: EventPayload<StoreItem>
  item_deleted: EventPayload<StoreItem>
  item_moved: EventPayload<{ to: 'queue' | 'history'; item: StoreItem }>
  item_status: EventPayload<{ status?: string; msg?: string; preset?: string }>
  paused: EventPayload<{ paused?: boolean }>
  resumed: EventPayload<{ paused?: boolean }>
  log_info: EventPayload<Record<string, unknown>>
  log_success: EventPayload<Record<string, unknown>>
  log_warning: EventPayload<Record<string, unknown>>
  log_error: EventPayload<Record<string, unknown>>
  config_update: EventPayload<ConfigUpdatePayload>
}

export type WebSocketClientEmits = {
  add_url: Record<string, unknown>
  item_cancel: string
  item_delete: { id: string; remove_file?: boolean }
  item_start: string | string[]
  item_pause: string | string[]
}

type ConfigUpdateAction = 'create' | 'update' | 'delete' | 'replace'

type ConfigFeature = 'presets' | 'dl_fields' | 'conditions'

type ConfigUpdatePayload<T = unknown> = {
  feature: ConfigFeature
  action: ConfigUpdateAction
  data: T | Array<T>
  meta?: Record<string, unknown>
}

export type { ConfigUpdateAction, ConfigFeature, ConfigUpdatePayload }
