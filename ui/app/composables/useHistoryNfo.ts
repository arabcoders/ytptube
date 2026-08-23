import { ref } from 'vue';

import { parse_api_error, request } from '~/utils';
import type { StoreItem } from '~/types/store';

type NfoResult = {
  message?: string;
};

const requestNfo = async (item: StoreItem): Promise<NfoResult> => {
  const response = await request(`/api/history/${item._id}/nfo`, {
    method: 'POST',
    body: JSON.stringify({ type: 'tv', overwrite: true }),
  });
  const data = (await response.json()) as NfoResult;

  if (!response.ok) {
    const error = new Error(await parse_api_error(data));
    error.name = 'NfoResponseError';
    throw error;
  }

  return data;
};

export const useHistoryNfo = () => {
  const isGenerating = ref(false);

  const generateNfo = async (item: StoreItem): Promise<NfoResult> => requestNfo(item);

  const generateSelectedNfo = async (items: StoreItem[]): Promise<{ failed: boolean }> => {
    if (isGenerating.value) {
      return { failed: false };
    }

    isGenerating.value = true;
    let failed = false;

    try {
      for (const item of items) {
        if (!item.filename) {
          continue;
        }

        try {
          await requestNfo(item);
        } catch {
          failed = true;
        }
      }
    } finally {
      isGenerating.value = false;
    }

    return { failed };
  };

  return { isGenerating, generateNfo, generateSelectedNfo };
};
