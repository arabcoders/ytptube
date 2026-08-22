// --- Task Definition Schema Types ---
import type { Paginated } from '~/types/responses';

export type EngineType = 'http' | 'browser';

export interface HttpEngineOptions {
  impersonate?: string;
  curl_default_headers?: boolean;
  flaresolverr?: boolean;
}

export type ImpersonateTargetsResponse = { targets: string[] };

export interface CdpBrowserOptions {
  protocol?: 'cdp';
  url: string;
  wait_for?: WaitForSelector | null;
  wait_timeout?: number;
  page_load_timeout?: number;
}

export type EngineOptions = HttpEngineOptions | CdpBrowserOptions;

export type EngineConfig =
  | { type?: 'http'; options?: HttpEngineOptions }
  | { type: 'browser'; options: CdpBrowserOptions };

export type HttpMethod = 'GET' | 'POST';

export type StringMap = Record<string, string | number | boolean | null>;

export type RequestBody =
  | { type: 'form'; value: StringMap }
  | { type: 'json'; value: unknown }
  | { type: 'raw'; value: string };

export interface RequestConfig {
  method?: HttpMethod;
  url?: string | null;
  headers?: Record<string, string>;
  params?: StringMap;
  body?: RequestBody | null;
  timeout?: number | null;
}

export type ResponseType = 'html' | 'json';

export interface ResponseConfig {
  type?: ResponseType;
}

export type ExtractionType = 'css' | 'xpath' | 'regex' | 'jsonpath';

export interface PostFilter {
  filter: string;
  value?: string | null;
}

export interface ExtractionRule {
  type: ExtractionType;
  expression: string;
  attribute?: string | null;
  post_filter?: PostFilter | null;
}

export interface ContainerFields {
  url: ExtractionRule;
  title?: ExtractionRule;
  thumbnail?: ExtractionRule;
  description?: ExtractionRule;
  published?: ExtractionRule;
  [field: string]: ExtractionRule | undefined;
}

export type ContainerSelectorType = 'css' | 'xpath' | 'jsonpath';

export interface Container {
  type?: ContainerSelectorType;
  selector: string;
  fields: ContainerFields;
}

export interface WaitForSelector {
  type?: 'css' | 'xpath';
  expression: string;
}

export interface ParseConfig {
  items?: Container | null;
  url?: ExtractionRule;
  title?: ExtractionRule;
  thumbnail?: ExtractionRule;
  description?: ExtractionRule;
  published?: ExtractionRule;
  [field: string]: ExtractionRule | Container | null | undefined;
}

export interface TaskDefinitionConfig {
  parse: ParseConfig;
  engine?: EngineConfig;
  request?: RequestConfig;
  response?: ResponseConfig;
}

export interface TaskDefinitionDocument {
  name: string;
  match_url: string[];
  priority?: number;
  enabled?: boolean;
  definition: TaskDefinitionConfig;
}

export type TaskDefinitionSummary = {
  id: number;
  name: string;
  priority: number;
  match_url: ReadonlyArray<string>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type TaskDefinitionDetailed = TaskDefinitionSummary & {
  definition: TaskDefinitionConfig;
};

export type TaskDefinitionList = Paginated<TaskDefinitionSummary>;

export type TaskDefinitionErrorResponse = {
  error: string;
};
