<template>
  <Message message_class="is-success has-background-success-90 has-text-dark">
    <span class="icon"><i class="fas fa-info-circle" /></span>
    <span>
      A New WebUI Version installed, please
      <NuxtLink class="is-bold" @click="reloadPage">click here</NuxtLink>
      to reload the app.
    </span>
  </Message>
</template>

<script setup lang="ts">
import Message from "~/components/Message.vue";

const reloadPage = () => window.location.reload();
</script>
