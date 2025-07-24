export type item_request = {
  /** Unique identifier for the item */
  id?: string|null,
  /** URL of the item to download */
  url: string,
  /** Preset to use for the download */
  preset?: string,
  /** Where to save the downloaded item */
  folder?: string,
  /** Output template for the downloaded item */
  template?: string,
  /** Additional command line options for yt-dlp */
  cli?: string,
  /** Cookies file for the download */
  cookies?: string,
  /** Auto start the download */
  auto_start?: boolean,
  /** Extras data for the item */
  extras?: Record<string, any>,
}
