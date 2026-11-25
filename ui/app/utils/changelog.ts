import type { changelogs, changeset } from '~/types/changelogs';

export const filterChangelog = (logs: changelogs, query: string): changelogs => {
  const search = query.trim().toLowerCase();
  if (!search) {
    return logs;
  }

  return logs.flatMap((log) => {
    if (log.tag.toLowerCase().includes(search)) {
      return [log];
    }

    const commits = log.commits.filter(
      (commit) =>
        commit.message.toLowerCase().includes(search) ||
        commit.author.toLowerCase().includes(search) ||
        commit.full_sha.toLowerCase().includes(search),
    );
    return commits.length > 0 ? [{ ...log, commits }] : [];
  });
};

export const matchesSha = (value: string, installed: string): boolean => {
  const candidate = value.trim().toLowerCase();
  const current = installed.trim().toLowerCase();
  return (
    current !== '' &&
    current !== 'unknown' &&
    candidate !== '' &&
    (candidate.startsWith(current) || current.startsWith(candidate))
  );
};

export const isInstalledRelease = (log: changeset, installed: string): boolean =>
  log.tag !== 'Unreleased' && matchesSha(log.full_sha, installed);

export const getOpenReleases = (logs: changelogs, installed: string): string[] => {
  const index = logs.findIndex(
    (log) =>
      matchesSha(log.full_sha, installed) ||
      log.commits.some(
        (commit) => matchesSha(commit.full_sha, installed) || matchesSha(commit.sha, installed),
      ),
  );
  return logs.slice(0, Math.max(0, index) + 1).map((log) => log.tag);
};
