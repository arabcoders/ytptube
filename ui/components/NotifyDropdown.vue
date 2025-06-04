<template>
  <div class="navbar-item has-dropdown is-hoverable">
    <a class="navbar-link">
      <span class="icon"><i class="fas fa-bell" /></span>
      <span class="tag ml-2">
        <span class="is-underlined">{{ store.unreadCount }}</span>
        <span>&nbsp;/&nbsp;</span>
        <span class="is-underlined">{{ store.notifications.length }}</span>
      </span>
    </a>
    <div class="navbar-dropdown is-right" style="width: 400px;">
      <template v-if="store.notifications.length > 0">
        <div class="px-3 py-2 is-flex is-justify-content-space-between is-align-items-center">
          <span class="has-text-grey"></span>

          <div class="field is-grouped">
            <div class="control" v-if="store.unreadCount > 0">
              <button class="button is-small is-light mr-1" @click="store.markAllRead">
                <span class="icon"><i class="fas fa-check" /></span>
                <span>Mark all read</span>
              </button>
            </div>

            <div class="control">
              <button class="button is-small is-danger is-light" @click="store.clear">
                <span class="icon"><i class="fas fa-trash" /></span>
                <span>Clear all</span>
              </button>
            </div>
          </div>
        </div>
        <hr class="navbar-divider">
      </template>
      <div class="notification-list">
        <div v-for="n in store.notifications" :key="n.id" class="navbar-item is-flex is-align-items-start"
          :class="['notification-item', 'notification-' + n.level]">
          <div class="is-flex-grow-1">
            <p class="is-size-7 mb-1 notification-message" :class="{ expanded: expandedId === n.id }"
              @click="toggleExpand(n.id)">
              {{ n.message }}
            </p>
            <p class="is-size-7 has-text-grey">
              <span :date-datetime="n.created" v-tooltip="moment(n.created).format('YYYY-M-DD H:mm Z')"
                v-rtime="n.created" />
              - <NuxtLink @click="copy_text(n.id, n.message)">
                <span v-if="copiedId === n.id" class="has-text-success">Copied!</span>
                <span v-else>Copy</span>
              </NuxtLink>
            </p>
          </div>
          <div class="ml-3 is-flex is-flex-direction-column is-justify-content-center">
            <div class="field is-grouped">
              <div class="control" v-if="!n.seen">
                <button class="button is-small is-light" @click="store.markRead(n.id)">
                  <span class="icon"><i class="fas fa-check" /></span>
                </button>
              </div>
              <div class="control">
                <button class="button is-danger is-small" @click="store.remove(n.id)">
                  <span class="icon"><i class="fas fa-trash" /></span>
                </button>
              </div>
            </div>
          </div>
        </div>
        <div v-if="store.notifications.length < 1" class="navbar-item is-flex is-align-items-start">
          <div class="is-flex-grow-1 has-text-centered has-text-grey">
            <p class="is-size-7">No notifications</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import moment from 'moment'
const store = useNotificationStore()
const copiedId = ref(null)
const expandedId = ref(null)

const toggleExpand = id => expandedId.value = expandedId.value === id ? null : id

const copy_text = (id, text) => {
  copiedId.value = id
  copyText(text, false, false)
  setTimeout(() => {
    if (copiedId.value === id) {
      copiedId.value = null
    }
  }, 2000)
}
</script>

<style scoped>
.notification-item {
  border-left: 4px solid transparent;
  padding-left: 0.75rem;
  border-bottom: 1px solid #f5f5f5;
}

.notification-info {
  border-color: var(--bulma-info);
}

.notification-success {
  border-color: var(--bulma-primary);
}

.notification-warning {
  border-color: var(--bulma-warning);
}

.notification-error {
  border-color: var(--bulma-danger);
}

.notification-list {
  max-height: 300px;
  overflow-y: auto;
}

.notification-message {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
  max-width: 280px;
}

.notification-message.expanded {
  white-space: normal;
  word-break: break-word;
  max-width: 100%;
}
</style>
