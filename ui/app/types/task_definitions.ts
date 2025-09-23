// --- Task Definition Schema Types ---

export type TaskMatchPattern = | string | { regex?: string; glob?: string }

export type EngineType = 'httpx' | 'selenium'

export interface EngineOptions {
  url?: string
  browser?: 'chrome'
  arguments?: Array<string> | string
  wait_for?: WaitForSelector
  wait_timeout?: number
  page_load_timeout?: number
  [key: string]: unknown
}

export interface EngineConfig {
  type?: EngineType
  options?: EngineOptions
}

export type HttpMethod = 'GET' | 'POST'

export type StringMap = Record<string, string | number | boolean | null>

export interface RequestConfig {
  method?: HttpMethod
  url?: string
  headers?: StringMap
  params?: StringMap
  data?: StringMap | string | null
  json?: object | Array<unknown> | string | number | boolean | null
  timeout?: number
}

export type ResponseType = 'html' | 'json'

export interface ResponseConfig {
  type?: ResponseType
}

export type ExtractionType = 'css' | 'xpath' | 'regex' | 'jsonpath'

export interface PostFilter {
  filter: string
  value?: string
}

export interface ExtractionRule {
  type: ExtractionType
  expression: string
  attribute?: string
  post_filter?: PostFilter
}

export interface ContainerFields {
  link: ExtractionRule
  [field: string]: ExtractionRule
}

export type ContainerSelectorType = 'css' | 'xpath' | 'jsonpath'

export interface Container {
  type?: ContainerSelectorType
  selector?: string
  expression?: string
  fields: ContainerFields
}

export interface WaitForSelector {
  type?: 'css' | 'xpath'
  expression?: string
  value?: string
}

export interface ParseConfig {
  items?: Container
  link?: ExtractionRule
  [field: string]: ExtractionRule | Container | undefined
}

export interface TaskDefinitionDocument {
  name: string
  match: Array<TaskMatchPattern>
  parse: ParseConfig
  priority?: number
  engine?: EngineConfig
  request?: RequestConfig
  response?: ResponseConfig
}

// --- Summaries and Error Types ---

export type TaskDefinitionSummary = {
  id: string,
  name: string,
  priority: number,
  updated_at: number,
}

export type TaskDefinitionDetailed = TaskDefinitionSummary & {
  definition: TaskDefinitionDocument
}

export type TaskDefinitionErrorResponse = {
  error: string,
}


