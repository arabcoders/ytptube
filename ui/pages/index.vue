<template>
  <div>
    <Queue />
    <History />
  </div>
</template>

<script setup>
const config = useConfigStore()
useHead({ title: 'YTPTube' })

watch(() => config.app.ui_update_title, value => {
  if (true !== value) {
    return
  }

  const s = useStateStore()
  useHead({ title: `YTPTube: ( ${Object.keys(s.queue).length || 0} | ${Object.keys(s.history).length || 0} )` })
  watch([s.queue, s.history], () => {
    const title = `YTPTube: ( ${Object.keys(s.queue).length || 0} | ${Object.keys(s.history).length || 0} )`
    useHead({ title })
  })

}, { immediate: true })
</script>
