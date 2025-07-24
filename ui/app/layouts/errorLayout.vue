<template>
  <div class="container">
    <nav class="navbar is-dark mb-5">
      <div class="navbar-brand pl-5">
        <NuxtLink class="navbar-item" to="/">
          <span class="icon-text">
            <span class="icon"><i class="fas fa-home"></i></span>
            <span>Home</span>
          </span>
        </NuxtLink>
      </div>
    </nav>
    <slot />
  </div>
</template>

<script setup>
import 'assets/css/bulma.css'
import 'assets/css/style.css'
import 'assets/css/all.css'
</script>
