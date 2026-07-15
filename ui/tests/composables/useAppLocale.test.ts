import { describe, it, expect, mock } from 'bun:test';

let currentLocale = 'en';
const localeItems: Array<{ code: string; name: string; dir: string }> = [
  { code: 'en', name: 'English', dir: 'ltr' },
  { code: 'ar', name: 'العربية', dir: 'rtl' },
];

const createRef = <T>(initial: T) => {
  let val = initial;
  return {
    get value() {
      return val;
    },
    set value(v: T) {
      val = v;
    },
  };
};

const localeRef = createRef(currentLocale);
const localesRef = createRef(localeItems);

const useHeadMock = mock(() => {});

mock.module('#imports', () => ({
  useI18n: () => ({
    locale: localeRef,
    locales: localesRef,
    setLocale: async (code: string) => {
      currentLocale = code;
      localeRef.value = code;
    },
    t: (key: string) => key,
    te: (_key: string) => false,
  }),
  useHead: useHeadMock,
  computed: (fn: () => unknown) => ({
    get value() {
      return fn();
    },
  }),
}));

globalThis.useI18n = () => ({
  locale: localeRef,
  locales: localesRef,
  setLocale: async (code: string) => {
    currentLocale = code;
    localeRef.value = code;
  },
  t: (key: string) => key,
  te: (_key: string) => false,
});

globalThis.useHead = useHeadMock;
globalThis.computed = (fn: () => unknown) => ({
  get value() {
    return fn();
  },
});

const { useAppLocale } = await import('~/composables/useAppLocale');

describe('useAppLocale', () => {
  it('returns en as default locale', () => {
    currentLocale = 'en';
    localeRef.value = 'en';
    const { locale } = useAppLocale();
    expect(locale.value).toBe('en');
  });

  it('direction is ltr for English', () => {
    currentLocale = 'en';
    localeRef.value = 'en';
    const { direction, isRtl } = useAppLocale();
    expect(direction.value).toBe('ltr');
    expect(isRtl.value).toBe(false);
  });

  it('direction is rtl for Arabic', () => {
    currentLocale = 'ar';
    localeRef.value = 'ar';
    const { direction, isRtl } = useAppLocale();
    expect(direction.value).toBe('rtl');
    expect(isRtl.value).toBe(true);
  });

  it('changeLocale updates locale', async () => {
    currentLocale = 'en';
    localeRef.value = 'en';
    const { locale, changeLocale } = useAppLocale();
    await changeLocale('ar');
    expect(locale.value).toBe('ar');
  });

  it('changes locale back to en', async () => {
    currentLocale = 'ar';
    localeRef.value = 'ar';
    const { locale, changeLocale } = useAppLocale();
    await changeLocale('en');
    expect(locale.value).toBe('en');
  });

  it('exposes locales list', () => {
    currentLocale = 'en';
    localeRef.value = 'en';
    const { locales } = useAppLocale();
    expect(locales.value.length).toBe(2);
  });
});
