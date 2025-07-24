export type Event = {
  id: str
  created_at: str
  event: str
  title: str | null = null
  message: str | null = null
  data: Any = { }
}
