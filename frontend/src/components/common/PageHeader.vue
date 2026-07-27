<template>
  <div class="page-header">
    <div class="page-header-left">
      <h1 class="page-title">{{ title }}</h1>
      <p v-if="description" class="page-description">{{ description }}</p>
    </div>
    <div v-if="$slots.extra" class="page-header-extra">
      <slot name="extra" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>

<style lang="scss" scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: $spacing-lg;
}

.page-title {
  font-size: $font-size-xl;
  font-weight: 600;
  color: $color-text-primary;
  line-height: 1.4;
}

.page-description {
  font-size: $font-size-sm;
  color: $color-text-secondary;
  margin-top: 4px;
}

.page-header-extra {
  flex-shrink: 0;
}
</style>
