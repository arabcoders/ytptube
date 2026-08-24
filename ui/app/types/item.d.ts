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
