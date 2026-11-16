import { describe, expect, it } from 'bun:test';
import type { changelogs } from '~/types/changelogs';
import {
  filterChangelog,
  getOpenReleases,
  isInstalledRelease,
  matchesSha,
} from '~/utils/changelog';

const logs: changelogs = [
  {
    tag: 'v2.0.0',
    full_sha: 'abcdef123456',
    date: '2026-11-16',
    commits: [
      {
        sha: 'abcdef1',
        full_sha: 'abcdef123456',
        message: 'Fix playback\n\nKeep progress after seeking.',
        author: 'Alice',
        date: '2026-11-16',
      },
      {
        sha: '1234567',
        full_sha: '123456789abc',
        message: 'Update guides',
        author: 'Bob',
        date: '2026-11-15',
      },
    ],
  },
  {
    tag: 'v1.0.0',
    full_sha: 'fedcba987654',
    date: '2026-11-01',
    commits: [],
  },
];

describe('changelog search', () => {
  it('keeps release commits', () => {
    expect(filterChangelog(logs, ' V2.0.0 ')).toEqual([logs[0]!]);
    expect(filterChangelog(logs, '  ')).toBe(logs);
  });

  it('filters matching commits', () => {
    for (const query of ['playback', 'progress', ' ALICE ', 'ABCDEF']) {
      const result = filterChangelog(logs, query);

      expect(result).toHaveLength(1);
      expect(result[0]!.commits).toEqual([logs[0]!.commits[0]!]);
    }
    expect(logs[0]!.commits).toHaveLength(2);
    expect(filterChangelog(logs, 'missing')).toEqual([]);
  });
});

describe('installed changelog', () => {
  it('collapses older releases', () => {
    const history = [
      logs[0]!,
      logs[1]!,
      { tag: 'v0.9.0', full_sha: '987654321abc', date: '2026-10-01', commits: [] },
    ];

    expect(getOpenReleases(history, 'fedcba9')).toEqual(['v2.0.0', 'v1.0.0']);
    expect(getOpenReleases(history, 'abcdef1')).toEqual(['v2.0.0']);
    expect(getOpenReleases(history, '1234567')).toEqual(['v2.0.0']);
  });

  it('opens newest fallback', () => {
    for (const installed of ['', 'unknown', 'missing']) {
      expect(getOpenReleases(logs, installed)).toEqual(['v2.0.0']);
    }
    expect(getOpenReleases([], 'abcdef1')).toEqual([]);
  });

  it('uses full history', () => {
    const history = Array.from({ length: 12 }, (_, index) => ({
      tag: `v${12 - index}.0.0`,
      full_sha: index.toString(16).padStart(40, '0'),
      date: '2026-11-16',
      commits: [],
    }));

    expect(getOpenReleases(history, history[10]!.full_sha)).toEqual(
      history.slice(0, 11).map((log) => log.tag),
    );
  });

  it('matches abbreviated hashes', () => {
    expect(matchesSha('ABCDEF123456', ' abcdef1 ')).toBe(true);
    expect(matchesSha('abcdef1', 'abcdef123456')).toBe(true);
    expect(matchesSha('abcdef123456', '1234567')).toBe(false);
    expect(matchesSha('abcdef123456', '')).toBe(false);
    expect(matchesSha('abcdef123456', 'unknown')).toBe(false);
    expect(matchesSha('', 'abcdef1')).toBe(false);
  });

  it('finds installed release', () => {
    expect(isInstalledRelease(logs[0]!, 'abcdef1')).toBe(true);
    expect(isInstalledRelease(logs[0]!, '1234567')).toBe(true);
    expect(isInstalledRelease(logs[1]!, 'fedcba9')).toBe(true);
    expect(isInstalledRelease(logs[1]!, '')).toBe(false);
    expect(isInstalledRelease(logs[0]!, 'fedcba9')).toBe(false);
  });
});
