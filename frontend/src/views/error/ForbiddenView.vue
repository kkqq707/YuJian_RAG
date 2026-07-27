<template>
  <div class="error-page">
    <div class="error-content">
      <div class="error-code">403</div>
      <h2 class="error-title">无权限访问</h2>
      <p class="error-desc">抱歉，您没有权限访问此页面</p>
      <div class="error-actions">
        <el-button @click="$router.back()">返回上一页</el-button>
        <el-button type="primary" @click="$router.push('/')">返回首页</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
</script>

<style lang="scss" scoped>
.error-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: $color-page-bg;
}

.error-content {
  text-align: center;
}

.error-code {
  font-size: 80px;
  font-weight: 700;
  color: $color-primary;
  line-height: 1;
  margin-bottom: $spacing-md;
}

.error-title {
  font-size: $font-size-2xl;
  font-weight: 600;
  color: $color-text-primary;
  margin-bottom: $spacing-sm;
}

.error-desc {
  font-size: $font-size-base;
  color: $color-text-secondary;
  margin-bottom: $spacing-xl;
}

.error-actions {
  display: flex;
  justify-content: center;
  gap: $spacing-sm;
}
</style>
