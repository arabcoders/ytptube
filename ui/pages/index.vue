<template>
  <div>
    <NewDownload v-if="config.showForm" />
    <Queue />
    <History />
  </div>
</template>

<script setup>
const bus = useEventBus('item_added', 'show_form', 'task_edit')
const config = useConfigStore()
const socket = useSocketStore()

bus.on((event, data) => {
  console.log({ e: event, d: data })

  if (!['show_form'].includes(event)) {
    return true;
  }

  if ('show_form' === event) {
    addForm.value = true;
    setTimeout(() => bus.emit('task_edit', data), 500);
  }
})

useHead({ title: 'Index' })
</script>
