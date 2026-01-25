type notificationRequestHeaderItem = {
  key: string;
  value: string;
};

type notificationRequest = {
  data_key: string;
  headers: notificationRequestHeaderItem[];
  method: string;
  type: string;
  url: string;
};

type notification = {
  id?: number;
  name: string;
  request: notificationRequest;
  on: Array<string>;
  presets: Array<string>;
  enabled: boolean;
};

type notificationPagination = {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
};

export type {
  notificationRequestHeaderItem,
  notification,
  notificationRequest,
  notificationPagination,
};
