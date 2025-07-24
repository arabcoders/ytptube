export type error_response = {
  /** The error message */
  error: string,
}

export type convert_args_response = {
  /** The converted CLI args */
  opts?: Record<string, any>,
  /** The output template if was provided */
  output_template?: string,
  /** The download path if was provided */
  download_path?: string,
  /** The download format if was provided */
  format?: string,
  /** The removed options from the original CLI args if any. */
  removed_options?: string[],
}

