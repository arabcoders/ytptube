<template>
  <nav class="navbar is-dark">
    <div class="navbar-brand pl-5">
      <a class="navbar-item" href="#">
        <b>YTPTube</b>
      </a>
    </div>

    <div class="navbar-end">
      <div class="navbar-item">
        <span class="icon-text" :class="config.isConnected ? 'has-text-success' : 'has-text-danger'">
          <span class="icon">
            <i v-if="config.isConnected" class="fa-solid fa-wifi"></i>
            <i v-else class="fa-solid fa-signal"></i>
          </span>
          <span>
            {{ config.isConnected ? 'Connected' : 'Connecting' }}
          </span>
        </span>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { defineProps } from 'vue'

defineProps({
  config: {
    type: Object,
    required: true
  }
})
</script>
