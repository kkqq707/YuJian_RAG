<template>
  <div class="statistic-card">
    <div class="stat-icon" :class="iconClass">
      <component :is="icon" :size="22" />
    </div>
    <div class="stat-body">
      <div class="stat-value">
        <span v-if="loading" class="skeleton skeleton-value" />
        <span v-else>{{ formattedValue }}</span>
      </div>
      <div class="stat-label">{{ label }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Component } from 'vue'

const props = withDefaults(defineProps<{
  label: string
  value: number | string | null
  icon: Component
  iconClass?: string
  loading?: boolean
}>(), {
  value: 0,
  iconClass: 'default',
  loading: false,
})

const formattedValue = computed(() => {
  if (props.value === null || props.value === undefined) return '--'
  if (typeof props.value === 'number') {
    return props.value.toLocaleString('zh-CN')
  }
  return props.value
})
</script>

<style lang="scss" scoped>
.statistic-card {
  background: $color-card-bg;
  border-radius: $card-radius;
  box-shadow: $shadow-card;
  padding: $spacing-lg;
  display: flex;
  align-items: flex-start;
  gap: $spacing-md;
  transition: box-shadow $transition-fast;

  &:hover {
    box-shadow: 0 2px 8px rgba(16, 24, 40, 0.1);
  }
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: $control-radius;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  &.default { background: $color-primary-light; color: $color-primary; }
  &.success { background: #f0fdf4; color: $color-success; }
  &.warning { background: #fffbeb; color: $color-warning; }
  &.danger { background: #fef2f2; color: $color-danger; }
}

.stat-body {
  flex: 1;
  min-width: 0;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: $color-text-primary;
  line-height: 1.2;
}

.stat-label {
  font-size: $font-size-sm;
  color: $color-text-secondary;
  margin-top: 4px;
}

.skeleton-value {
  display: inline-block;
  width: 64px;
  height: 28px;
  vertical-align: middle;
}
</style>
