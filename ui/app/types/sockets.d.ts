export type Event = {
  id: string
  created_at: string
  event: string
  title: string | null
  message: string | null
  data: Record<string, unknown>
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
