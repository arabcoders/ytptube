export type PlaylistDisplayEntry = {
  key: string;
  url: string;
  title: string;
  description: string;
  thumbnail: string;
  duration: number | null;
  viewCount: number | null;
  published: string | null;
  broadcastDateLabel: string;
  seriesTitle: string;
  broadcasterName: string;
  isArchived: boolean;
  archiveId?: string | null;
  extras: Record<string, unknown>;
};
