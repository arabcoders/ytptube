export const YTDLP_ALL_GROUPS = '__all_groups__';

type YTDLPGroupItem = {
  label: string;
  value: string;
};

export const buildYtdlpGroupItems = (groups: string[]): YTDLPGroupItem[] => {
  const { $i18n } = useNuxtApp();
  const t = $i18n?.t ?? ((key: string) => key);

  return [
    { label: t('common.allGroups'), value: YTDLP_ALL_GROUPS },
    ...groups.map((group) => ({ label: group, value: group })),
  ];
};

export const normalizeYtdlpGroupFilter = (value: string): string => {
  return value === YTDLP_ALL_GROUPS ? '' : value;
};
