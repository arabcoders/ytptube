export type ApiErrorPayload = {
  error?: string;
  message?: string;
  code?: string;
  params?: Record<string, string | number | boolean | null>;
  detail?:
    | string
    | Array<{
        loc?: Array<string | number>;
        msg?: string;
        type?: string;
        code?: string;
      }>;
  technical_message?: string;
};

export type convert_args_response = {
  opts?: Record<string, any>;
  output_template?: string;
  download_path?: string;
  format?: string;
  removed_options?: Array<string>;
};

export type Pagination = {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
};

export type Paginated<T> = {
  items: Array<T>;
  pagination: Pagination;
};

export interface APIResponse<T = unknown> {
  success: boolean;
  error: string | null;
  detail: unknown;
  data?: T;
}
