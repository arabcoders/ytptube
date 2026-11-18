<template>
  <div class="min-h-screen">
    <UApp :locale="uiLocale" :dir="direction">
      <main
        class="shell-surface relative flex min-h-dvh w-full items-center justify-center overflow-hidden px-4 py-8 sm:px-6"
      >
        <div class="relative w-full max-w-md space-y-6">
          <header class="space-y-3 text-center">
            <div
              class="mx-auto inline-flex size-14 items-center justify-center rounded-md border border-default bg-elevated/80 shadow-sm"
            >
              <img
                :src="uri('/images/favicon.png')"
                :alt="t('auth.brandAlt')"
                class="size-10 rounded-md object-contain"
              />
            </div>
            <h1 class="text-2xl font-semibold text-highlighted">YTPTube</h1>
            <p class="text-sm text-muted">{{ subtitle }}</p>
          </header>

          <UCard
            :ui="{
              header: 'px-5 py-4 sm:px-6',
              body: 'p-5 sm:p-6',
            }"
          >
            <template #header>
              <div class="flex flex-wrap items-center justify-between gap-3">
                <h2 class="text-base font-semibold text-highlighted">{{ title }}</h2>
                <div class="flex items-center gap-1">
                  <ThemeButton square :show-label="false" />
                  <USelect
                    :model-value="locale"
                    :items="localeOptions"
                    value-key="code"
                    label-key="label"
                    icon="i-lucide-languages"
                    size="sm"
                    class="w-32"
                    :aria-label="t('common.language')"
                    @update:model-value="(value: unknown) => void changeLocale(value as string)"
                  />
                </div>
              </div>
            </template>

            <slot />
          </UCard>
        </div>
      </main>
    </UApp>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { uri } from '~/utils';
import { getUiLocale } from '~/utils/ui-locales';

const route = useRoute();
const { t } = useI18n();
const { locale, locales, direction, changeLocale } = useAppLocale();
const uiLocale = computed(() => getUiLocale(locale.value));
const setup = computed(() => route.name === 'setup');
const title = computed(() => t(setup.value ? 'auth.setupHeading' : 'auth.loginHeading'));
const subtitle = computed(() => t(setup.value ? 'auth.setupSubtitle' : 'auth.loginSubtitle'));
const localeOptions = computed(() =>
  locales.value.map((entry) =>
    typeof entry === 'string'
      ? { code: entry, label: String(entry).toUpperCase() }
      : { code: entry.code, label: entry.name },
  ),
);
</script>
