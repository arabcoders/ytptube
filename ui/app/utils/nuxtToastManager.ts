type ToastPayload = {
  id?: string | number;
  [key: string]: unknown;
};

type ToastInstance = {
  id: string | number;
};

type ToastManager = {
  add: (toast: ToastPayload) => ToastInstance;
  remove: (id: string | number) => void;
};

let manager: ToastManager | null = null;

export const setNuxtToastManager = (toastManager: ToastManager): void => {
  manager = toastManager;
};

export const getNuxtToastManager = (): ToastManager | null => manager;
