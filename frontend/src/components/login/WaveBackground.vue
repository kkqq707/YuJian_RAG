<template>
  <!--
    WaveBackground — 底部 AI 数据流波浪

    使用 SVG 实现微弱的数据流波纹效果。
    多条波浪线叠加，缓慢移动，模拟数据流动。
    视觉克制，不抢夺注意力。
  -->
  <div class="wave-bg" aria-hidden="true">
    <svg
      class="wave-bg__svg"
      viewBox="0 0 1440 320"
      preserveAspectRatio="none"
    >
      <!-- 波浪 1 — 青色数据流 -->
      <path
        class="wave-bg__path wave-bg__path--1"
        d="M0,160 C120,200 240,100 360,140 C480,180 600,220 720,180 C840,140 960,100 1080,140 C1200,180 1320,200 1440,160 L1440,320 L0,320 Z"
      />
      <!-- 波浪 2 — 蓝紫色流 -->
      <path
        class="wave-bg__path wave-bg__path--2"
        d="M0,200 C100,160 200,240 360,200 C520,160 680,120 840,180 C1000,240 1160,200 1320,180 L1440,200 L1440,320 L0,320 Z"
      />
      <!-- 波浪 3 — 微弱底色 -->
      <path
        class="wave-bg__path wave-bg__path--3"
        d="M0,240 C180,200 360,280 540,240 C720,200 900,260 1080,230 C1260,200 1380,240 1440,220 L1440,320 L0,320 Z"
      />
    </svg>
  </div>
</template>

<script setup lang="ts">
// 纯视觉效果，无交互逻辑
</script>

<style lang="scss" scoped>
/* ============================================================
 * WaveBackground — AI 数据流波浪
 * ============================================================ */

.wave-bg {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 0;
  pointer-events: none;
  opacity: 0.25;
}

.wave-bg__svg {
  width: 100%;
  height: 200px;
  display: block;
}

.wave-bg__path {
  fill: none;
  stroke-width: 0.8;
}

/* 波浪 1 — 青色微光 */
.wave-bg__path--1 {
  stroke: rgba(54, 209, 220, 0.12);
  animation: wave-shift-1 6s ease-in-out infinite;
}

/* 波浪 2 — 蓝紫色微光 */
.wave-bg__path--2 {
  stroke: rgba(140, 100, 220, 0.1);
  animation: wave-shift-2 7s ease-in-out infinite;
}

/* 波浪 3 — 极弱底色填充 */
.wave-bg__path--3 {
  stroke: rgba(80, 120, 220, 0.06);
  fill: rgba(80, 120, 220, 0.02);
  animation: wave-shift-3 8s ease-in-out infinite;
}

@keyframes wave-shift-1 {
  0%, 100% {
    transform: translateX(0) translateY(0);
  }
  50% {
    transform: translateX(-20px) translateY(-8px);
  }
}

@keyframes wave-shift-2 {
  0%, 100% {
    transform: translateX(0) translateY(0);
  }
  50% {
    transform: translateX(15px) translateY(-5px);
  }
}

@keyframes wave-shift-3 {
  0%, 100% {
    transform: translateX(0) translateY(0);
  }
  50% {
    transform: translateX(-10px) translateY(-3px);
  }
}

/* 性能与无障碍 */
@media (prefers-reduced-motion: reduce) {
  .wave-bg__path {
    animation: none;
  }
  .wave-bg {
    opacity: 0.12;
  }
}

/* 移动端：降低波浪高度 */
@media (max-width: 768px) {
  .wave-bg__svg {
    height: 120px;
  }
  .wave-bg {
    opacity: 0.18;
  }
}
</style>
