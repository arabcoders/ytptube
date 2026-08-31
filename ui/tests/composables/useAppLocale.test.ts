import { describe, it, expect, mock } from 'bun:test';
import { computed, ref } from 'vue';

const localeRef = ref('en');
const localesRef = ref<Array<{ code: string; name: string; dir: string }>>([
  { code: 'en', name: 'English', dir: 'ltr' },
  { code: 'ar', name: 'العربية', dir: 'rtl' },
]);

const useHeadMock = mock(() => {});

mock.module('#imports', () => ({
  useI18n: () => ({
    locale: localeRef,
    locales: localesRef,
    setLocale: async (code: string) => {
      localeRef.value = code;
    },
    t: (key: string) => key,
    te: (_key: string) => false,
  }),
  useHead: useHeadMock,
}));

globalThis.useI18n = () => ({
  locale: localeRef,
  locales: localesRef,
  setLocale: async (code: string) => {
    localeRef.value = code;
  },
  t: (key: string) => key,
  te: (_key: string) => false,
});

globalThis.useHead = useHeadMock;
globalThis.computed = computed;

const { useAppLocale } = await import('~/composables/useAppLocale');

describe('useAppLocale', () => {
  it('direction is ltr for English', () => {
    localeRef.value = 'en';
    const { direction, isRtl } = useAppLocale();
    expect(direction.value).toBe('ltr');
    expect(isRtl.value).toBe(false);
  });

  it('direction is rtl for Arabic', () => {
    localeRef.value = 'ar';
    const { direction, isRtl } = useAppLocale();
    expect(direction.value).toBe('rtl');
    expect(isRtl.value).toBe(true);
  });

  it('changeLocale updates locale', async () => {
    localeRef.value = 'en';
    const { locale, changeLocale } = useAppLocale();
    await changeLocale('ar');
    expect(locale.value).toBe('ar');
  });
});
