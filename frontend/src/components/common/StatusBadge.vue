<template>
  <span class="status-badge" :class="statusClass">
    <span class="status-dot" />
    <span class="status-label">{{ label }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  status: string
  label?: string
}>(), {
  label: '',
})

const statusClass = computed(() => {
  const s = props.status.toLowerCase()
  if (s === 'ok' || s === 'active' || s === 'online' || s === 'indexed') return 'status-ok'
  if (s === 'error' || s === 'failed' || s === 'offline') return 'status-error'
  if (s === 'warning' || s === 'degraded' || s === 'pending') return 'status-warning'
  if (s === 'processing') return 'status-processing'
  return 'status-default'
})

const statusLabel = computed(() => {
  return props.label || props.status
})
</script>

<style lang="scss" scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: $font-size-sm;
  font-weight: 500;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.status-label {
  white-space: nowrap;
}

.status-ok {
  background: #f0fdf4;
  color: $color-success;
  .status-dot { background: $color-success; }
}

.status-error {
  background: #fef2f2;
  color: $color-danger;
  .status-dot { background: $color-danger; }
}

.status-warning {
  background: #fffbeb;
  color: $color-warning;
  .status-dot { background: $color-warning; }
}

.status-processing {
  background: $color-primary-light;
  color: $color-primary;
  .status-dot {
    background: $color-primary;
    animation: pulse 1.5s infinite;
  }
}

.status-default {
  background: #f1f5f9;
  color: $color-text-tertiary;
  .status-dot { background: $color-text-tertiary; }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
