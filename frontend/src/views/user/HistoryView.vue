<template>
  <div class="history-view">
    <div class="chat-header">
      <h2 class="chat-title">历史记录</h2>
      <p class="chat-desc">查看您的问答历史</p>
    </div>
    <div class="app-card">
      <EmptyState title="暂无历史记录" description="您的问答历史将在这里展示" type="default" />
    </div>
  </div>
</template>

<script setup lang="ts">
import EmptyState from '@/components/common/EmptyState.vue'
</script>

<style lang="scss" scoped>
.history-view {
  max-width: 900px;
  margin: 0 auto;
  padding: $page-padding;
}

.chat-header {
  text-align: center;
  padding: $spacing-xl 0 $spacing-lg;
}

.chat-title {
  font-size: $font-size-2xl;
  font-weight: 600;
  color: $color-text-primary;
  margin-bottom: $spacing-xs;
}

.chat-desc {
  font-size: $font-size-sm;
  color: $color-text-secondary;
}
</style>
