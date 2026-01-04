<template></template>

<script lang="ts" setup>
import { useStorage } from '@vueuse/core'
const simpleMode = useStorage<boolean>('simple_mode', true)

onMounted(async () => {
  simpleMode.value = true
  await nextTick()
  await navigateTo('/')
})
</script>
