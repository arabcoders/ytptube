<template>
  <div class="min-h-screen">
    <UApp :locale="uiLocale" :dir="direction">
      <main
        class="relative flex min-h-screen w-full items-center justify-center overflow-hidden bg-default px-4 py-8 sm:px-6"
      >
        <div
          class="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgb(59_130_246/0.16),transparent_42%),radial-gradient(circle_at_bottom_right,rgb(14_165_233/0.12),transparent_40%)] dark:bg-[radial-gradient(circle_at_top_left,rgb(59_130_246/0.22),transparent_42%),radial-gradient(circle_at_bottom_right,rgb(14_165_233/0.14),transparent_40%)]"
        />

        <div class="relative w-full max-w-md space-y-5">
          <div class="flex justify-end gap-1" :class="isRtl ? 'flex-row-reverse' : ''">
            <ThemeButton :square="true" :show-label="false" />
            <USelect
              :model-value="locale"
              :items="localeOptions"
              value-key="code"
              label-key="label"
              icon="i-lucide-languages"
              size="sm"
              class="min-w-32"
              :aria-label="t('auth.language')"
              @update:model-value="(value: unknown) => void changeLocale(value as string)"
            />
          </div>

          <section
            class="space-y-6 rounded-2xl border border-default bg-elevated/70 p-5 shadow-2xl backdrop-blur-sm sm:p-8"
          >
            <header class="space-y-4 text-center">
              <div
                class="mx-auto flex size-16 items-center justify-center rounded-2xl border border-default bg-default shadow-sm"
              >
                <img
                  :src="uri('/images/favicon.png')"
                  :alt="t('auth.brandAlt')"
                  class="size-10 rounded-xl object-contain"
                />
              </div>
              <div>
                <p class="text-sm font-semibold tracking-[0.18em] text-primary uppercase">
                  YTPTube
                </p>
                <h1 class="mt-2 text-2xl font-semibold text-highlighted">{{ title }}</h1>
                <p class="mt-1 text-sm text-toned">{{ subtitle }}</p>
              </div>
            </header>

            <slot />
          </section>
        </div>
      </main>
    </UApp>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { getUiLocale } from '~/utils/ui-locales';

const route = useRoute();
const { t } = useI18n();
const { locale, locales, direction, isRtl, changeLocale } = useAppLocale();
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
