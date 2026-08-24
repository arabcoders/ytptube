type ItemStatus =
  | 'started'
  | 'finished'
  | 'preparing'
  | 'error'
  | 'cancelled'
  | 'downloading'
  | 'postprocessing'
  | 'not_live'
  | 'skip'
  | null;

type SideCar = {
  file: string;
};

type sideCarSubtitle = SideCar & {
  lang: string;
  name: string;
};

type MediaProfile = {
  video?: {
    width?: number;
    height?: number;
    fps?: number;
    codec?: string;
  };
  audio?: {
    bitrate?: number | string;
    codec?: string;
    channels?: number;
    sample_rate?: string;
  };
};

type StoreItem = {
  _id: string;
  error: string | null;
  id: string;
  title: string;
  description: string;
  url: string;
  preset: string;
  folder: string;
  download_dir: string;
  temp_dir: string;
  status: ItemStatus;
  cookies: string;
  template: string;
  template_chapter: string;
  timestamp: number;
  is_live: boolean;
  datetime: string;
  live_in: string | null;
  file_size: number | null;
  cli: string;
  auto_start: boolean;
  force_start: boolean;
  queue_position: number | null;
  options: Record<string, unknown>;
  sidecar: {
    Unknown?: Array<SideCar>;
    subtitle?: Array<sideCarSubtitle>;
    image?: Array<SideCar>;
  };
  download_skipped?: boolean;
  extras: {
    channel?: string;
    duration?: number | null;
    release_in?: string;
    thumbnail?: string;
    uploader?: string;
    media_profile?: MediaProfile;
    is_audio?: boolean;
    is_video?: boolean;
    live_in?: string;
    is_premiere?: boolean;
    retry_attempt?: number;
  };
  tmpfilename?: string | null;
  filename?: string | null;
  total_bytes?: number | null;
  total_bytes_estimate?: number | null;
  downloaded_bytes?: number | null;
  msg?: string | null;
  percent?: number | null;
  speed?: number | null;
  eta?: number | null;
  is_archivable?: boolean;
  is_archived?: boolean;
  archive_id?: string | null;
  postprocessor?: string | null;
};

export type { ItemStatus, MediaProfile, StoreItem };
