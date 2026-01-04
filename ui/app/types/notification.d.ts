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
  id?: string;
  name: string;
  request: notificationRequest;
  on: Array<string>;
  presets: Array<string>;
  enabled: boolean;
};

type notificationImport = notification & {
  _type: 'notification';
  _version: string;
};

export type { notificationRequestHeaderItem, notification, notificationRequest, notificationImport };
