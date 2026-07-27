<template>
  <div class="audit-logs-page">
    <PageHeader title="审计日志" description="查看管理员操作记录和系统审计日志" />
    <div class="app-card">
      <EmptyState title="审计日志" description="审计日志查看和筛选功能将在下一阶段完善" type="default" />
    </div>
  </div>
</template>

<script setup lang="ts">
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
</script>

<style lang="scss" scoped>
.audit-logs-page {
  max-width: 1440px;
}
</style>
