<template>
  <div class="space-y-6">
    <UAlert
      v-if="error"
      color="error"
      variant="soft"
      icon="i-lucide-circle-alert"
      :title="t('auth.errorTitle')"
      :description="error"
      data-testid="auth-error"
    />
    <form class="space-y-5" @submit.prevent="submit">
      <UFormField :label="t('auth.username')" name="username" required>
        <UInput
          id="setup-username"
          v-model="username"
          class="w-full"
          :placeholder="t('auth.username')"
          icon="i-lucide-user"
          autocomplete="username"
          autofocus
        />
      </UFormField>
      <UFormField :label="t('auth.password')" name="password" required>
        <UInput
          id="setup-password"
          v-model="password"
          class="w-full"
          :type="showPassword ? 'text' : 'password'"
          :placeholder="t('auth.password')"
          icon="i-lucide-lock-keyhole"
          autocomplete="new-password"
        >
          <template #trailing>
            <UButton
              type="button"
              color="neutral"
              variant="ghost"
              square
              size="xs"
              :icon="showPassword ? 'i-lucide-eye-off' : 'i-lucide-eye'"
              :aria-label="showPassword ? t('auth.hidePassword') : t('auth.showPassword')"
              @click="showPassword = !showPassword"
            />
          </template>
        </UInput>
      </UFormField>
      <UButton type="submit" color="primary" block icon="i-lucide-user-plus" :loading="busy">
        {{ t('auth.setupAction') }}
      </UButton>
    </form>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: 'auth' });

const { t } = useI18n();
const auth = useAuth();
const username = ref('');
const password = ref('');
const error = ref('');
const busy = ref(false);
const showPassword = ref(false);

const submit = async (): Promise<void> => {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    const redirect = authRedirect(await auth.probe(true), '/setup');
    if (redirect) {
      await navigateTo(redirect);
      return;
    }
    await auth.setup(username.value, password.value);
    await navigateTo('/');
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause);
  } finally {
    busy.value = false;
  }
};
</script>
