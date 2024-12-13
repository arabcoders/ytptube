<template>
  <NuxtLayout name="error-layout">
    <div>
      <div class="columns is-multiline">
        <div class="column is-12">
          <h1 class="title is-4">
            {{ error.statusCode }}<span v-if="error.statusMessage"> - {{ error.statusMessage }}</span>
          </h1>
        </div>
      </div>
      <div class="column is-12" v-if="error.message">
        <div class="notification has-background-warning-90 has-text-dark">
          <p>{{ error.message }}</p>
        </div>
      </div>

      <div class="column is-12" v-if="error.stack">
        <h2 class="title is-5 is-clickable" @click="showStacks = !showStacks">
          <span class="icon-text">
            <span class="icon">
              <i v-if="showStacks" class="fas fa-arrow-up"></i>
              <i v-else class="fas fa-arrow-down"></i>
            </span>
            <span>Stack trace</span>
          </span>
        </h2>

        <pre v-if="showStacks"><code>{{ error.stack }}</code></pre>
      </div>

      <div class="column is-12">
        <h2 class="title is-5">
          <NuxtLink to="/">
            <span class="icon-text">
              <span class="icon"><i class="fas fa-home"></i></span>
              <span>Back to Home</span>
            </span>
          </NuxtLink>
        </h2>
      </div>
    </div>
  </NuxtLayout>
</template>

<script setup>
defineProps({
  error: {
    type: Object,
    required: true
  }
})

const showStacks = ref(false)
</script>
