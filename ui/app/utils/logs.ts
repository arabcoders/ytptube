const formatPathValue = (value: unknown): string => {
  if (typeof value === 'string') {
    return value;
  }

  if (typeof value === 'number' || typeof value === 'boolean' || null === value) {
    return String(value);
  }

  return JSON.stringify(value);
};

const flattenJsonPaths = (value: unknown, prefix = ''): Array<string> => {
  if (Array.isArray(value)) {
    if (0 === value.length) {
      return prefix ? [`${prefix}: []`] : [];
    }

    return value.flatMap((item, index) =>
      flattenJsonPaths(item, prefix ? `${prefix}.${index}` : String(index)),
    );
  }

  if (value && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>);
    if (0 === entries.length) {
      return prefix ? [`${prefix}: {}`] : [];
    }

    return entries.flatMap(([key, item]) =>
      flattenJsonPaths(item, prefix ? `${prefix}.${key}` : key),
    );
  }

  return prefix ? [`${prefix}: ${formatPathValue(value)}`] : [];
};

export const filterLogTextLines = (value: string, filter: string): Array<string> => {
  const query = filter.trim();
  if (!query) {
    return value.split('\n');
  }

  const needle = query.toLowerCase();

  if (query.includes('.')) {
    try {
      const flattened = flattenJsonPaths(JSON.parse(value) as unknown);
      const matches = flattened.filter((line) => line.toLowerCase().includes(needle));
      if (matches.length > 0) {
        return matches;
      }
    } catch {
      // Fall back to plain line filtering for non-JSON content.
    }
  }

  return value.split('\n').filter((line) => line.toLowerCase().includes(needle));
};
