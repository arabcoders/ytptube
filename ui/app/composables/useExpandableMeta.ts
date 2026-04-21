export const useExpandableMeta = () => {
  const expandedItems = ref<Record<string, Set<string>>>({});

  const normalizeId = (itemId: string | number | undefined | null): string | null => {
    if (itemId === undefined || itemId === null) {
      return null;
    }

    return String(itemId);
  };

  const toggleExpand = (itemId: string | number | undefined | null, field: string): void => {
    const key = normalizeId(itemId);
    if (!key) {
      return;
    }

    if (!expandedItems.value[key]) {
      expandedItems.value[key] = new Set();
    }

    if (expandedItems.value[key]?.has(field)) {
      expandedItems.value[key]?.delete(field);
      return;
    }

    expandedItems.value[key]?.add(field);
  };

  const isExpanded = (itemId: string | number | undefined | null, field: string): boolean => {
    const key = normalizeId(itemId);
    if (!key) {
      return false;
    }

    return expandedItems.value[key]?.has(field) ?? false;
  };

  const expandClass = (itemId: string | number | undefined | null, field: string): string => {
    return isExpanded(itemId, field)
      ? 'block max-w-full whitespace-pre-wrap break-words'
      : 'block max-w-full truncate';
  };

  return {
    toggleExpand,
    isExpanded,
    expandClass,
  };
};
