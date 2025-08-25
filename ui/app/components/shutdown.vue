<template>
  <div id="main_container" class="container">
    <div class="columns">
      <div class="column">
        <section
          class="hero has-text-centered is-flex is-align-items-center is-justify-content-center">
          <div class="goodbye-box">
            <div class="goodbye-title">Goodbye!</div>
            <p class="goodbye-subtitle">YTPTube has shut down.</p>
            <p class="goodbye-hint">You may now close this window.</p>
            <div class="goodbye-spinner" />
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.goodbye-box {
  animation: fadeInUp 0.6s ease-out;
  background: radial-gradient(circle at top left, #6f42c1, #f66d9b);
  color: white;
  padding: 3rem 4rem;
  border-radius: 1rem;
  box-shadow: 0 0 50px rgba(255, 255, 255, 0.15);
  max-width: 480px;
  margin: 2rem auto;
  position: relative;
  overflow: hidden;
  transform-style: preserve-3d;
}

.goodbye-title {
  font-size: 3rem;
  font-weight: bold;
  margin-bottom: 1rem;
  animation: floatTitle 3s ease-in-out infinite;
}

.goodbye-subtitle {
  font-size: 1.5rem;
  margin-bottom: 0.75rem;
  opacity: 0.95;
}

.goodbye-hint {
  opacity: 0.75;
  font-size: 1rem;
  margin-bottom: 1rem;
}

.goodbye-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(255, 255, 255, 0.3);
  border-top: 3px solid white;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 1rem auto 0;
}

@keyframes fadeInUp {
  from {
    transform: translateY(40px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

@keyframes floatTitle {
  0%, 100% {
    transform: translateY(0px);
  }
  50% {
    transform: translateY(-8px);
  }
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}
</style>
