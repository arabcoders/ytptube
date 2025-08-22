<style scoped>
#logView {
  min-height: 72vh;
  min-width: inherit;
  max-width: 100%;
}

#logView>span:nth-child(even) {
  color: #ffc9d4;
}

#logView>span:nth-child(odd) {
  color: #e3c981;
}

.logbox {
  background-color: #1f2229 !important;
  box-shadow: 0 4px 8px 0 rgba(0, 0, 0, 0.2), 0 6px 20px 0 rgba(0, 0, 0, 0.19);
  min-width: 100%;
  max-height: 73vh;
  overflow-y: scroll;
  overflow-x: auto;
}

code {
  background-color: unset;
}

.logline {
  word-break: break-all;
  line-height: 1.75rem;
  padding: 1em;
  color: #fff1b8;
}
</style>

<template>
  <div>
    <div class="mt-1 columns is-multiline">
      <div class="column is-12 is-clearfix is-unselectable">
        <span class="title is-4">
          <span class="icon"><i class="fas fa-file-lines" /></span>
          Logs
        </span>
        <div class="is-pulled-right">
          <div class="field is-grouped">
            <div class="control">
              <button v-if="!autoScroll" @click="scrollToBottom(false)" class="button is-primary">
                <span class="icon"><i class="fas fa-arrow-down"></i></span>
                <span>Go to Bottom</span>
              </button>
            </div>

            <div class="control has-icons-left" v-if="toggleFilter || query">
              <input type="search" v-model.lazy="query" class="input" id="filter"
                placeholder="Filter displayed content">
              <span class="icon is-left"><i class="fas fa-filter" /></span>
            </div>

            <div class="control">
              <button class="button is-danger is-light" @click="toggleFilter = !toggleFilter">
                <span class="icon"><i class="fas fa-filter" /></span>
              </button>
            </div>


            <p class="control">
              <button class="button is-purple" @click="textWrap = !textWrap" v-tooltip.bottom="'Toggle text wrap'">
                <span class="icon"><i class="fas fa-text-width"></i></span>
              </button>
            </p>
          </div>
        </div>

        <div class="is-hidden-mobile">
          <span class="subtitle">The logs are being streamed in real-time. You can scroll up to view older logs.</span>
        </div>
      </div>

      <div class="column is-12">
        <div class="logbox is-grid" ref="logContainer" @scroll.passive="handleScroll">
          <code id="logView" class="p-2 logline is-block"
            :class="{ 'is-pre-wrap': true === textWrap, 'is-pre': false === textWrap }">
            <span class="is-block m-0 notification is-info is-dark has-text-centered" v-if="reachedEnd && !query">
              <span class="notification-title">
                <span class="icon"><i class="fas fa-exclamation-triangle"/></span>
                No more logs available for this file.
              </span>
            </span>
            <span v-for="log in filteredItems" :key="log.id" class="is-block">
              <template v-if="log?.datetime">[<span class="has-tooltip" :title="log.datetime">{{ moment(log.datetime).format('HH:mm:ss') }}</span>]</template>
{{ log.line }}
</span>
<span class="is-block" v-if="filteredItems.length < 1">
  <span class="is-block m-0 notification is-warning is-dark has-text-centered" v-if="query">
    <span class="notification-title is-danger">
      <span class="icon"><i class="fas fa-filter" /></span>
      No logs match this query: <u>{{ query }}</u>
    </span>
  </span>
  <span v-else>
    <span class="has-text-danger">No logs available</span></span>
</span>
</code>
          <div ref="bottomMarker"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import moment from 'moment'
import { useStorage } from '@vueuse/core'
import type { log_line } from '~/types/logs'

let scrollTimeout: NodeJS.Timeout | null = null

const toast = useNotification()
const socket = useSocketStore()
const config = useConfigStore()
const route = useRoute()

const logContainer = useTemplateRef<HTMLDivElement>('logContainer')
const bottomMarker = useTemplateRef<HTMLDivElement>('bottomMarker')
const textWrap = useStorage<boolean>('logs_wrap', true)
const bg_enable = useStorage<boolean>('random_bg', true)
const bg_opacity = useStorage<number>('random_bg_opacity', 0.95)

const logs = ref<Array<log_line>>([])
const offset = ref<number>(0)
const loading = ref<boolean>(false)
const autoScroll = ref<boolean>(true)
const reachedEnd = ref<boolean>(false)

const query = ref<string>((() => {
  const filter = route.query.filter ?? ''
  if (!filter) {
    return ''
  }
  if (typeof filter === 'string') {
    return filter.trim()
  }
  if (Array.isArray(filter) && filter.length > 0) {
    return filter[0]?.trim() ?? ''
  }
  return ''
})())

const toggleFilter = ref(false)
watch(toggleFilter, () => {
  if (!toggleFilter.value) {
    query.value = ''
    scrollToBottom(true)
  }
});

watch(() => config.app.basic_mode, async v => {
  if (!config.isLoaded() || !v) {
    return
  }
  await navigateTo('/')
}, { immediate: true })

watch(() => config.app.file_logging, async v => {
  if (v) {
    return
  }
  await navigateTo('/')
})

const filteredItems = computed(() => {
  const raw = query.value.trim().toLowerCase()
  const contextMatch = raw.match(/context:(\d+)/)
  const context = contextMatch ? parseInt(String(contextMatch[1]), 10) : 0
  const searchTerm = raw.replace(/context:\d+/, '').trim()

  if (!searchTerm) {
    return logs.value
  }

  const result: Array<log_line> = []
  const matchedIndexes = new Set()

  logs.value.forEach((log, i) => {
    if (log.line.toLowerCase().includes(searchTerm)) {
      for (let j = Math.max(0, i - context); j <= Math.min(logs.value.length - 1, i + context); j++) {
        matchedIndexes.add(j)
      }
    }
  })

  Array.from(matchedIndexes).sort((a: any, b: any) => a - b).forEach((index: any) => {
    result.push(logs.value[index] as log_line)
  })

  return result
})

const fetchLogs = async () => {
  loading.value = true

  if (reachedEnd.value || query.value) {
    return
  }

  try {
    const req = await request(`/api/logs?offset=${offset.value}`)
    if (!req.ok) {
      toast.error('Failed to fetch logs');
      return
    }

    const response = await req.json()
    if (response.error) {
      toast.error(response.error)
      return
    }

    const lines = response.logs ?? [];

    if (lines.length) {
      logs.value.unshift(...response.logs)
    }

    if (response?.next_offset) {
      offset.value = response.next_offset
    }

    if (response?.end_is_reached) {
      reachedEnd.value = true
    }

    nextTick(() => {
      if (autoScroll.value && bottomMarker.value) {
        bottomMarker.value.scrollIntoView({ behavior: 'auto' })
      }
    })
  } catch (err) {
    console.error('Failed to fetch logs:', err)
  } finally {
    loading.value = false
  }
}

const handleScroll = () => {
  if (!logContainer.value || query.value) {
    return
  }

  const container = logContainer.value
  const nearBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - 50
  const nearTop = container.scrollTop < 50

  autoScroll.value = nearBottom

  if (nearTop && !loading.value && !scrollTimeout) {
    scrollTimeout = setTimeout(async () => {
      const previousHeight = container.scrollHeight
      await fetchLogs()
      nextTick(() => {
        const newHeight = container.scrollHeight
        container.scrollTop += newHeight - previousHeight
      })
      scrollTimeout = null
    }, 300)
  }
}

const scrollToBottom = (fast = false) => {
  autoScroll.value = true
  nextTick(() => {
    if (bottomMarker.value) {
      bottomMarker.value.scrollIntoView({ behavior: fast ? 'auto' : 'smooth' })
    }
  })
}

const log_handler = (data: log_line) => {
  logs.value.push(data)

  nextTick(() => {
    if (autoScroll.value && bottomMarker.value) {
      bottomMarker.value.scrollIntoView({ behavior: 'smooth' })
    }
  })
}

onMounted(async () => {
  await fetchLogs()
  socket.on('log_lines', log_handler)
  socket.emit('subscribe', 'log_lines')
  if (bg_enable.value) {
    document.querySelector('body')?.setAttribute("style", `opacity: 1.0`)
  }
})

onBeforeUnmount(() => {
  socket.emit('unsubscribe', 'log_lines')
  socket.off('log_lines', log_handler)
  if (bg_enable.value) {
    document.querySelector('body')?.setAttribute("style", `opacity: ${bg_opacity.value}`)
  }
})

onBeforeUnmount(() => {
  socket.emit('unsubscribe', 'log_lines')
  socket.off('log_lines', log_handler)
  if (scrollTimeout) clearTimeout(scrollTimeout)

})

useHead({ title: 'Logs' })
</script>
