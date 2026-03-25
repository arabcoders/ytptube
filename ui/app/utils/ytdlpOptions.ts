export const YTDLP_ALL_GROUPS = '__all_groups__';

type YTDLPGroupItem = {
  label: string;
  value: string;
};

export const buildYtdlpGroupItems = (groups: string[]): YTDLPGroupItem[] => {
  return [
    { label: 'All groups', value: YTDLP_ALL_GROUPS },
    ...groups.map((group) => ({ label: group, value: group })),
  ];
};

export const normalizeYtdlpGroupFilter = (value: string): string => {
  return value === YTDLP_ALL_GROUPS ? '' : value;
};
