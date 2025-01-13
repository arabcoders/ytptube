<template>
  <div>
    <Queue @getInfo="url => emitter('getInfo', url)" />
    <History @getInfo="url => emitter('getInfo', url)" />
  </div>
</template>

<script setup>
const emitter = defineEmits(['getInfo'])
const config = useConfigStore()
const stateStore = useStateStore()

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

</script>
