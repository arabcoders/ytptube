<template>
  <div class="columns is-multiline mt-3">
    <div class="column has-text-left">
      {{Year}} © YTPtube
    </div>
    <div class="column has-text-right">
      <a href="https://github.com/ArabCoders/ytptube" target="_blank">
        Github
      </a>
    </div>
  </div>
</template>

<script setup>
const Year = new Date().getFullYear()
</script>
