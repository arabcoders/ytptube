export type error_response = {
  /** The error message */
  error: string,
}

export type convert_args_response = {
  /** The converted CLI args */
  opts?: Record<string, any>,
  /** The output template if was provided */
  output_template?: string,
  /** The download path if was provided */
  download_path?: string,
  /** The download format if was provided */
  format?: string,
  /** The removed options from the original CLI args if any. */
  removed_options?: Array<string>,
}

export type Pagination = {
  page: number
  per_page: number
  total: number
  total_pages: number
  has_next: boolean
  has_prev: boolean
}

export type Paginated<T> = {
  items: Array<T>
  pagination: Pagination
}

export interface APIResponse<T = unknown> {
  success: boolean
  error: string | null
  detail: unknown
  data?: T
}
