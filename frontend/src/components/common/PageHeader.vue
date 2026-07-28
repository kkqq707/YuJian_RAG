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
  gap: $spacing-md;

  // 移动端：纵向排列
  @media (max-width: 767px) {
    flex-direction: column;
    align-items: stretch;
  }
}

.page-header-left {
  min-width: 0;
}

.page-title {
  font-size: $font-size-xl;
  font-weight: 600;
  color: $color-text-primary;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;

  @media (max-width: 767px) {
    font-size: $font-size-lg;
  }
}

.page-description {
  font-size: $font-size-sm;
  color: $color-text-secondary;
  margin-top: 4px;
  word-break: break-word;
}

.page-header-extra {
  flex-shrink: 0;

  // 移动端：操作按钮全宽
  @media (max-width: 767px) {
    display: flex;
    flex-wrap: wrap;
    gap: $spacing-sm;

    :deep(.el-button) {
      min-height: var(--touch-target-min);

      &:first-child {
        flex: 1;
      }
    }
  }
}
</style>
