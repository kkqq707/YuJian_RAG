<template>
  <div class="welcome-panel">
    <div class="welcome-icon">
      <Sparkles :size="48" />
    </div>
    <h1 class="welcome-title">您好，我是企业智库 AI 助手</h1>
    <p class="welcome-desc">
      我可以基于企业内部资料，为您解答业务、产品、制度和服务相关问题。
    </p>
    <div class="welcome-suggestions">
      <button
        v-for="item in suggestions"
        :key="item"
        class="suggestion-card"
        :disabled="sending"
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
}>()

defineEmits<{
  select: [question: string]
}>()

/**
 * 推荐问题 — 基于企业知识库常见问题
 * 快速提问卡片：公司介绍 / 产品信息 / 服务流程 / 合作政策
 */
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
}

.welcome-title {
  font-size: $font-size-2xl;
  font-weight: 600;
  color: $color-text-primary;
  margin-bottom: $spacing-sm;
}

.welcome-desc {
  font-size: $font-size-base;
  color: $color-text-secondary;
  max-width: 420px;
  line-height: 1.6;
  margin-bottom: $spacing-xl;
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

@media (max-width: 768px) {
  .welcome-suggestions {
    grid-template-columns: 1fr;
  }
  .welcome-title {
    font-size: $font-size-xl;
  }
}
</style>
