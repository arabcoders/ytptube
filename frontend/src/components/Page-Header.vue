<template>
  <nav class="navbar is-mobile is-dark">
    <div class="navbar-brand pl-5">
      <a class="navbar-item" href="#">
        <b>YTPTube</b>
      </a>
    </div>

    <div class="navbar-end">
      <div class="navbar-item">
        <button class="button is-dark has-tooltip-bottom" :data-tooltip="config.isConnected ? 'Connected' : 'Connecting'">
          <span class="icon-text" :class="config.isConnected ? 'has-text-success' : 'has-text-danger'">
            <span class="icon">
              <font-awesome-icon :icon="config.isConnected ? 'fa-solid fa-wifi' : 'fa-solid fa-signal'" />
            </span>
          </span>
        </button>
      </div>
      <div class="navbar-item">
        <button data-tooltip="Show/Hide Add Form" class="button is-dark has-tooltip-bottom" @click="$emit('toggleForm')">
          <font-awesome-icon icon="fa-solid fa-plus" />
        </button>
      </div>
      <div class="navbar-item">
        <button data-tooltip="Switch to Light theme" class="button is-dark has-tooltip-bottom"
          @click="selectedTheme = 'light'" v-if="selectedTheme == 'dark'">🌞</button>
        <button data-tooltip="Switch to Dark theme" class="button is-dark  has-tooltip-bottom"
          @click="selectedTheme = 'dark'" v-if="selectedTheme == 'light'">🌚</button>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { defineProps, defineEmits, watch, onMounted } from 'vue'
import { useStorage } from '@vueuse/core'

const selectedTheme = useStorage('theme', (() => window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')());

defineEmits(['toggleForm'])

defineProps({
  config: {
    type: Object,
    required: true
  }
})

const applyPreferredColorScheme = (scheme) => {
  for (var s = 0; s < document.styleSheets.length; s++) {
    for (var i = 0; i < document.styleSheets[s].cssRules.length; i++) {
      const rule = document.styleSheets[s].cssRules[i];

      if (rule && rule.media && rule.media.mediaText.includes("prefers-color-scheme")) {
        switch (scheme) {
          case "light":
            rule.media.appendMedium("original-prefers-color-scheme");
            if (rule.media.mediaText.includes("light")) {
              rule.media.deleteMedium("(prefers-color-scheme: light)");
            }
            if (rule.media.mediaText.includes("dark")) {
              rule.media.deleteMedium("(prefers-color-scheme: dark)");
            }
            break;
          case "dark":
            rule.media.appendMedium("(prefers-color-scheme: light)");
            rule.media.appendMedium("(prefers-color-scheme: dark)");
            if (rule.media.mediaText.includes("original")) {
              rule.media.deleteMedium("original-prefers-color-scheme");
            }
            break;
          default:
            rule.media.appendMedium("(prefers-color-scheme: dark)");
            if (rule.media.mediaText.includes("light")) {
              rule.media.deleteMedium("(prefers-color-scheme: light)");
            }
            if (rule.media.mediaText.includes("original")) {
              rule.media.deleteMedium("original-prefers-color-scheme");
            }
            break;
        }
      }
    }
  }
}

onMounted(() => {
  try {
    applyPreferredColorScheme(selectedTheme.value);
  } catch (e) {
    console.debug(e);
  }
})

watch(selectedTheme, (value) => {
  try {
    applyPreferredColorScheme(value);
  } catch (e) {
    console.debug(e);
  }
})

</script>

<style scoped>
.navbar-item {
  display: flex;
}

.navbar,
.navbar-menu,
.navbar-start,
.navbar-end {
  align-items: stretch;
  display: flex;
  padding: 0;
}
.navbar-menu {
  flex-grow: 1;
  flex-shrink: 0;
}

.navbar-start {
  justify-content: flex-start;
  margin-right: auto;
}

.navbar-end {
  justify-content: flex-end;
  margin-left: auto;
}
</style>
