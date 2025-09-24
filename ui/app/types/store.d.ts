type ItemStatus = 'finished' | 'preparing' | 'error' | 'cancelled' | 'downloading' | 'postprocessing' | 'not_live' | 'skip' | null;

type SideCar = {
  file: string
}

type sideCarSubtitle = SideCar & {
  lang: string
  name: string
}

type StoreItem = {
  /** Unique identifier for the item */
  _id: string
  /** Error message if available */
  error: string | null
  /** Item source id */
  id: string
  /** Title of the item */
  title: string
  /** Description of the item */
  description: string
  /** URL of the item */
  url: string
  /** Preset used for the item */
  preset: string
  /** Folder where the item is saved */
  folder: string
  /** Download directory */
  download_dir: string
  /** Temporary directory for the item */
  temp_dir: string
  /** Status of the item */
  status: ItemStatus
  /** If the item has cookies */
  cookies: string
  /** If the item has custom output_template */
  template: string
  /** If the item has custom output_template for chapters */
  template_chapter: string
  /** When the item was created */
  timestamp: number
  /** If the item is a live stream */
  is_live: boolean
  /** ISO 8601 formatted start time of the item */
  datetime: string
  /** Live stream start time if available */
  live_in: string | null
  /** File size of the item if available */
  file_size: number | null
  /** Custom yt-dlp command line arguments */
  cli: string
  /** If the item is auto-started */
  auto_start: boolean
  /** Options for the item */
  options: Record<string, unknown>
  /** Sidecar associated with the item. */
  sidecar: {
    Unknown?: Array<SideCar>
    subtitle?: Array<sideCarSubtitle>
    image?: Array<SideCar>
  },
  /** Extras for the item */
  extras: {
    /** Which channel the item belongs to */
    channel?: string
    /** The video duration if available */
    duration?: number | null
    /** The video release date if available */
    release_in?: string
    /** The video thumbnail URL if available */
    thumbnail?: string
    /** The uploader of the item if available */
    uploader?: string
    /** Uploader name if available */
    is_audio?: boolean
    /** If the item has audio stream */
    is_video?: boolean
    /** If the item has video stream */
    live_in?: string
    /** Live stream start time if available */
    is_premiere?: boolean
    /** If the item is a premiere */
  }
  /** The item temporary filename */
  tmpfilename?: string | null
  /** The item filename */
  filename?: string | null
  /** Actual file size of the item if available */
  total_bytes?: number | null
  /** Estimated total bytes for the item if available */
  total_bytes_estimate?: number | null
  /** Downloaded bytes of the item if available */
  downloaded_bytes?: number | null
  /** Message attached with the item if available */
  msg?: string | null
  /** Progress percentage of the item if available */
  percent?: number | null
  /** Speed of the item download if available */
  speed?: number | null
  /** Time remaining for the item download if available */
  eta?: number | null
  /** If the item can be archived */
  is_archivable?: boolean
  /** If the item is archived */
  is_archived?: boolean
  /** Item archive ID */
  archive_id?: string | null
}

export type { ItemStatus, StoreItem }
