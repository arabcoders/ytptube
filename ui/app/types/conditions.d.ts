export interface Condition {
  id?: number
  name: string
  filter: string
  cli: string
  extras: Record<string, unknown>
  enabled: boolean
  priority: number
  description: string
}

export interface Pagination {
  page: number
  per_page: number
  total: number
  total_pages: number
  has_next: boolean
  has_prev: boolean
}

export interface ConditionTestRequest {
  url: string
  condition: string
  preset?: string
}

export interface ConditionTestResponse {
  status: boolean
  condition: string
  data: Record<string, unknown>
}
