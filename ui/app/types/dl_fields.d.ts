type DLFieldType = 'string' | 'text' | 'bool';

type DLField = {
  id?: number;

  name: string;

  description: string;

  field: string;

  kind: DLFieldType;

  /** Lucide/Iconify name, such as `i-lucide-image`. */
  icon?: string;

  /** Sort position in the download form. */
  order: number;

  /** Reserved for a future default value. */
  value: string;

  extras: Record<string, any>;
};

type DLFieldRequest = {
  name: string;
  description: string;
  field: string;
  kind: DLFieldType;
  value?: string;
  extras?: Record<string, any>;
};

export type { DLField, DLFieldRequest, DLFieldType };
