import { ar, en } from '@nuxt/ui/locale';

const uiLocales = { en, ar } as const;
type UiCode = keyof typeof uiLocales;

export function getUiLocale(code: string): (typeof uiLocales)[UiCode] | typeof en {
  return uiLocales[code as UiCode] ?? en;
}
