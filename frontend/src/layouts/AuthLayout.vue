<template>
  <div class="auth-layout">
    <router-view />
  </div>
</template>

<script setup lang="ts">
</script>

<style lang="scss" scoped>
.auth-layout {
  min-height: var(--app-height);
  height: auto;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
