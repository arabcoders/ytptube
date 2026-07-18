import { requirePageShell, type PageShell } from '~/utils/topLevelNavigation';

export const usePageShell = (id: string): PageShell => {
  const { locale, t } = useI18n();
  const raw = requirePageShell(id);

  return {
    icon: raw.icon,
    get sectionLabel() {
      void locale.value;
      return t(raw.sectionLabel);
    },
    get pageLabel() {
      void locale.value;
      return t(raw.pageLabel);
    },
    get description() {
      void locale.value;
      return t(raw.description);
    },
  };
};
