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
          id="login-username"
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
          id="login-password"
          v-model="password"
          class="w-full"
          :type="showPassword ? 'text' : 'password'"
          :placeholder="t('auth.password')"
          icon="i-lucide-lock-keyhole"
          autocomplete="current-password"
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
      <UButton type="submit" color="primary" block icon="i-lucide-log-in" :loading="busy">
        {{ t('auth.loginAction') }}
      </UButton>
    </form>
    <UButton variant="link" color="neutral" class="w-full" @click="recoveryOpen = true">
      {{ t('auth.forgotPassword') }}
    </UButton>

    <UModal v-model:open="recoveryOpen" :title="t('auth.forgotPassword')">
      <template #body>
        <div class="space-y-3">
          <p class="text-sm text-toned">{{ t('auth.recoveryGuidance') }}</p>
          <a
            class="text-sm font-medium text-primary hover:underline"
            href="https://github.com/arabcoders/ytptube/blob/master/FAQ.md#how-do-i-reset-a-forgotten-password"
            target="_blank"
            rel="noopener noreferrer"
          >
            {{ t('auth.recoveryInstructions') }}
          </a>
        </div>
      </template>
    </UModal>
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
const recoveryOpen = ref(false);

const submit = async (): Promise<void> => {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    await auth.login(username.value, password.value);
    await navigateTo('/');
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause);
  } finally {
    busy.value = false;
  }
};
</script>
