type log_source = {
  path?: string;
  file?: string;
  module?: string;
  function?: string;
  line?: number;
};

type log_process = {
  id?: number | string;
  name?: string;
};

type log_thread = {
  id?: number | string;
  name?: string;
};

type log_line = {
  id: string;
  message: string;
  datetime: string;
  level: string;
  levelno?: number;
  logger: string;
  source?: log_source;
  process?: log_process;
  thread?: log_thread;
  fields?: Record<string, unknown>;
  exception?: string | null;
  exception_message?: string | null;
  stack?: string | null;
};

export type { log_line, log_process, log_source, log_thread };
