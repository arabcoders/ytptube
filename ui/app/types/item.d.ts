export type item_request = {
  id?: string | null;
  url: string;
  preset?: string;
  folder?: string;
  template?: string;
  cli?: string;
  cookies?: string;
  auto_start?: boolean;
  extras?: Record<string, any>;
};

export type picked_entry = {
  url: string;
  extras: Record<string, unknown>;
};

export type download_form_item = item_request & {
  picked_entries?: picked_entry[];
};
