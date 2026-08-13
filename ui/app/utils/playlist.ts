type Info = Record<string, unknown>;

const isPlaylistKey = (key: string): boolean =>
  key === 'playlist' ||
  key === 'n_entries' ||
  key === '__last_playlist_index' ||
  key.startsWith('playlist_');

export const playlistExtras = (
  entry: Info,
  playlist: Info | null,
  index: number,
  total: number,
): Record<string, unknown> => {
  const extras: Record<string, unknown> = {};

  if (playlist) {
    const count = typeof playlist.playlist_count === 'number' ? playlist.playlist_count : total;
    Object.assign(extras, {
      playlist_count: count,
      playlist: playlist.title || playlist.id,
      playlist_id: playlist.id,
      playlist_title: playlist.title,
      playlist_uploader: playlist.uploader,
      playlist_uploader_id: playlist.uploader_id,
      playlist_channel: playlist.channel,
      playlist_channel_id: playlist.channel_id,
      playlist_webpage_url: playlist.webpage_url,
      __last_playlist_index: count - 1,
      n_entries: total,
      playlist_index: index + 1,
      playlist_index_number: index + 1,
      playlist_autonumber: index + 1,
    });
  }

  const metadata =
    entry.metadata && typeof entry.metadata === 'object' ? (entry.metadata as Info) : null;
  for (const source of [playlist, entry, metadata]) {
    if (!source) continue;
    for (const [key, value] of Object.entries(source)) {
      if (isPlaylistKey(key)) extras[key] = value;
    }
  }

  return extras;
};
