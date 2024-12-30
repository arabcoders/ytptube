<template>
  <div>
    <Queue />
    <History />
  </div>
</template>

<script setup>
const config = useConfigStore()
const stateStore = useStateStore()

onMounted(() => {
  if (!config.app.ui_update_title) {
    useHead({ title: 'YTPTube' })
    return
  }
  useHead({ title: `YTPTube: ( ${Object.keys(stateStore.queue).length || 0} | ${Object.keys(stateStore.history).length || 0} )` })
})

watch([stateStore.queue, stateStore.history], () => {
  if (!config.app.ui_update_title) {
    return
  }
  console.log('logging watch event')
  useHead({ title: `YTPTube: ( ${Object.keys(stateStore.queue).length || 0} | ${Object.keys(stateStore.history).length || 0} )` })
}, { deep: true })

</script>
