<template>
  <div class="app-logo" :class="{ collapsed }">
    <div class="logo-icon">
      <BookOpen :size="collapsed ? 24 : 28" />
    </div>
    <span v-if="!collapsed" class="logo-text">{{ title }}</span>
  </div>
</template>

<script setup lang="ts">
import { BookOpen } from '@lucide/vue'

withDefaults(defineProps<{
  collapsed?: boolean
  title?: string
}>(), {
  collapsed: false,
  title: '企业智库 AI',
})
</script>

<style lang="scss" scoped>
.app-logo {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  overflow: hidden;
}

.logo-icon {
  color: $color-primary;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.logo-text {
  font-size: $font-size-lg;
  font-weight: 600;
  color: $color-text-primary;
  white-space: nowrap;
}
</style>
