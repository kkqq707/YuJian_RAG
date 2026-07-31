<template>
  <div class="public-welcome">
    <!-- Logo -->
    <div class="public-welcome__logo">
      <img src="/logo.png" alt="煜见科技" class="public-welcome__logo-img" />
    </div>

    <!-- 标题 -->
    <h1 class="public-welcome__title">煜见科技 AI 智能助手</h1>

    <!-- 副标题 -->
    <p class="public-welcome__subtitle">基于企业知识库的智能问答助手</p>

    <!-- 能力列表 -->
    <div class="public-welcome__capabilities">
      <p class="public-welcome__capabilities-title">我可以帮助您了解：</p>
      <ul class="public-welcome__capabilities-list">
        <li><Check :size="16" />公司业务介绍</li>
        <li><Check :size="16" />技术服务方案</li>
        <li><Check :size="16" />产品能力</li>
        <li><Check :size="16" />合作流程</li>
      </ul>
    </div>

    <!-- 推荐问题 -->
    <div class="public-welcome__suggestions">
      <p class="public-welcome__suggestions-title">您也可以直接问我：</p>
      <div class="public-welcome__suggestion-grid">
        <button
          v-for="item in suggestions"
          :key="item"
          class="public-welcome__suggestion-btn touch-target-min"
          :disabled="sending"
          :aria-label="`推荐问题：${item}`"
          @click="$emit('select', item)"
        >
          {{ item }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Check } from '@lucide/vue'

defineProps<{
  sending?: boolean
  isMobile?: boolean
}>()

defineEmits<{
  select: [question: string]
}>()

const suggestions = [
  '煜见科技主要业务是什么？',
  '公司有哪些技术服务？',
  '如何与煜见科技合作？',
  '有哪些 AI 解决方案？',
]
</script>

<style lang="scss" scoped>
.public-welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: $spacing-2xl $spacing-lg $spacing-xl;
  text-align: center;
  min-height: 0;
  animation: fadeInUp 0.5s ease;
}

.public-welcome__logo {
  margin-bottom: $spacing-lg;
  flex-shrink: 0;
}

.public-welcome__logo-img {
  width: 72px;
  height: 72px;
  object-fit: contain;
  border-radius: 16px;
}

// ---- 标题 & 副标题 ----
.public-welcome__title {
  font-size: $font-size-2xl;
  font-weight: 700;
  color: $color-text-primary;
  margin: 0 0 $spacing-sm;
  line-height: 1.4;
  letter-spacing: -0.3px;
}

.public-welcome__subtitle {
  font-size: $font-size-base;
  color: $color-text-secondary;
  max-width: 420px;
  line-height: 1.6;
  margin: 0 0 $spacing-xl;
}

// ---- 能力列表 ----
.public-welcome__capabilities {
  width: 100%;
  max-width: 540px;
  background: $color-card-bg;
  border: 1px solid $color-border;
  border-radius: 12px;
  padding: $spacing-md $spacing-lg;
  margin-bottom: $spacing-xl;
  text-align: left;
  box-shadow: $shadow-card;
}

.public-welcome__capabilities-title {
  font-size: $font-size-sm;
  color: $color-text-secondary;
  margin: 0 0 $spacing-sm;
  line-height: 1.5;
}

.public-welcome__capabilities-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: $spacing-xs $spacing-lg;

  li {
    display: flex;
    align-items: center;
    gap: $spacing-sm;
    font-size: $font-size-sm;
    color: $color-text-primary;
    line-height: 1.5;
    padding: 2px 0;

    svg {
      color: $color-success;
      flex-shrink: 0;
    }
  }
}

// ---- 推荐问题 ----
.public-welcome__suggestions {
  width: 100%;
  max-width: 540px;
}

.public-welcome__suggestions-title {
  font-size: $font-size-xs;
  color: $color-text-tertiary;
  margin: 0 0 $spacing-sm;
  line-height: 1.5;
}

.public-welcome__suggestion-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: $spacing-sm;
}

.public-welcome__suggestion-btn {
  display: block;
  width: 100%;
  padding: 12px 16px;
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
  line-height: 1.5;

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
// 平板端适配
// ================================================================
@media (min-width: 768px) and (max-width: 1199px) {
  .public-welcome {
    padding: $spacing-xl $spacing-md;
  }

  .public-welcome__logo-img {
    width: 60px;
    height: 60px;
  }

  .public-welcome__title {
    font-size: $font-size-xl;
  }

  .public-welcome__capabilities {
    max-width: 480px;
  }

  .public-welcome__suggestions {
    max-width: 480px;
  }
}

// ================================================================
// 移动端适配
// ================================================================
@media (max-width: 767px) {
  .public-welcome {
    padding: $spacing-lg $spacing-md;
    justify-content: flex-start;
    overflow-y: auto;
  }

  .public-welcome__logo-img {
    width: 52px;
    height: 52px;
    border-radius: 12px;
  }

  .public-welcome__title {
    font-size: $font-size-lg;
  }

  .public-welcome__subtitle {
    font-size: $font-size-sm;
    max-width: 300px;
    margin-bottom: $spacing-lg;
  }

  .public-welcome__capabilities {
    max-width: 100%;
    padding: $spacing-sm;
  }

  .public-welcome__capabilities-list {
    grid-template-columns: 1fr;
    gap: 2px;

    li {
      font-size: $font-size-xs;
    }
  }

  .public-welcome__suggestions {
    max-width: 100%;
  }

  .public-welcome__suggestion-grid {
    grid-template-columns: 1fr;
  }

  .public-welcome__suggestion-btn {
    padding: 10px 14px;
    font-size: $font-size-xs;
  }
}

// ---- prefers-reduced-motion ----
@media (prefers-reduced-motion: reduce) {
  .public-welcome {
    animation: none;
  }
}
</style>
