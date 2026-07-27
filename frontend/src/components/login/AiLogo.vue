<template>
  <!--
    AiLogo — AI 六边形 Logo 组件

    六边形科技感图标 + 双层旋转光环 + 呼吸动画
    设计：未来科技 · 企业AI · 渐变紫蓝
  -->
  <div class="ai-logo" aria-hidden="true">
    <!-- 外层旋转光环 -->
    <svg class="ai-logo__ring ai-logo__ring--outer" viewBox="0 0 100 100">
      <polygon
        points="50,5 87,23 87,59 50,77 13,59 13,23"
        fill="none"
        stroke="url(#grad-outer)"
        stroke-width="1.2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      <defs>
        <linearGradient id="grad-outer" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="rgba(80,140,220,0.6)" />
          <stop offset="50%" stop-color="rgba(140,100,220,0.4)" />
          <stop offset="100%" stop-color="rgba(54,209,220,0.5)" />
        </linearGradient>
      </defs>
    </svg>

    <!-- 内层旋转光环 -->
    <svg class="ai-logo__ring ai-logo__ring--inner" viewBox="0 0 100 100">
      <polygon
        points="50,11 81,28 81,62 50,79 19,62 19,28"
        fill="none"
        stroke="url(#grad-inner)"
        stroke-width="0.8"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      <defs>
        <linearGradient id="grad-inner" x1="100%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="rgba(140,100,220,0.5)" />
          <stop offset="50%" stop-color="rgba(54,209,220,0.3)" />
          <stop offset="100%" stop-color="rgba(80,140,220,0.4)" />
        </linearGradient>
      </defs>
    </svg>

    <!-- 核心六边形 -->
    <div class="ai-logo__core">
      <svg viewBox="0 0 100 100" class="ai-logo__hex">
        <polygon
          points="50,18 80,34 80,66 50,82 20,66 20,34"
          fill="url(#grad-hex)"
          stroke="rgba(140,180,230,0.35)"
          stroke-width="0.8"
        />
        <defs>
          <linearGradient id="grad-hex" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="rgba(80,140,220,0.25)" />
            <stop offset="100%" stop-color="rgba(140,100,220,0.2)" />
          </linearGradient>
        </defs>
      </svg>
      <!-- AI 文字 -->
      <span class="ai-logo__text">AI</span>
    </div>

    <!-- 光点 -->
    <div class="ai-logo__dot" />
  </div>
</template>

<script setup lang="ts">
// 纯视觉组件，无交互逻辑
</script>

<style lang="scss" scoped>
/* ============================================================
 * AiLogo — AI 六边形 Logo
 * 呼吸 + 旋转光环 + 光点环绕
 * ============================================================ */

.ai-logo {
  position: relative;
  width: 96px;
  height: 96px;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: logo-breathe 4s ease-in-out infinite;
}

@keyframes logo-breathe {
  0%, 100% {
    transform: scale(1);
    filter: brightness(1);
  }
  50% {
    transform: scale(1.05);
    filter: brightness(1.08);
  }
}

/* ---- 旋转光环 ---- */
.ai-logo__ring {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;

  &--outer {
    animation: ring-spin-outer 8s linear infinite;
  }

  &--inner {
    animation: ring-spin-inner 6s linear infinite reverse;
  }
}

@keyframes ring-spin-outer {
  to { transform: rotate(360deg); }
}

@keyframes ring-spin-inner {
  to { transform: rotate(-360deg); }
}

/* ---- 核心六边形 ---- */
.ai-logo__core {
  position: relative;
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
}

.ai-logo__hex {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.ai-logo__text {
  position: relative;
  z-index: 1;
  font-size: 20px;
  font-weight: 800;
  letter-spacing: 1px;
  background: linear-gradient(135deg, #8baef0 0%, #a78bfa 50%, #c4b5fd 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  font-family: 'SF Pro Display', 'Inter', -apple-system, sans-serif;
}

/* ---- 光点（沿六边形轨道旋转） ---- */
.ai-logo__dot {
  position: absolute;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: rgba(140, 180, 240, 0.9);
  box-shadow:
    0 0 8px rgba(140, 180, 240, 0.7),
    0 0 16px rgba(140, 180, 240, 0.3);
  pointer-events: none;
  top: -2px;
  left: 50%;
  margin-left: -2.5px;
  animation: dot-orbit 4s linear infinite;
}

@keyframes dot-orbit {
  from { transform: rotate(0deg) translateX(48px) rotate(0deg); }
  to   { transform: rotate(360deg) translateX(48px) rotate(-360deg); }
}

/* ============================================================
 * 响应式
 * ============================================================ */

@media (max-width: 900px) {
  .ai-logo {
    width: 72px;
    height: 72px;
  }

  .ai-logo__core {
    width: 42px;
    height: 42px;
  }

  .ai-logo__text {
    font-size: 16px;
  }

  .ai-logo__dot {
    animation: dot-orbit 4s linear infinite;
  }

  @keyframes dot-orbit {
    from { transform: rotate(0deg) translateX(36px) rotate(0deg); }
    to   { transform: rotate(360deg) translateX(36px) rotate(-360deg); }
  }
}

/* 低性能设备：关闭动画 */
@media (prefers-reduced-motion: reduce) {
  .ai-logo {
    animation: none;
  }
  .ai-logo__ring {
    animation: none;
  }
  .ai-logo__dot {
    display: none;
  }
}
</style>
