export const useAppLocale = () => {
  const { locale, locales, setLocale } = useI18n();

  const currentLocale = computed(() =>
    locales.value.find((entry) =>
      typeof entry === 'string' ? entry === locale.value : entry.code === locale.value,
    ),
  );

  const direction = computed<'ltr' | 'rtl'>(() => {
    const entry = currentLocale.value;
    if (entry && typeof entry !== 'string' && entry.dir === 'rtl') return 'rtl';
    return 'ltr';
  });

  const changeLocale = async (code: string): Promise<void> => {
    await (setLocale as (code: string) => Promise<void>)(code);
  };

  useHead({
    htmlAttrs: {
      lang: locale,
      dir: direction,
    },
  });

  return {
    locale,
    locales,
    direction,
    isRtl: computed(() => direction.value === 'rtl'),
    changeLocale,
  };
};
