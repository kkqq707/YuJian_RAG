<template>
  <div class="welcome-panel">
    <div class="welcome-icon">
      <Sparkles :size="isMobile ? 36 : 48" />
    </div>
    <h1 class="welcome-title">{{ title || '您好，我是企业智库 AI 助手' }}</h1>
    <p class="welcome-desc">
      {{ description || '我可以基于企业内部资料，为您解答业务、产品、制度和服务相关问题。' }}
    </p>
    <div class="welcome-suggestions">
      <button
        v-for="item in suggestions"
        :key="item"
        class="suggestion-card touch-target-min"
        :disabled="sending"
        :aria-label="`推荐问题：${item}`"
        @click="$emit('select', item)"
      >
        {{ item }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Sparkles } from '@lucide/vue'

defineProps<{
  sending?: boolean
  isMobile?: boolean
  title?: string
  description?: string
}>()

defineEmits<{
  select: [question: string]
}>()

const suggestions = [
  '公司介绍：煜见科技是做什么的？',
  '产品信息：煜见科技有哪些产品？',
  '服务流程：公司提供什么样的服务？',
  '合作政策：如何与公司合作？',
]
</script>

<style lang="scss" scoped>
.welcome-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: $spacing-2xl $spacing-lg;
  text-align: center;
  min-height: 0;
  animation: fadeInUp 0.5s ease;
}

.welcome-icon {
  width: 80px;
  height: 80px;
  border-radius: 20px;
  background: $color-primary-light;
  color: $color-primary;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: $spacing-lg;
  flex-shrink: 0;
}

.welcome-title {
  font-size: $font-size-2xl;
  font-weight: 600;
  color: $color-text-primary;
  margin: 0 0 $spacing-sm;
  line-height: 1.4;
}

.welcome-desc {
  font-size: $font-size-base;
  color: $color-text-secondary;
  max-width: 420px;
  line-height: 1.6;
  margin: 0 0 $spacing-xl;
  white-space: pre-line;
}

.welcome-suggestions {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: $spacing-sm;
  max-width: 500px;
  width: 100%;
}

.suggestion-card {
  display: block;
  width: 100%;
  padding: 14px 16px;
  background: $color-card-bg;
  border: 1px solid $color-border;
  border-radius: 10px;
  font-size: $font-size-sm;
  color: $color-text-primary;
  text-align: left;
  cursor: pointer;
  transition: all $transition-fast;
  font-family: inherit;
  overflow-wrap: anywhere;
  word-break: break-word;

  &:hover:not(:disabled) {
    border-color: $color-primary;
    background: $color-primary-light;
    color: $color-primary;
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.touch-target-min {
  min-height: var(--touch-target-min);
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

// ================================================================
// 平板端适配 (768px - 1199px)
// ================================================================
@media (min-width: 768px) and (max-width: 1199px) {
  .welcome-panel {
    padding: $spacing-xl $spacing-md;
  }

  .welcome-icon {
    width: 64px;
    height: 64px;
    border-radius: 16px;
    margin-bottom: $spacing-md;
  }

  .welcome-title {
    font-size: $font-size-xl;
  }

  .welcome-suggestions {
    max-width: 440px;
  }
}

// ================================================================
// 移动端适配 (< 768px)
// ================================================================
@media (max-width: 767px) {
  .welcome-panel {
    padding: $spacing-lg $spacing-md;
    justify-content: flex-start;
    overflow-y: auto;
  }

  .welcome-icon {
    width: 56px;
    height: 56px;
    border-radius: 14px;
    margin-bottom: $spacing-md;
  }

  .welcome-title {
    font-size: $font-size-lg;
  }

  .welcome-desc {
    font-size: $font-size-sm;
    max-width: 300px;
    margin-bottom: $spacing-lg;
  }

  .welcome-suggestions {
    grid-template-columns: 1fr;
    max-width: 400px;
  }

  .suggestion-card {
    padding: 12px 14px;
    font-size: $font-size-xs;
  }
}

// ---- prefers-reduced-motion ----
@media (prefers-reduced-motion: reduce) {
  .welcome-panel {
    animation: none;
  }
}
</style>
