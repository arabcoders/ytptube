<template>
  <UModal
    v-model:open="open"
    :title="t('auth.account')"
    :dismissible="!busy"
    :ui="{
      content: 'w-full sm:max-w-2xl',
      body: 'max-h-[75vh] overflow-y-auto p-4 sm:p-5',
      footer: 'px-4 pb-4 sm:px-5 sm:pb-5',
    }"
  >
    <template #body>
      <div v-if="loading && !username" class="flex min-h-48 items-center justify-center">
        <UIcon name="i-lucide-loader-circle" class="size-8 animate-spin text-toned" />
        <span class="sr-only">{{ t('common.loading') }}</span>
      </div>
      <div v-else-if="loadFailed" class="space-y-3">
        <UAlert
          color="error"
          variant="soft"
          icon="i-lucide-circle-alert"
          :title="t('auth.errorTitle')"
          :description="t('common.failedFetch')"
        />
        <UButton
          color="neutral"
          variant="outline"
          icon="i-lucide-refresh-cw"
          :loading="loading"
          @click="load"
        >
          {{ t('common.retry') }}
        </UButton>
      </div>
      <div v-else class="space-y-6">
        <section class="space-y-3">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div class="flex min-w-0 items-center gap-3">
              <span class="ytp-detail-icon">
                <UIcon name="i-lucide-user-round-cog" class="size-4" />
              </span>
              <div>
                <h2 class="font-semibold text-highlighted">{{ t('auth.accountDetails') }}</h2>
                <p class="text-sm text-toned">{{ t('auth.accountDetailsDescription') }}</p>
              </div>
            </div>
            <UButton
              color="neutral"
              variant="outline"
              size="sm"
              icon="i-lucide-pencil"
              :disabled="busy"
              @click="openEdit"
            >
              {{ t('common.edit') }}
            </UButton>
          </div>
          <div
            class="flex min-w-0 items-center gap-3 rounded-sm border border-default bg-elevated/40 p-3"
          >
            <UIcon name="i-lucide-user" class="size-4 shrink-0 text-toned" />
            <div class="min-w-0">
              <p class="text-xs font-medium text-toned">{{ t('auth.username') }}</p>
              <p class="truncate font-semibold text-highlighted">{{ username }}</p>
            </div>
          </div>
        </section>

        <section class="space-y-3 border-t border-default pt-5">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div class="flex min-w-0 items-center gap-3">
              <span class="ytp-detail-icon">
                <UIcon name="i-lucide-key-round" class="size-4" />
              </span>
              <div>
                <h2 class="font-semibold text-highlighted">{{ t('auth.apiKeys') }}</h2>
                <p class="text-sm text-toned">{{ t('auth.apiKeysDescription') }}</p>
              </div>
            </div>
            <UButton
              color="neutral"
              variant="outline"
              size="sm"
              icon="i-lucide-plus"
              :disabled="busy"
              @click="openCreateKey"
            >
              {{ t('auth.createKey') }}
            </UButton>
          </div>
          <UEmpty
            v-if="!keys.length"
            icon="i-lucide-key-round"
            :title="t('auth.noApiKeys')"
            :description="t('auth.noApiKeysDescription')"
            class="py-8"
          />
          <div v-else class="divide-y divide-default rounded-sm border border-default">
            <div
              v-for="key in keys"
              :key="key.id"
              class="flex flex-col gap-3 p-3 sm:flex-row sm:items-center sm:justify-between"
            >
              <div class="min-w-0">
                <p class="truncate font-medium text-highlighted">{{ key.name }}</p>
                <div class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-toned">
                  <code class="rounded-sm bg-elevated px-1.5 py-0.5 font-mono"
                    >...{{ key.hint }}</code
                  >
                  <UTooltip :text="formatDateTime(key.created_at, locale)">
                    <span>{{
                      t('auth.createdAt', {
                        date: formatRelativeTime(key.created_at, locale),
                      })
                    }}</span>
                  </UTooltip>
                  <UTooltip
                    v-if="key.last_used_at"
                    :text="formatDateTime(key.last_used_at, locale)"
                  >
                    <span>{{
                      t('auth.lastUsedAt', {
                        date: formatRelativeTime(key.last_used_at, locale),
                      })
                    }}</span>
                  </UTooltip>
                </div>
              </div>
              <UButton
                color="error"
                variant="soft"
                size="sm"
                icon="i-lucide-trash-2"
                class="shrink-0 self-start sm:self-auto"
                :loading="revoking === key.id"
                :disabled="revoking !== null"
                @click="revoke(key.id)"
              >
                {{ t('auth.revoke') }}
              </UButton>
            </div>
          </div>
        </section>

        <section class="space-y-3 border-t border-default pt-5">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div class="flex min-w-0 items-center gap-3">
              <span class="ytp-detail-icon">
                <UIcon name="i-lucide-monitor" class="size-4" />
              </span>
              <div>
                <h2 class="font-semibold text-highlighted">{{ t('auth.sessions') }}</h2>
                <p class="text-sm text-toned">{{ t('auth.sessionsDescription') }}</p>
              </div>
            </div>
            <UButton
              color="error"
              variant="soft"
              size="sm"
              icon="i-lucide-log-out"
              :loading="revokingAll"
              :disabled="busy || !otherSessions"
              @click="revokeAll"
            >
              {{ t('auth.signOutAllOtherSessions') }}
            </UButton>
          </div>
          <UEmpty
            v-if="!sessions.length"
            icon="i-lucide-monitor"
            :title="t('auth.noSessions')"
            class="py-8"
          />
          <div v-else class="divide-y divide-default rounded-sm border border-default">
            <div
              v-for="session in sessions"
              :key="session.id"
              class="flex flex-col gap-3 p-3 sm:flex-row sm:items-center sm:justify-between"
            >
              <div class="min-w-0">
                <div class="flex flex-wrap items-center gap-2">
                  <p class="font-medium text-highlighted">{{ t('auth.session') }}</p>
                  <UBadge v-if="session.current" color="primary" variant="soft" size="sm">
                    {{ t('auth.currentSession') }}
                  </UBadge>
                </div>
                <div class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-toned">
                  <span class="min-w-0 wrap-break-word">{{ t('auth.userAgent') }}: </span>
                  <UTooltip v-if="session.user_agent?.trim()" :text="session.user_agent">
                    <span class="wrap-break-word">{{ browserSummary(session.user_agent) }}</span>
                  </UTooltip>
                  <span v-else>{{ t('common.unknown') }}</span>
                  <span>{{ t('auth.ipAddress') }}: {{ session.ip || t('common.unknown') }}</span>
                  <UTooltip :text="formatDateTime(session.created_at, locale)">
                    <span>{{
                      t('auth.createdAt', { date: formatRelativeTime(session.created_at, locale) })
                    }}</span>
                  </UTooltip>
                  <UTooltip :text="formatDateTime(session.expires_at, locale)">
                    <span>{{
                      t('auth.expiresAt', { date: formatRelativeTime(session.expires_at, locale) })
                    }}</span>
                  </UTooltip>
                </div>
              </div>
              <UButton
                color="error"
                variant="soft"
                size="sm"
                icon="i-lucide-log-out"
                class="shrink-0 self-start sm:self-auto"
                :loading="revoking === session.id"
                :disabled="session.current || revoking !== null || revokingAll"
                @click="revokeSession(session.id)"
              >
                {{ t('auth.signOut') }}
              </UButton>
            </div>
          </div>
        </section>
      </div>
    </template>
    <template #footer>
      <div class="flex w-full flex-wrap items-center justify-between gap-2">
        <UButton
          color="error"
          variant="soft"
          icon="i-lucide-log-out"
          :loading="loggingOut"
          :disabled="busy"
          @click="logout"
        >
          {{ t('auth.logout') }}
        </UButton>
        <UButton
          color="neutral"
          variant="outline"
          icon="i-lucide-x"
          :disabled="busy"
          @click="open = false"
        >
          {{ t('common.cancel') }}
        </UButton>
      </div>
    </template>
  </UModal>

  <UModal
    v-if="editOpen"
    :open="editOpen"
    :title="t('auth.editAccount')"
    :description="t('auth.editAccountDescription')"
    :dismissible="!saving"
    @update:open="handleEditOpenChange"
  >
    <template #body>
      <form id="accountForm" class="space-y-4" @submit.prevent="save">
        <UFormField :label="t('auth.username')" name="username"
          ><UInput
            v-model="editUsername"
            class="w-full"
            icon="i-lucide-user"
            autocomplete="username"
            :disabled="saving"
        /></UFormField>
        <UFormField :label="t('auth.currentPassword')" name="currentPassword" required
          ><UInput
            v-model="currentPassword"
            class="w-full"
            icon="i-lucide-lock-keyhole"
            :type="showCurrentPassword ? 'text' : 'password'"
            autocomplete="current-password"
            required
            :disabled="saving"
            :trailing-icon="showCurrentPassword ? 'i-lucide-eye-off' : 'i-lucide-eye'"
            @click:trailing="showCurrentPassword = !showCurrentPassword"
        /></UFormField>
        <UFormField :label="t('auth.newPassword')" name="newPassword"
          ><UInput
            v-model="newPassword"
            class="w-full"
            icon="i-lucide-lock-keyhole"
            :type="showNewPassword ? 'text' : 'password'"
            autocomplete="new-password"
            :disabled="saving"
            :trailing-icon="showNewPassword ? 'i-lucide-eye-off' : 'i-lucide-eye'"
            @click:trailing="showNewPassword = !showNewPassword"
        /></UFormField>
      </form>
    </template>
    <template #footer
      ><div class="flex w-full flex-wrap items-center justify-end gap-2">
        <UButton
          color="neutral"
          variant="outline"
          icon="i-lucide-x"
          :disabled="saving"
          @click="() => void requestCloseEdit()"
          >{{ t('common.cancel') }}</UButton
        ><UButton
          type="submit"
          form="accountForm"
          color="primary"
          icon="i-lucide-save"
          :loading="saving"
          :disabled="saving"
          >{{ t('common.save') }}</UButton
        >
      </div></template
    >
  </UModal>

  <UModal
    v-if="createOpen"
    :open="createOpen"
    :title="t('auth.createKey')"
    :description="t('auth.createKeyDescription')"
    :dismissible="!creating"
    @update:open="handleCreateOpenChange"
  >
    <template #body
      ><form id="keyForm" class="space-y-4" @submit.prevent="createKey">
        <UFormField :label="t('auth.keyName')" name="keyName" required
          ><UInput
            v-model="keyName"
            class="w-full"
            icon="i-lucide-key-round"
            autocomplete="off"
            required
            :disabled="creating"
        /></UFormField></form
    ></template>
    <template #footer
      ><div class="flex w-full flex-wrap items-center justify-end gap-2">
        <UButton
          color="neutral"
          variant="outline"
          icon="i-lucide-x"
          :disabled="creating"
          @click="() => void requestCloseCreate()"
          >{{ t('common.cancel') }}</UButton
        ><UButton
          type="submit"
          form="keyForm"
          color="primary"
          icon="i-lucide-plus"
          :loading="creating"
          :disabled="creating || !keyName.trim()"
          >{{ t('auth.createKey') }}</UButton
        >
      </div></template
    >
  </UModal>

  <UModal
    v-if="newKey"
    v-model:open="keyOpen"
    :title="t('auth.keyCreated')"
    :description="t('auth.copyWarning')"
    :dismissible="false"
  >
    <template #body
      ><div class="flex items-start gap-3 rounded-sm border border-default bg-elevated/50 p-3">
        <UIcon name="i-lucide-key-round" class="mt-0.5 size-4 shrink-0 text-toned" />
        <code class="min-w-0 break-all font-mono text-sm text-highlighted">{{ newKey }}</code>
      </div></template
    >
    <template #footer
      ><div class="flex w-full flex-wrap items-center justify-end gap-2">
        <UButton color="neutral" variant="outline" icon="i-lucide-check" @click="closeNewKey">{{
          t('common.ok')
        }}</UButton
        ><UButton color="primary" icon="i-lucide-copy" @click="copyKey">{{
          t('common.copy')
        }}</UButton>
      </div></template
    >
  </UModal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useDirtyCloseGuard } from '~/composables/useDirtyCloseGuard';
import { useDirtyState } from '~/composables/useDirtyState';
import {
  ApiError,
  browserSummary,
  copyText,
  ensure_api_success,
  parse_api_error,
  request,
} from '~/utils';
import { formatDateTime } from '~/utils/date';
import { formatRelativeTime } from '~/utils/relativeTime';

type ApiKey = {
  id: number;
  name: string;
  hint: string;
  created_at: string;
  last_used_at: string | null;
};
type AuthSession = {
  id: number;
  created_at: string;
  expires_at: string;
  current: boolean;
  user_agent: string | null;
  ip: string | null;
};
const open = defineModel<boolean>('open', { default: false });
const { t, locale } = useI18n();
const auth = useAuth();
const notify = useNotification();
const { confirm } = useConfirm();
const username = ref('');
const editUsername = ref('');
const currentPassword = ref('');
const newPassword = ref('');
const keyName = ref('');
const newKey = ref('');
const keys = ref<ApiKey[]>([]);
const sessions = ref<AuthSession[]>([]);
const loading = ref(false);
const loadFailed = ref(false);
const saving = ref(false);
const creating = ref(false);
const loggingOut = ref(false);
const revoking = ref<number | null>(null);
const revokingAll = ref(false);
const editOpen = ref(false);
const createOpen = ref(false);
const keyOpen = ref(true);
const showCurrentPassword = ref(false);
const showNewPassword = ref(false);
const busy = computed(
  () =>
    loading.value ||
    saving.value ||
    creating.value ||
    loggingOut.value ||
    revoking.value !== null ||
    revokingAll.value,
);
const otherSessions = computed(() => sessions.value.some((session) => !session.current));
const editSource = computed(() => ({
  username: editUsername.value,
  currentPassword: currentPassword.value,
  newPassword: newPassword.value,
}));
const createSource = computed(() => ({ name: keyName.value }));
const editDirty = useDirtyState(editSource);
const createDirty = useDirtyState(createSource);

const discardEdit = (): void => {
  editUsername.value = username.value;
  currentPassword.value = '';
  newPassword.value = '';
  showCurrentPassword.value = false;
  showNewPassword.value = false;
  editDirty.markClean();
};
const discardCreate = (): void => {
  keyName.value = '';
  createDirty.markClean();
};
const { handleOpenChange: handleEditOpenChange, requestClose: requestCloseEdit } =
  useDirtyCloseGuard(editOpen, {
    dirty: editDirty.isDirty,
    preferenceKey: 'account',
    onDiscard: discardEdit,
    routeGuards: false,
  });
const { handleOpenChange: handleCreateOpenChange, requestClose: requestCloseCreate } =
  useDirtyCloseGuard(createOpen, {
    dirty: createDirty.isDirty,
    preferenceKey: 'account-api-key',
    onDiscard: discardCreate,
    routeGuards: false,
  });

const report = async (error: unknown): Promise<void> => {
  if (error instanceof Response) notify.error(await parse_api_error(await error.json()));
  else if (error instanceof ApiError && error.payload)
    notify.error(await parse_api_error(error.payload));
  else notify.error(error instanceof Error ? error.message : String(error));
};
const load = async (): Promise<void> => {
  if (loading.value) return;
  loading.value = true;
  loadFailed.value = false;
  try {
    const me = await request('/api/auth/me');
    await ensure_api_success(me);
    const user = ((await me.json()) as { user: { username: string } }).user;
    username.value = user.username;
    editUsername.value = user.username;
    const response = await request('/api/auth/api-keys');
    await ensure_api_success(response);
    keys.value = ((await response.json()) as { items: ApiKey[] }).items;
    const sessionResponse = await request('/api/auth/sessions');
    await ensure_api_success(sessionResponse);
    sessions.value = ((await sessionResponse.json()) as { items: AuthSession[] }).items;
  } catch (error) {
    loadFailed.value = true;
    await report(error);
  } finally {
    loading.value = false;
  }
};
const openEdit = (): void => {
  discardEdit();
  editOpen.value = true;
};
const save = async (): Promise<void> => {
  if (saving.value) return;
  saving.value = true;
  try {
    const response = await request('/api/auth/account', {
      method: 'PATCH',
      body: JSON.stringify({
        current_password: currentPassword.value,
        username: editUsername.value || undefined,
        password: newPassword.value || undefined,
      }),
    });
    await ensure_api_success(response);
    username.value = editUsername.value;
    await auth.probe();
    notify.success(t('auth.accountSaved'));
    editDirty.markClean();
    editOpen.value = false;
  } catch (error) {
    await report(error);
  } finally {
    saving.value = false;
  }
};
const openCreateKey = (): void => {
  discardCreate();
  createOpen.value = true;
};
const createKey = async (): Promise<void> => {
  if (creating.value || !keyName.value.trim()) return;
  creating.value = true;
  try {
    const response = await request('/api/auth/api-keys', {
      method: 'POST',
      body: JSON.stringify({ name: keyName.value.trim() }),
    });
    await ensure_api_success(response);
    newKey.value = ((await response.json()) as { key: string }).key;
    keyOpen.value = true;
    createDirty.markClean();
    createOpen.value = false;
    await load();
  } catch (error) {
    await report(error);
  } finally {
    creating.value = false;
  }
};
const closeNewKey = (): void => {
  newKey.value = '';
  keyOpen.value = false;
};
const copyKey = (): void => {
  if (newKey.value) {
    copyText(newKey.value);
  }
};
const revoke = async (id: number): Promise<void> => {
  if (revoking.value !== null) return;
  if (
    !(await confirm(t('auth.revokeConfirm'), {
      confirmText: t('auth.revoke'),
      confirmColor: 'error',
    }))
  )
    return;
  revoking.value = id;
  try {
    const response = await request(`/api/auth/api-keys/${id}`, { method: 'DELETE' });
    await ensure_api_success(response);
    await load();
  } catch (error) {
    await report(error);
  } finally {
    revoking.value = null;
  }
};
const revokeSession = async (id: number): Promise<void> => {
  if (revoking.value !== null) return;
  if (
    !(await confirm(t('auth.signOutConfirm'), {
      confirmText: t('auth.signOut'),
      confirmColor: 'error',
    }))
  )
    return;
  revoking.value = id;
  try {
    const response = await request(`/api/auth/sessions/${id}`, { method: 'DELETE' });
    await ensure_api_success(response);
    await load();
  } catch (error) {
    await report(error);
  } finally {
    revoking.value = null;
  }
};
const revokeAll = async (): Promise<void> => {
  if (revokingAll.value || !otherSessions.value) return;
  if (
    !(await confirm(t('auth.signOutAllConfirm'), {
      confirmText: t('auth.signOutAllOtherSessions'),
      confirmColor: 'error',
    }))
  )
    return;
  revokingAll.value = true;
  try {
    const response = await request('/api/auth/sessions', { method: 'DELETE' });
    await ensure_api_success(response);
    await load();
  } catch (error) {
    await report(error);
  } finally {
    revokingAll.value = false;
  }
};
const logout = async (): Promise<void> => {
  if (loggingOut.value) return;
  loggingOut.value = true;
  try {
    const response = await request('/api/auth/logout', { method: 'POST' });
    await ensure_api_success(response);
    open.value = false;
    await navigateTo('/login');
  } catch (error) {
    await report(error);
  } finally {
    loggingOut.value = false;
  }
};
watch(open, (value) => {
  if (value) void load();
});
</script>
