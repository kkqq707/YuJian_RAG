<template>
  <div class="loading-block">
    <!-- 骨架屏 -->
    <div v-if="variant === 'skeleton'" class="skeleton-group">
      <div
        v-for="i in lines"
        :key="i"
        class="skeleton-line"
        :style="{ width: skeletonWidths[(i - 1) % skeletonWidths.length] }"
      />
    </div>
    <!-- 加载 Spinner -->
    <div v-else class="loading-spinner">
      <el-icon class="is-loading" :size="size === 'large' ? 32 : 24">
        <Loading />
      </el-icon>
      <span v-if="text" class="loading-text">{{ text }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Loading } from '@element-plus/icons-vue'

withDefaults(defineProps<{
  variant?: 'skeleton' | 'spinner'
  size?: 'default' | 'large'
  text?: string
  lines?: number
}>(), {
  variant: 'skeleton',
  size: 'default',
  text: '',
  lines: 4,
})

const skeletonWidths = ['100%', '75%', '60%', '85%']
</script>

<style lang="scss" scoped>
.loading-block {
  width: 100%;
}

// ---- 骨架屏 ----
.skeleton-group {
  display: flex;
  flex-direction: column;
  gap: $spacing-sm;
}

.skeleton-line {
  height: 16px;
  border-radius: 4px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s infinite;
}

@keyframes skeleton-loading {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

// ---- Spinner ----
.loading-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: $spacing-lg * 2;
  gap: $spacing-sm;
}

.loading-text {
  font-size: $font-size-sm;
  color: $color-text-tertiary;
}
</style>
