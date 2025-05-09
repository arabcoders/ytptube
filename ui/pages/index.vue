<template>
  <div>
    <div class="mt-1 columns is-multiline">
      <div class="column is-12 is-clearfix is-unselectable">
        <span class="title is-4">
          <span class="icon-text">
            <span class="icon"><i class="fa-solid fa-download" /></span>
            <span>Downloads</span>
          </span>
        </span>

        <div class="is-pulled-right" v-if="socket.isConnected && false === config.app.basic_mode">
          <div class="field is-grouped">
            <p class="control" v-if="config.app.has_cookies">
              <button class="button is-purple" @click="checkCookies" v-tooltip.bottom="'Check youtube cookies status.'"
                :disabled="isChecking">
                <span class="icon"><i class="fas fa-cookie" :class="{ 'is-loading': isChecking }" /></span>
              </button>
            </p>

            <p class="control">
              <button class="button is-warning" @click="pauseDownload" v-if="false === config.paused"
                v-tooltip.bottom="'Pause non-active downloads.'">
                <span class="icon"><i class="fas fa-pause" /></span>
              </button>
              <button class="button is-danger" @click="socket.emit('resume', {})" v-else
                v-tooltip.bottom="'Resume downloading.'">
                <span class="icon"><i class="fas fa-play" /></span>
              </button>
            </p>

            <p class="control" v-if="!config.app.basic_mode">
              <button v-tooltip.bottom="'Toggle new download form'" class="button is-primary has-tooltip-bottom"
                @click="config.showForm = !config.showForm">
                <span class="icon"><i class="fa-solid fa-plus" /></span>
              </button>
            </p>

            <p class="control">
              <button v-tooltip.bottom="'Change display style'" class="button has-tooltip-bottom"
                @click="() => changeDisplay()">
                <span class="icon"><i class="fa-solid"
                    :class="{ 'fa-table': display_style === 'cards', 'fa-table-list': display_style === 'list' }" /></span>
              </button>
            </p>

          </div>
        </div>
        <div class="is-hidden-mobile">
          <span class="subtitle">
            Queued and completed downloads are displayed here.
          </span>
        </div>
      </div>
    </div>

    <NewDownload v-if="config.showForm || config.app.basic_mode" @getInfo="url => get_info = url" :item="item_form"
      @clear_form="item_form = {}" />
    <Queue @getInfo="url => get_info = url" />
    <History @getInfo="url => get_info = url" @add_new="item => toNewDownload(item)" />
    <GetInfo v-if="get_info" :link="get_info" @closeModel="get_info = ''" />
  </div>
</template>

<script setup>
import { request } from '~/utils/index'
import { useStorage } from '@vueuse/core'

const emitter = defineEmits(['getInfo'])
const config = useConfigStore()
const stateStore = useStateStore()
const socket = useSocketStore()
const toast = useToast()
const isChecking = ref(false)
const get_info = ref('')
const bg_enable = useStorage('random_bg', true)
const bg_opacity = useStorage('random_bg_opacity', 0.85)
const display_style = useStorage('display_style', 'cards')
const item_form = ref({})

onMounted(() => {
  if (!config.app.ui_update_title) {
    useHead({ title: 'YTPTube' })
    return
  }
  useHead({ title: `YTPTube: ( ${Object.keys(stateStore.queue).length || 0}/${config.app.max_workers} | ${Object.keys(stateStore.history).length || 0} )` })
})

watch(() => stateStore.history, () => {
  if (!config.app.ui_update_title) {
    return
  }
  useHead({ title: `YTPTube: ( ${Object.keys(stateStore.queue).length || 0}/${config.app.max_workers}  | ${Object.keys(stateStore.history).length || 0} )` })
}, { deep: true })

watch(() => stateStore.queue, () => {
  if (!config.app.ui_update_title) {
    return
  }
  useHead({ title: `YTPTube: ( ${Object.keys(stateStore.queue).length || 0}/${config.app.max_workers}  | ${Object.keys(stateStore.history).length || 0} )` })
}, { deep: true })

const checkCookies = async () => {
  if (true === isChecking.value) {
    return
  }

  if (false === confirm(`Check for cookies status?`)) {
    return
  }

  try {
    isChecking.value = true
    const response = await request('/api/youtube/auth')
    const data = await response.json()
    if (response.ok) {
      toast.success('Succuss. ' + data.message)
    } else {
      toast.error('Failed. ' + data.message)
    }
  } catch (e) {
    toast.error('Failed to check cookies state. ' + e.message)
  } finally {
    isChecking.value = false
  }
}

const pauseDownload = () => {
  if (false === confirm('Are you sure you want to pause all non-active downloads?')) {
    return false
  }

  socket.emit('pause', {})
}

watch(get_info, v => {
  if (!bg_enable.value) {
    return
  }

  document.querySelector('body').setAttribute("style", `opacity: ${v ? 1 : bg_opacity.value}`)
})

const changeDisplay = () => display_style.value = display_style.value === 'cards' ? 'list' : 'cards'

const toNewDownload = async (item) => {
  if (!item) {
    return
  }

  if (config.showForm) {
    config.showForm = false
    await nextTick()
  }

  item_form.value = item

  await nextTick()
  config.showForm = true
}
</script>
