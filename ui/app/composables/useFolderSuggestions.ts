import { encodePath, request } from '~/utils';

const CACHE_TTL = 30_000;

const cache = new Map<string, { folders: string[]; expires: number }>();

const fetchFolders = async (parentPath: string): Promise<string[]> => {
  const key = parentPath;
  const cached = cache.get(key);
  if (cached && cached.expires > Date.now()) {
    return cached.folders;
  }

  try {
    const resp = await request(`/api/system/folders?path=${encodePath(parentPath)}`, {
      timeout: 5,
    });
    if (!resp.ok) {
      return [];
    }
    const data = await resp.json();
    const folders: string[] = data.folders ?? [];
    cache.set(key, { folders, expires: Date.now() + CACHE_TTL });
    return folders;
  } catch {
    return [];
  }
};

export const useFolderSuggestions = () => ({ fetchFolders });
