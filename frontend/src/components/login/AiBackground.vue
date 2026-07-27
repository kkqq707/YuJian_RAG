<template>
  <!--
    AiBackground — AI 空间背景（多层叠加）

    Layer 1: 渐变背景（#25145E → #283593 → #0066CC + #8A2BE2, #00CFFF 辅助色）
             200% 200% 尺寸，15-25s 流动动画
    Layer 2: 网格纹理（淡化）
    Layer 3: 动态光球（紫色 + 蓝色 + 青色）
    Layer 4: 粒子网络（独立组件，slot）
    Layer 5: 底部波浪（独立组件，slot）

    设计：克制、企业级、不刺眼
  -->
  <div class="ai-bg" aria-hidden="true">
    <!-- Layer 1: 渐变背景（颜色流动） -->
    <div class="ai-bg__gradient" />

    <!-- Layer 2: 网格纹理 -->
    <div class="ai-bg__grid" />

    <!-- Layer 3: 动态光球 -->
    <div class="ai-bg__orbs">
      <div class="ai-bg__orb ai-bg__orb--purple" />
      <div class="ai-bg__orb ai-bg__orb--blue" />
      <div class="ai-bg__orb ai-bg__orb--cyan" />
    </div>

    <!-- Layer 4: 粒子网络 -->
    <slot name="particles" />

    <!-- Layer 5: 底部波浪 -->
    <slot name="wave" />
  </div>
</template>

<script setup lang="ts">
// 纯视觉容器，无交互逻辑
</script>

<style lang="scss" scoped>
/* ============================================================
 * AiBackground — 企业 AI 空间背景
 * 主色：#25145E, #283593, #0066CC
 * 辅助：#8A2BE2, #00CFFF
 * ============================================================ */

.ai-bg {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
}

/* ---- Layer 1: 渐变背景（流动动画 20s） ---- */
.ai-bg__gradient {
  position: absolute;
  inset: -20%;
  background:
    radial-gradient(ellipse 70% 50% at 25% 25%, rgba(138, 43, 226, 0.18), transparent 55%),
    radial-gradient(ellipse 60% 55% at 65% 55%, rgba(40, 53, 147, 0.22), transparent 55%),
    radial-gradient(ellipse 55% 45% at 45% 75%, rgba(0, 111, 204, 0.18), transparent 55%),
    radial-gradient(ellipse 50% 40% at 80% 30%, rgba(0, 207, 255, 0.1), transparent 55%),
    radial-gradient(ellipse 65% 50% at 15% 70%, rgba(37, 20, 94, 0.15), transparent 55%),
    linear-gradient(
      160deg,
      #25145E 0%,
      #1e1a50 15%,
      #283593 35%,
      #1a2d70 50%,
      #0066CC 65%,
      #1a3d70 80%,
      #25145E 100%
    );
  background-size: 200% 200%;
  animation: gradientMove 20s ease-in-out infinite;
}

@keyframes gradientMove {
  0% {
    background-position: 0% 0%;
  }
  25% {
    background-position: 50% 25%;
  }
  50% {
    background-position: 100% 50%;
  }
  75% {
    background-position: 50% 75%;
  }
  100% {
    background-position: 0% 0%;
  }
}

/* ---- Layer 2: 网格纹理 ---- */
.ai-bg__grid {
  position: absolute;
  inset: 0;
  opacity: 0.3;
  background-image:
    radial-gradient(circle, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
  background-size: 55px 55px;
  mask-image: radial-gradient(ellipse 70% 50% at 50% 50%, black 25%, transparent 70%);
  -webkit-mask-image: radial-gradient(ellipse 70% 50% at 50% 50%, black 25%, transparent 70%);
}

/* ---- Layer 3: 动态光球 ---- */
.ai-bg__orbs {
  position: absolute;
  inset: 0;
}

.ai-bg__orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(130px);
  will-change: transform, opacity;
}

/* 紫色光球（#8A2BE2） — 左上方 */
.ai-bg__orb--purple {
  width: 50vw;
  height: 50vw;
  max-width: 750px;
  max-height: 750px;
  top: -12%;
  left: -10%;
  background: radial-gradient(circle, rgba(138, 43, 226, 0.25), transparent 65%);
  animation: orb-purple 8s ease-in-out infinite;
}

@keyframes orb-purple {
  0%, 100% {
    transform: translate(0, 0) scale(1);
    opacity: 0.55;
  }
  50% {
    transform: translate(30px, 25px) scale(1.1);
    opacity: 0.75;
  }
}

/* 蓝色光球（#283593） — 右下方 */
.ai-bg__orb--blue {
  width: 48vw;
  height: 48vw;
  max-width: 700px;
  max-height: 700px;
  bottom: -8%;
  right: -8%;
  background: radial-gradient(circle, rgba(40, 53, 147, 0.22), transparent 65%);
  animation: orb-blue 9s ease-in-out infinite;
}

@keyframes orb-blue {
  0%, 100% {
    transform: translate(0, 0) scale(1);
    opacity: 0.5;
  }
  50% {
    transform: translate(-30px, -20px) scale(1.12);
    opacity: 0.7;
  }
}

/* 青色光球（#00CFFF） — 顶部中间 */
.ai-bg__orb--cyan {
  width: 38vw;
  height: 38vw;
  max-width: 500px;
  max-height: 500px;
  top: -18%;
  left: 45%;
  background: radial-gradient(circle, rgba(0, 207, 255, 0.12), transparent 65%);
  animation: orb-cyan 7s ease-in-out infinite;
}

@keyframes orb-cyan {
  0%, 100% {
    transform: translateX(-50%) scale(1);
    opacity: 0.25;
  }
  50% {
    transform: translateX(-50%) scale(1.18);
    opacity: 0.45;
  }
}

/* ============================================================
 * 性能与无障碍
 * ============================================================ */

@media (prefers-reduced-motion: reduce) {
  .ai-bg__gradient {
    animation: none;
  }
  .ai-bg__orb {
    animation: none;
    display: none;
  }
  .ai-bg__grid {
    opacity: 0.12;
  }
}

/* 移动端：降低光球强度 */
@media (max-width: 768px) {
  .ai-bg__orb {
    filter: blur(80px);
  }
  .ai-bg__orb--purple,
  .ai-bg__orb--blue {
    opacity: 0.35;
  }
}
</style>
