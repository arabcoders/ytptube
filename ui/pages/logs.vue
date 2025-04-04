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
  background-color: #333;
  box-shadow: 0 4px 8px 0 rgba(0, 0, 0, 0.2), 0 6px 20px 0 rgba(0, 0, 0, 0.19);
  min-width: 100%;
  max-height: 73vh;
  overflow-y: scroll;
  overflow-x: auto;
}

div.logbox pre {
  background-color: rgb(31, 34, 41);
}

.logline {
  word-break: break-all;
  line-height: 2.3em;
  padding: 1em;
  color: #fff1b8;
}
</style>

<template>
  <div>
    <div class="mt-1 columns is-multiline">
      <div class="column is-12 is-clearfix is-unselectable">
        <span class="title is-4">
          <span class="icon"><i class="fas fa-file-lines" :class="{ 'fa-spin': loading }" /></span>
          Logs
        </span>
        <div class="is-pulled-right">
          <div class="field is-grouped">
            <div class="control">
              <button v-if="!autoScroll" @click="scrollToBottom" class="button is-primary">
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
          <span class="subtitle">The logs are displayed in real-time. You can scroll up to view older logs.</span>
        </div>
      </div>
    </div>

    <div class="column is-12">
      <div class="logbox is-grid" ref="logContainer" @scroll.passive="handleScroll">
        <pre class="p-1 m-1"><code id="logView" class="p-0 logline is-block"
                               :class="{ 'is-pre-wrap': true === textWrap, 'is-pre': false === textWrap }"><span
        v-for="log in filteredItems" :key="log.id" class="is-block"><template
        v-if="log?.datetime">[<span class="has-tooltip" :title="log.datetime">{{ moment(log.datetime).format('HH:mm:ss') }}</span>]&nbsp;</template>{{
          log.line }}</span><span class="is-block" v-if="filteredItems.length < 1"><span v-if="query"><span
      class="has-text-danger">No logs found for the filter: </span><span class="has-text-info">{{ query
      }}</span></span><span v-else><span class="has-text-danger">No logs available</span></span>
</span></code></pre>
        <div ref="bottomMarker"></div>
      </div>
    </div>
  </div>
</template>
<script setup>
import moment from 'moment'
import { request } from '~/utils/index'
import { ref, onMounted, nextTick } from 'vue'

let scrollTimeout = null

const toast = useToast()
const socket = useSocketStore()
const config = useConfigStore()

const logs = ref([])
const offset = ref(0)
const limit = 50
const maxLogLimit = 1000
const loading = ref(false)
const logContainer = ref(null)
const bottomMarker = ref(null)
const autoScroll = ref(true)
const textWrap = ref(true)

const query = ref(useRoute().query.filter ?? '')
const toggleFilter = ref(false)
watch(toggleFilter, () => {
  if (!toggleFilter.value) {
    query.value = ''
  }
});

watch(() => config.app.basic_mode, async v => {
  if (!v) {
    return
  }
  await navigateTo('/')
})

watch(() => config.app.file_logging, async v => {
  if (v) {
    return
  }
  await navigateTo('/')
})

const filteredItems = computed(() => {
  const raw = query.value.trim().toLowerCase()
  const contextMatch = raw.match(/context:(\d+)/)
  const context = contextMatch ? parseInt(contextMatch[1], 10) : 0
  const searchTerm = raw.replace(/context:\d+/, '').trim()

  if (!searchTerm) return logs.value

  const result = []
  const matchedIndexes = new Set()

  logs.value.forEach((log, i) => {
    if (log.line.toLowerCase().includes(searchTerm)) {
      for (let j = Math.max(0, i - context); j <= Math.min(logs.value.length - 1, i + context); j++) {
        matchedIndexes.add(j)
      }
    }
  })

  Array.from(matchedIndexes).sort((a, b) => a - b).forEach(index => {
    result.push(logs.value[index])
  })

  return result
})

const fetchLogs = async () => {
  if (logs.value.length >= maxLogLimit) {
    return
  }

  loading.value = true

  try {
    const req = await request(`/api/logs?offset=${offset.value}&limit=${limit}`)
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
      offset.value += lines.length;
      if (logs.value.length > maxLogLimit) {
        logs.value.splice(0, logs.value.length - maxLogLimit)
      }
    }

    // Auto-scroll only if the user was already at the bottom
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

const scrollToBottom = () => {
  autoScroll.value = true
  nextTick(() => {
    if (bottomMarker.value) {
      bottomMarker.value.scrollIntoView({ behavior: 'smooth' })
    }
  })
}

onMounted(async () => {
  await fetchLogs()
  socket.emit('subscribe', 'log_lines')
  window.socket = socket

  socket.on('log_lines', data => {
    if (logs.value.length >= maxLogLimit) {
      logs.value.shift()
    }

    logs.value.push(data)

    nextTick(() => {
      if (autoScroll.value && bottomMarker.value) {
        bottomMarker.value.scrollIntoView({ behavior: 'smooth' })
      }
    })

  })
})

onUnmounted(() => {
  socket.emit('unsubscribe', 'log_lines')
  socket.off('log_lines')
})

onBeforeUnmount(() => {
  socket.emit('unsubscribe', 'log_lines')
  socket.off('log_lines')
  if (scrollTimeout) clearTimeout(scrollTimeout)
})

useHead({ title: 'Logs' })
</script>
