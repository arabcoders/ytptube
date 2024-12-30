<template>
  <div>
    <Queue />
    <History />
  </div>
</template>

<script setup>
const config = useConfigStore()
const stateStore = useStateStore()
const maxWorkers = config.app.max_workers

onMounted(() => {
  if (!config.app.ui_update_title) {
    useHead({ title: 'YTPTube' })
    return
  }
  useHead({ title: `YTPTube: ( ${Object.keys(stateStore.queue).length || 0}/${maxWorkers} | ${Object.keys(stateStore.history).length || 0} )` })
})

watch(() => stateStore.history, () => {
  if (!config.app.ui_update_title) {
    return
  }
  useHead({ title: `YTPTube: ( ${Object.keys(stateStore.queue).length || 0}/${maxWorkers}  | ${Object.keys(stateStore.history).length || 0} )` })
}, { deep: true })

watch(() => stateStore.queue, () => {
  if (!config.app.ui_update_title) {
    return
  }
  useHead({ title: `YTPTube: ( ${Object.keys(stateStore.queue).length || 0}/${maxWorkers}  | ${Object.keys(stateStore.history).length || 0} )` })
}, { deep: true })

</script>
