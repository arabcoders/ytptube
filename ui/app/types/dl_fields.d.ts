type DLFieldType = "string" | "text" | "bool";

type DLField = {
  /** The id of the field */
  id?: string;

  /** The name of the preset */
  name: string;

  /** The description of the preset */
  description: string;

  /** The yt-dlp field to use in long format */
  field: string;

  /** The kind of the field. i.e. string, bool */
  kind: DLFieldType;

  /** The icon of the field, it can be a font-awesome icon */
  icon?: string;

  /** The order of the field, used to sort the fields in the UI. */
  order: number = 1;

  /** The default value of the field, It's currently unused */
  value: string;

  /** Additional options for the field */
  extras: Record<string, any>;
}

/**
 * Request payload for creating/updating DLField
 */
type DLFieldRequest = {
  name: string;
  description: string;
  field: string;
  kind: DLFieldType;
  value?: string;
  extras?: Record<string, any>;
}

export type { DLField, DLFieldRequest, DLFieldType };
