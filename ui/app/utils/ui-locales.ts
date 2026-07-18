import { ar, en, fr, ja, zh_cn } from '@nuxt/ui/locale';

const uiLocales = { en, ar, fr, ja, zh: zh_cn } as const;
type UiCode = keyof typeof uiLocales;

export function getUiLocale(code: string): (typeof uiLocales)[UiCode] | typeof en {
  return uiLocales[code as UiCode] ?? en;
}
