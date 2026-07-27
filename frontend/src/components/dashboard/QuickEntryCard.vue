<template>
  <div class="quick-entry-card" @click="$emit('click')">
    <div class="entry-icon" :class="iconClass">
      <component :is="icon" :size="20" />
    </div>
    <div class="entry-body">
      <div class="entry-title">{{ title }}</div>
      <div class="entry-desc">{{ description }}</div>
    </div>
    <el-icon class="entry-arrow"><ArrowRight /></el-icon>
  </div>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
import { ArrowRight } from '@element-plus/icons-vue'

defineProps<{
  title: string
  description: string
  icon: Component
  iconClass?: string
}>()

defineEmits<{
  click: []
}>()
</script>

<style lang="scss" scoped>
.quick-entry-card {
  background: $color-card-bg;
  border-radius: $card-radius;
  box-shadow: $shadow-card;
  padding: $spacing-md $spacing-lg;
  display: flex;
  align-items: center;
  gap: $spacing-md;
  cursor: pointer;
  transition: all $transition-fast;

  &:hover {
    box-shadow: 0 2px 8px rgba(16, 24, 40, 0.1);
    transform: translateY(-1px);
  }
}

.entry-icon {
  width: 40px;
  height: 40px;
  border-radius: $control-radius;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: $color-primary-light;
  color: $color-primary;

  &.success { background: #f0fdf4; color: $color-success; }
  &.warning { background: #fffbeb; color: $color-warning; }
  &.danger { background: #fef2f2; color: $color-danger; }
}

.entry-body {
  flex: 1;
}

.entry-title {
  font-size: $font-size-base;
  font-weight: 500;
  color: $color-text-primary;
}

.entry-desc {
  font-size: $font-size-xs;
  color: $color-text-tertiary;
  margin-top: 2px;
}

.entry-arrow {
  color: $color-text-tertiary;
  font-size: $font-size-sm;
}
</style>
