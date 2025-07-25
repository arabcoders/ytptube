type task_item = {
  id: string,
  name: string,
  url: string,
  preset?: string,
  folder?: string,
  template?: string,
  cli?: string,
  timer?: string,
  in_progress?: boolean,
  auto_start?: boolean,
  enabled_handler?: boolean,
}

type exported_task = task_item & { _type: string, _version: string }

type error_response = { error: string }

export type { task_item, exported_task, error_response };
