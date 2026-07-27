<template>
  <div class="brand-logo">
    <!-- Logo 图标 + 旋转光环 -->
    <div class="brand-logo__icon-wrapper">
      <div class="brand-logo__ring brand-logo__ring--outer" />
      <div class="brand-logo__ring brand-logo__ring--inner" />
      <div class="brand-logo__glow-dot" />
      <div class="brand-logo__icon">
        <Sparkles :size="26" />
      </div>
    </div>

    <!-- 品牌文字 -->
    <h1 class="brand-logo__title">YuJian AI</h1>
    <p class="brand-logo__subtitle">企业知识智能平台</p>

    <!-- 宣传语 -->
    <p class="brand-logo__tagline">让知识驱动智能决策</p>

    <!-- 特性亮点 -->
    <div class="brand-logo__features">
      <div class="brand-logo__feature">
        <span class="feature-dot" />
        <span>RAG 智能检索增强</span>
      </div>
      <div class="brand-logo__feature">
        <span class="feature-dot" />
        <span>企业级知识管理</span>
      </div>
      <div class="brand-logo__feature">
        <span class="feature-dot" />
        <span>多模型 AI 对话</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Sparkles } from '@lucide/vue'
</script>

<style lang="scss" scoped>
.brand-logo {
  user-select: none;
}

/* ---- 图标区域 ---- */
.brand-logo__icon-wrapper {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  margin-bottom: 28px;
}

/* 旋转光环 */
.brand-logo__ring {
  position: absolute;
  border-radius: 50%;
  border: 1px solid transparent;
  pointer-events: none;

  &--outer {
    inset: -4px;
    border-top-color: rgba(80, 120, 220, 0.4);
    border-right-color: rgba(140, 100, 220, 0.25);
    animation: brand-ring-spin 4s linear infinite;
  }

  &--inner {
    inset: 4px;
    border-bottom-color: rgba(140, 100, 220, 0.35);
    border-left-color: rgba(80, 120, 220, 0.2);
    animation: brand-ring-spin 2.5s linear infinite reverse;
  }
}

@keyframes brand-ring-spin {
  to { transform: rotate(360deg); }
}

/* 光点 — 跟随光环旋转 */
.brand-logo__glow-dot {
  position: absolute;
  top: -4px;
  left: 50%;
  width: 6px;
  height: 6px;
  margin-left: -3px;
  border-radius: 50%;
  background: rgba(122, 158, 232, 0.9);
  box-shadow: 0 0 10px rgba(122, 158, 232, 0.6), 0 0 20px rgba(122, 158, 232, 0.3);
  pointer-events: none;
  animation: brand-dot-orbit 4s linear infinite;
}

@keyframes brand-dot-orbit {
  from { transform: rotate(0deg) translateX(40px) rotate(0deg); }
  to   { transform: rotate(360deg) translateX(40px) rotate(-360deg); }
}

/* 图标 */
.brand-logo__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(80, 120, 220, 0.18), rgba(140, 100, 220, 0.18));
  border: 1px solid rgba(122, 158, 232, 0.25);
  color: #8AAAEE;
  position: relative;
  z-index: 1;
}

/* ---- 标题 ---- */
.brand-logo__title {
  font-size: 36px;
  font-weight: 800;
  margin: 0 0 10px;
  background: linear-gradient(135deg, #8AAAEE 0%, #A78BFA 50%, #C4B5FD 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: 2px;
  line-height: 1.2;
}

/* ---- 副标题 ---- */
.brand-logo__subtitle {
  font-size: 15px;
  color: var(--text-secondary);
  margin: 0 0 32px;
  letter-spacing: 2px;
}

/* ---- 宣传语 ---- */
.brand-logo__tagline {
  font-size: 14px;
  color: var(--text-tertiary);
  margin: 0 0 36px;
  line-height: 1.6;
  letter-spacing: 0.5px;
}

/* ---- 特性列表 ---- */
.brand-logo__features {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.brand-logo__feature {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: var(--text-secondary);
  letter-spacing: 0.5px;
}

.feature-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(122, 158, 232, 0.5);
  box-shadow: 0 0 6px rgba(122, 158, 232, 0.3);
  flex-shrink: 0;
}

/* ---- 响应式 ---- */
@media (max-width: 900px) {
  .brand-logo__icon-wrapper {
    width: 64px;
    height: 64px;
    margin-bottom: 20px;
  }

  .brand-logo__icon {
    width: 44px;
    height: 44px;
    border-radius: 12px;
  }

  .brand-logo__title {
    font-size: 28px;
  }

  .brand-logo__subtitle {
    margin-bottom: 20px;
  }

  .brand-logo__tagline {
    margin-bottom: 24px;
  }

  .brand-logo__features {
    display: none;
  }
}

/* 低性能设备：关闭动画 */
@media (prefers-reduced-motion: reduce) {
  .brand-logo__ring {
    animation: none;
  }
  .brand-logo__glow-dot {
    display: none;
  }
}
</style>
