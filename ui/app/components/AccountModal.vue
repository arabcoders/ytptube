<template>
  <UModal
    v-model:open="open"
    :title="t('auth.account')"
    :description="t('auth.accountDescription')"
    :dismissible="!busy"
    :ui="{ content: 'w-full sm:max-w-4xl', body: 'max-h-[80vh] overflow-y-auto p-4 sm:p-6' }"
  >
    <template #body>
      <div class="space-y-5">
        <section class="ytp-card space-y-5 p-4 sm:p-6">
          <div class="flex flex-wrap items-start justify-between gap-4">
            <div class="flex items-start gap-3">
              <span class="ytp-section-icon"
                ><UIcon name="i-lucide-user-round-cog" class="size-5"
              /></span>
              <div>
                <h2 class="font-semibold text-highlighted">{{ t('auth.accountDetails') }}</h2>
                <p class="mt-1 text-sm text-toned">{{ t('auth.accountDetailsDescription') }}</p>
              </div>
            </div>
            <UButton
              color="neutral"
              variant="outline"
              size="sm"
              icon="i-lucide-pencil"
              @click="openEdit"
            >
              {{ t('common.edit') }}
            </UButton>
          </div>
          <div class="rounded-lg border border-default bg-elevated/40 p-4">
            <p class="text-xs font-semibold uppercase tracking-wide text-toned">
              {{ t('auth.username') }}
            </p>
            <p class="mt-1 break-all text-lg font-semibold text-highlighted">
              {{ username || t('auth.account') }}
            </p>
          </div>
        </section>

        <section class="ytp-card space-y-5 p-4 sm:p-6">
          <div class="flex flex-wrap items-start justify-between gap-4">
            <div class="flex items-start gap-3">
              <span class="ytp-section-icon"
                ><UIcon name="i-lucide-key-round" class="size-5"
              /></span>
              <div>
                <h2 class="font-semibold text-highlighted">{{ t('auth.apiKeys') }}</h2>
                <p class="mt-1 text-sm text-toned">{{ t('auth.apiKeysDescription') }}</p>
              </div>
            </div>
            <UButton
              color="neutral"
              variant="outline"
              size="sm"
              icon="i-lucide-plus"
              @click="openCreateKey"
            >
              {{ t('auth.createKey') }}
            </UButton>
          </div>
          <UAlert
            v-if="!keys.length"
            color="neutral"
            variant="soft"
            icon="i-lucide-key-round"
            :title="t('auth.noApiKeys')"
            :description="t('auth.noApiKeysDescription')"
          />
          <div v-else class="space-y-3">
            <div
              v-for="key in keys"
              :key="key.id"
              class="flex flex-col gap-4 rounded-lg border border-default p-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <div class="flex min-w-0 items-start gap-3">
                <UIcon name="i-lucide-key-round" class="mt-0.5 size-5 shrink-0 text-toned" />
                <div class="min-w-0">
                  <p class="truncate font-semibold text-highlighted">{{ key.name }}</p>
                  <div class="mt-1 flex flex-wrap items-center gap-2 text-xs text-toned">
                    <UBadge color="neutral" variant="soft">...{{ key.hint }}</UBadge>
                    <span>{{
                      t('auth.createdAt', { date: formatDateTime(key.created_at, locale) })
                    }}</span>
                    <span v-if="key.last_used_at">{{
                      t('auth.lastUsedAt', { date: formatDateTime(key.last_used_at, locale) })
                    }}</span>
                  </div>
                </div>
              </div>
              <UButton
                color="error"
                variant="soft"
                size="sm"
                icon="i-lucide-trash-2"
                class="shrink-0 self-start sm:self-auto"
                @click="revoke(key.id)"
              >
                {{ t('auth.revoke') }}
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
        /></UFormField>
        <UFormField :label="t('auth.currentPassword')" name="currentPassword" required
          ><UInput
            v-model="currentPassword"
            class="w-full"
            icon="i-lucide-lock-keyhole"
            :type="showCurrentPassword ? 'text' : 'password'"
            autocomplete="current-password"
            required
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
      ><form id="keyForm" @submit.prevent="createKey">
        <UFormField :label="t('auth.keyName')" name="keyName" required
          ><UInput
            v-model="keyName"
            class="w-full"
            icon="i-lucide-key-round"
            autocomplete="off"
            required
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
      ><div class="flex items-start gap-3 rounded-lg border border-default bg-elevated/50 p-4">
        <UIcon name="i-lucide-key-round" class="mt-0.5 size-5 shrink-0 text-toned" />
        <code class="min-w-0 break-all font-mono text-sm text-highlighted">{{ newKey }}</code>
      </div></template
    >
    <template #footer
      ><div class="flex w-full flex-wrap items-center justify-end gap-2">
        <UButton color="neutral" variant="outline" icon="i-lucide-check" @click="closeNewKey">{{
          t('common.ok')
        }}</UButton
        ><UButton icon="i-lucide-copy" @click="copyKey">{{ t('common.copy') }}</UButton>
      </div></template
    >
  </UModal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useDirtyCloseGuard } from '~/composables/useDirtyCloseGuard';
import { useDirtyState } from '~/composables/useDirtyState';
import { ApiError, copyText, ensure_api_success, parse_api_error, request } from '~/utils';
import { formatDateTime } from '~/utils/date';

type ApiKey = {
  id: number;
  name: string;
  hint: string;
  created_at: string;
  last_used_at: string | null;
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
const loading = ref(false);
const saving = ref(false);
const creating = ref(false);
const loggingOut = ref(false);
const editOpen = ref(false);
const createOpen = ref(false);
const keyOpen = ref(true);
const showCurrentPassword = ref(false);
const showNewPassword = ref(false);
const busy = computed(() => loading.value || saving.value || creating.value || loggingOut.value);
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
  try {
    const me = await request('/api/auth/me');
    await ensure_api_success(me);
    const user = ((await me.json()) as { user: { username: string } }).user;
    username.value = user.username;
    editUsername.value = user.username;
    const response = await request('/api/auth/api-keys');
    await ensure_api_success(response);
    keys.value = ((await response.json()) as { items: ApiKey[] }).items;
  } catch (error) {
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
  if (
    !(await confirm(t('auth.revokeConfirm'), {
      confirmText: t('auth.revoke'),
      confirmColor: 'error',
    }))
  )
    return;
  try {
    const response = await request(`/api/auth/api-keys/${id}`, { method: 'DELETE' });
    await ensure_api_success(response);
    await load();
  } catch (error) {
    await report(error);
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
