import { describe, expect, it } from 'bun:test';
import { playlistExtras } from '~/utils/playlist';

describe('playlistExtras', () => {
  it('derives playlist context', () => {
    const playlist = {
      id: 'PL123',
      title: 'Playlist',
      uploader: 'Owner',
      webpage_url: 'https://example.com/playlist',
    };

    expect(playlistExtras({}, playlist, 2, 5)).toEqual({
      playlist_count: 5,
      playlist: 'Playlist',
      playlist_id: 'PL123',
      playlist_title: 'Playlist',
      playlist_uploader: 'Owner',
      playlist_uploader_id: undefined,
      playlist_channel: undefined,
      playlist_channel_id: undefined,
      playlist_webpage_url: 'https://example.com/playlist',
      __last_playlist_index: 4,
      n_entries: 5,
      playlist_index: 3,
      playlist_index_number: 3,
      playlist_autonumber: 3,
    });
  });

  it('keeps entry indexes', () => {
    const entry = {
      playlist_index: 8,
      metadata: { playlist_title: 'Entry playlist' },
    };

    const extras = playlistExtras(entry, { id: 'PL123', title: 'Playlist' }, 1, 10);

    expect(extras.playlist_index).toBe(8);
    expect(extras.playlist_index_number).toBe(2);
    expect(extras.playlist_title).toBe('Entry playlist');
  });
});
