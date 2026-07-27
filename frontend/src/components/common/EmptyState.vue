<template>
  <div class="empty-state">
    <div class="empty-icon">
      <component :is="iconComponent" :size="48" />
    </div>
    <h3 class="empty-title">{{ title }}</h3>
    <p v-if="description" class="empty-description">{{ description }}</p>
    <div v-if="$slots.default" class="empty-action">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { FolderOpen, Inbox, SearchX } from '@lucide/vue'

const props = withDefaults(defineProps<{
  title?: string
  description?: string
  type?: 'default' | 'search' | 'folder'
}>(), {
  title: '暂无数据',
  description: '',
  type: 'default',
})

const iconComponent = computed(() => {
  switch (props.type) {
    case 'search': return SearchX
    case 'folder': return FolderOpen
    default: return Inbox
  }
})
</script>

<style lang="scss" scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: $spacing-lg * 2 $spacing-lg;
  text-align: center;
}

.empty-icon {
  color: $color-text-tertiary;
  margin-bottom: $spacing-md;
  opacity: 0.5;
}

.empty-title {
  font-size: $font-size-base;
  font-weight: 500;
  color: $color-text-secondary;
  margin-bottom: $spacing-xs;
}

.empty-description {
  font-size: $font-size-sm;
  color: $color-text-tertiary;
  max-width: 320px;
  line-height: 1.5;
}

.empty-action {
  margin-top: $spacing-md;
}
</style>
