import type { LocationQuery } from 'vue-router';

export const SHARE_MARKER = 'share';
const SHARE_VALUES = ['title', 'text', 'url'] as const;

const trimPunctuation = (value: string): string =>
  value.replace(/[.,!?;:]+$/, '').replace(/[)\]}]+$/, '');

export const isShareTarget = (query: LocationQuery): boolean => query[SHARE_MARKER] === '1';

export const parseShareUrls = (query: LocationQuery): string[] => {
  if (!isShareTarget(query)) return [];

  const found: string[] = [];
  for (const key of SHARE_VALUES) {
    const values = Array.isArray(query[key]) ? query[key] : [query[key]];
    for (const value of values) {
      if (typeof value !== 'string') continue;
      for (const match of value.matchAll(/https?:\/\/[^\s<>"'`]+/gi)) {
        const url = trimPunctuation(match[0]);
        try {
          const parsed = new URL(url);
          if (
            (parsed.protocol === 'http:' || parsed.protocol === 'https:') &&
            parsed.hostname &&
            !found.includes(url)
          ) {
            found.push(url);
          }
        } catch {
          // Shared values may contain prose instead of URLs.
        }
      }
    }
  }
  return found;
};

export const removeShareQuery = (query: LocationQuery): LocationQuery => {
  const cleaned = { ...query };
  delete cleaned.share;
  delete cleaned.title;
  delete cleaned.text;
  delete cleaned.url;
  return cleaned;
};
