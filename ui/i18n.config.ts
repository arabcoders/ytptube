export default defineI18nConfig(() => ({
  legacy: false,
  fallbackLocale: 'en',
  missingWarn: import.meta.dev,
  fallbackWarn: import.meta.dev,
}));
