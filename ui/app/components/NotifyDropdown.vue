<template>
  <UPopover :content="{ align: 'end', side: 'bottom', sideOffset: 8 }">
    <UButton color="neutral" variant="ghost" size="sm">
      <template #leading>
        <UIcon name="i-lucide-bell" class="size-4" />
      </template>
      <span class="hidden sm:inline">{{ t('common.notifications') }}</span>
      <template #trailing>
        <UBadge :color="severityTone" variant="soft" size="sm"
          >{{ store.unreadCount }}/{{ store.notifications.length }}</UBadge
        >
      </template>
    </UButton>

    <template #content>
      <UCard
        class="w-md max-w-[calc(100vw-1rem)]"
        :ui="{
          header: 'flex items-center justify-between gap-3',
          body: 'sm:p-2 p-0',
          footer: 'flex justify-end gap-2',
        }"
      >
        <template #header>
          <div>
            <p class="text-sm font-semibold text-highlighted">{{ t('common.notifications') }}</p>
            <p class="text-xs text-toned">{{ t('app.notifications.subtitle') }}</p>
          </div>

          <div class="flex items-center gap-1">
            <UTooltip
              :text="
                allow_toasts ? t('common.pauseNotifications') : t('common.resumeNotifications')
              "
            >
              <UButton
                color="neutral"
                variant="ghost"
                size="xs"
                square
                :icon="allow_toasts ? 'i-lucide-bell' : 'i-lucide-bell-off'"
                @click="toggleToasts"
              />
            </UTooltip>
            <UBadge :color="severityTone" variant="soft" size="sm">
              {{ t('app.notifications.unread', { count: store.unreadCount }) }}
            </UBadge>
          </div>
        </template>

        <template #default>
          <div
            v-if="store.sortedNotifications.length > 0"
            ref="scrollEl"
            class="max-h-104 overflow-y-auto p-0"
          >
            <div class="space-y-2">
              <LateLoader
                v-for="item in store.sortedNotifications"
                :key="item.id"
                :root="scrollEl"
                :min-height="55"
                unrender
              >
                <UAlert
                  orientation="horizontal"
                  variant="outline"
                  color="neutral"
                  :icon="notificationIcon(item.level)"
                  :title="item.message"
                  :ui="{
                    root: 'select-none rounded-none border border-default border-s-4 bg-default px-3 py-2 transition-colors hover:bg-muted/40',
                    icon: 'size-4 mt-0.5',
                    title:
                      expandedId === item.id
                        ? 'whitespace-normal break-words text-sm'
                        : 'truncate text-sm',
                    description: 'mt-1 text-xs text-toned',
                    actions: 'items-center gap-1 ms-2',
                  }"
                  :class="notificationAlertClass(item.level, item.id)"
                  @click="handleNotificationClick(item.id)"
                >
                  <template #description>
                    <span class="flex items-center gap-1 text-xs text-toned">
                      <UTooltip :text="moment(item.created).format('YYYY-M-DD H:mm Z')">
                        <span :date-datetime="item.created" v-rtime="item.created" />
                      </UTooltip>
                      <span>-</span>
                      <button
                        type="button"
                        class="underline underline-offset-2"
                        @click.stop="copy_text(item.id, item.message)"
                      >
                        <span v-if="copiedId === item.id" class="text-success">{{
                          t('app.notifications.copied')
                        }}</span>
                        <span v-else>{{ t('common.copy') }}</span>
                      </button>
                    </span>
                  </template>

                  <template #actions>
                    <UButton
                      v-if="!item.seen"
                      color="neutral"
                      variant="ghost"
                      size="xs"
                      square
                      @click.stop="store.markRead(item.id)"
                    >
                      <UIcon name="i-lucide-check" class="size-3.5" />
                    </UButton>
                    <UButton
                      color="neutral"
                      variant="ghost"
                      size="xs"
                      square
                      @click.stop="store.remove(item.id)"
                    >
                      <UIcon name="i-lucide-trash" class="size-3.5" />
                    </UButton>
                  </template>
                </UAlert>
              </LateLoader>
            </div>
          </div>

          <UEmpty
            v-else
            icon="i-lucide-inbox"
            :title="t('app.notifications.noNotifications')"
            :description="t('app.notifications.noNotificationsDesc')"
            class="px-4 py-8"
          />
        </template>

        <template #footer>
          <UButton
            color="neutral"
            variant="ghost"
            size="sm"
            icon="i-lucide-check"
            :disabled="store.unreadCount === 0"
            @click="store.markAllRead()"
          >
            {{ t('app.notifications.markAllRead') }}
          </UButton>

          <UButton
            color="neutral"
            variant="ghost"
            size="sm"
            icon="i-lucide-trash"
            :disabled="store.notifications.length === 0"
            @click="store.clear()"
          >
            {{ t('app.notifications.clearAll') }}
          </UButton>
        </template>
      </UCard>
    </template>
  </UPopover>
</template>

<script setup lang="ts">
import moment from 'moment';
import { useStorage } from '@vueuse/core';
import { useNotificationCenter } from '~/composables/useNotificationCenter';
import type { notificationType } from '~/composables/useNotification';

const { t } = useI18n();

const store = useNotificationCenter();

const allow_toasts = useStorage<boolean>('allow_toasts', true);

const toggleToasts = () => {
  allow_toasts.value = !allow_toasts.value;
};

const scrollEl = ref<HTMLElement | null>(null);
const copiedId = ref<string | null>(null);
const expandedId = ref<string | null>(null);

const severityTone = computed(() => {
  switch (store.severityLevel) {
    case 'error':
      return 'error' as const;
    case 'warning':
      return 'warning' as const;
    case 'success':
      return 'success' as const;
    case 'info':
      return 'info' as const;
    default:
      return 'neutral' as const;
  }
});

const notificationIcon = (level: notificationType): string => {
  switch (level) {
    case 'error':
      return 'i-lucide-triangle-alert';
    case 'warning':
      return 'i-lucide-circle-alert';
    case 'success':
      return 'i-lucide-badge-check';
    case 'info':
    default:
      return 'i-lucide-info';
  }
};

const notificationAlertClass = (level: notificationType, id: string): string => {
  const selectedClass = expandedId.value === id ? 'bg-muted/55 ring-1 ring-inset ring-default' : '';

  switch (level) {
    case 'error':
      return `border-s-error text-default ${selectedClass}`.trim();
    case 'warning':
      return `border-s-warning text-default ${selectedClass}`.trim();
    case 'success':
      return `border-s-success text-default ${selectedClass}`.trim();
    case 'info':
    default:
      return `border-s-info text-default ${selectedClass}`.trim();
  }
};

const toggleExpand = (id: string) => (expandedId.value = expandedId.value === id ? null : id);

const handleNotificationClick = (id: string) => {
  toggleExpand(id);
  store.markRead(id);
};

const copy_text = (id: string, text: string): void => {
  copiedId.value = id;
  copyText(text, false, false);
  setTimeout(() => {
    if (copiedId.value === id) copiedId.value = null;
  }, 2000);
};
</script>
