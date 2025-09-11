export type Event = {
  id: string
  created_at: string
  event: string
  title: string | null
  message: string | null
  data: Record<string, unknown>
}
