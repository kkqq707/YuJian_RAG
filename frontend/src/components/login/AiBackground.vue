<template>
  <!--
    AiBackground — AI 空间背景（多层多色动态渐变）

    Layer 1: 超大尺寸多色线性渐变（7色 400% 尺寸，24s 流动）
             深蓝 → 科技蓝 → 靛蓝 → 紫色 → 品红 → 青蓝 → 青绿 → 深蓝
    Layer 2: 网格纹理（淡化）
    Layer 3: 动态光球 × 5（蓝/紫/品红/青蓝/青绿，大幅移动 10%-30%）
    Layer 4: 粒子网络（slot）
    Layer 5: 底部波浪（slot）

    设计：多种颜色缓慢交替、流动和融合，极光般效果
  -->
  <div class="ai-bg" aria-hidden="true">
    <!-- Layer 1: 多色渐变背景（超大尺寸位移） -->
    <div class="ai-bg__gradient" />

    <!-- Layer 1b: 辅助渐变层（反向流动，增强层次） -->
    <div class="ai-bg__gradient-secondary" />

    <!-- Layer 2: 网格纹理 -->
    <div class="ai-bg__grid" />

    <!-- Layer 3: 动态光球（5 个，大范围移动） -->
    <div class="ai-bg__orbs">
      <div class="ai-bg__orb ai-bg__orb--deepblue" />
      <div class="ai-bg__orb ai-bg__orb--purple" />
      <div class="ai-bg__orb ai-bg__orb--magenta" />
      <div class="ai-bg__orb ai-bg__orb--cyan" />
      <div class="ai-bg__orb ai-bg__orb--teal" />
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
 * AiBackground — 企业 AI 多色动态渐变空间背景
 *
 * 颜色方案（循环交替）：
 *   深蓝 #102A72  →  科技蓝 #1268E8  →  靛蓝 #3A32A3
 *   → 紫 #7234D8  →  品红 #B336D9  →  青蓝 #08A8C8
 *   → 青绿 #18B8A0  →  回到深蓝
 *
 * 完整周期：~24s
 * ============================================================ */

.ai-bg {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
}

/* ============================================================
 * Layer 1: 主渐变 — 超大尺寸多色 linear-gradient
 * 7 色渐变，400% 尺寸，24s 缓慢位移
 * 颜色分阶段进入画面，形成自然的多色交替
 * ============================================================ */
.ai-bg__gradient {
  position: absolute;
  inset: -20%;
  background: linear-gradient(
    135deg,
    #0a0e2a 0%,       /* 深空底色 */
    #102A72 12%,       /* 深蓝 */
    #1268E8 22%,       /* 科技蓝 */
    #3A32A3 35%,       /* 靛蓝 */
    #7234D8 48%,       /* 紫色 */
    #B336D9 60%,       /* 品红 */
    #08A8C8 72%,       /* 青蓝 */
    #18B8A0 84%,       /* 青绿 */
    #102A72 96%,       /* 回到深蓝（接缝自然） */
    #0a0e2a 100%
  );
  background-size: 400% 400%;
  animation: gradientFlow 24s ease-in-out infinite;
}

@keyframes gradientFlow {
  0% {
    background-position: 0% 0%;
  }
  12.5% {
    background-position: 30% 15%;
  }
  25% {
    background-position: 55% 30%;
  }
  37.5% {
    background-position: 70% 55%;
  }
  50% {
    background-position: 85% 70%;
  }
  62.5% {
    background-position: 70% 85%;
  }
  75% {
    background-position: 45% 75%;
  }
  87.5% {
    background-position: 15% 45%;
  }
  100% {
    background-position: 0% 0%;
  }
}

/* ============================================================
 * Layer 1b: 辅助渐变层 — 反向流动，增强多色层次感
 * 不同角度、不同周期，产生颜色叠加效果
 * ============================================================ */
.ai-bg__gradient-secondary {
  position: absolute;
  inset: -20%;
  background: radial-gradient(
      ellipse 70% 55% at 30% 20%,
      rgba(18, 104, 232, 0.12),
      transparent 50%
    ),
    radial-gradient(
      ellipse 60% 50% at 70% 60%,
      rgba(114, 52, 216, 0.1),
      transparent 50%
    ),
    radial-gradient(
      ellipse 55% 45% at 50% 40%,
      rgba(8, 168, 200, 0.08),
      transparent 50%
    );
  background-size: 300% 300%;
  animation: gradientFlowSecondary 20s ease-in-out infinite;
  opacity: 0.7;
}

@keyframes gradientFlowSecondary {
  0% {
    background-position: 100% 100%;
  }
  25% {
    background-position: 70% 50%;
  }
  50% {
    background-position: 30% 20%;
  }
  75% {
    background-position: 60% 70%;
  }
  100% {
    background-position: 100% 100%;
  }
}

/* ============================================================
 * Layer 2: 网格纹理
 * ============================================================ */
.ai-bg__grid {
  position: absolute;
  inset: 0;
  opacity: 0.25;
  background-image:
    radial-gradient(circle, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
  background-size: 55px 55px;
  mask-image: radial-gradient(ellipse 70% 50% at 50% 50%, black 25%, transparent 70%);
  -webkit-mask-image: radial-gradient(ellipse 70% 50% at 50% 50%, black 25%, transparent 70%);
}

/* ============================================================
 * Layer 3: 动态光球 × 5
 * 每个光球：大范围移动（10%-30% 页面宽高），不同动画时长
 * 颜色：深蓝 / 紫色 / 品红 / 青蓝 / 青绿
 * 光球穿梭页面，形成"极光"般的色彩流动
 * ============================================================ */
.ai-bg__orbs {
  position: absolute;
  inset: 0;
}

.ai-bg__orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(140px);
  will-change: transform, opacity;
}

/* ---- 深蓝光球（#102A72） — 左上区，大幅漂移 ---- */
.ai-bg__orb--deepblue {
  width: 55vw;
  height: 55vw;
  max-width: 800px;
  max-height: 800px;
  top: -15%;
  left: -12%;
  background: radial-gradient(circle, rgba(18, 104, 232, 0.18), rgba(16, 42, 114, 0.12), transparent 60%);
  animation: orb-deepblue 11s ease-in-out infinite;
}

@keyframes orb-deepblue {
  0%, 100% {
    transform: translate(0, 0) scale(1);
    opacity: 0.5;
  }
  25% {
    transform: translate(45px, 35px) scale(1.12);
    opacity: 0.7;
  }
  50% {
    transform: translate(15px, 60px) scale(0.95);
    opacity: 0.45;
  }
  75% {
    transform: translate(-20px, 25px) scale(1.08);
    opacity: 0.6;
  }
}

/* ---- 紫色光球（#7234D8） — 右上区，斜向移动 ---- */
.ai-bg__orb--purple {
  width: 48vw;
  height: 48vw;
  max-width: 700px;
  max-height: 700px;
  top: -10%;
  right: -10%;
  background: radial-gradient(circle, rgba(114, 52, 216, 0.2), rgba(179, 54, 217, 0.1), transparent 60%);
  animation: orb-purple 13s ease-in-out infinite;
  animation-delay: -3s;
}

@keyframes orb-purple {
  0%, 100% {
    transform: translate(0, 0) scale(1);
    opacity: 0.45;
  }
  20% {
    transform: translate(-50px, 40px) scale(1.15);
    opacity: 0.65;
  }
  40% {
    transform: translate(-25px, 15px) scale(1.05);
    opacity: 0.5;
  }
  60% {
    transform: translate(20px, -30px) scale(0.9);
    opacity: 0.35;
  }
  80% {
    transform: translate(-10px, 20px) scale(1.1);
    opacity: 0.55;
  }
}

/* ---- 品红光球（#B336D9） — 左下区，缓慢穿行 ---- */
.ai-bg__orb--magenta {
  width: 42vw;
  height: 42vw;
  max-width: 600px;
  max-height: 600px;
  bottom: -15%;
  left: -5%;
  background: radial-gradient(circle, rgba(179, 54, 217, 0.16), rgba(114, 52, 216, 0.08), transparent 60%);
  animation: orb-magenta 14s ease-in-out infinite;
  animation-delay: -6s;
}

@keyframes orb-magenta {
  0%, 100% {
    transform: translate(0, 0) scale(1);
    opacity: 0.35;
  }
  30% {
    transform: translate(40px, -55px) scale(1.2);
    opacity: 0.55;
  }
  60% {
    transform: translate(60px, -20px) scale(0.92);
    opacity: 0.28;
  }
  85% {
    transform: translate(15px, -40px) scale(1.08);
    opacity: 0.45;
  }
}

/* ---- 青蓝光球（#08A8C8） — 右下区，对角漂移 ---- */
.ai-bg__orb--cyan {
  width: 45vw;
  height: 45vw;
  max-width: 650px;
  max-height: 650px;
  bottom: -12%;
  right: -8%;
  background: radial-gradient(circle, rgba(8, 168, 200, 0.14), rgba(24, 184, 160, 0.08), transparent 60%);
  animation: orb-cyan 10s ease-in-out infinite;
  animation-delay: -2s;
}

@keyframes orb-cyan {
  0%, 100% {
    transform: translate(0, 0) scale(1);
    opacity: 0.3;
  }
  25% {
    transform: translate(-35px, -25px) scale(1.1);
    opacity: 0.5;
  }
  50% {
    transform: translate(-15px, -50px) scale(0.95);
    opacity: 0.25;
  }
  75% {
    transform: translate(-45px, -10px) scale(1.15);
    opacity: 0.45;
  }
}

/* ---- 青绿光球（#18B8A0） — 顶部中区，横向漂移 ---- */
.ai-bg__orb--teal {
  width: 38vw;
  height: 38vw;
  max-width: 500px;
  max-height: 500px;
  top: -20%;
  left: 35%;
  background: radial-gradient(circle, rgba(24, 184, 160, 0.12), rgba(8, 168, 200, 0.06), transparent 60%);
  animation: orb-teal 9s ease-in-out infinite;
  animation-delay: -5s;
}

@keyframes orb-teal {
  0%, 100% {
    transform: translateX(-50%) scale(1);
    opacity: 0.2;
  }
  33% {
    transform: translateX(-50%) translateY(35px) scale(1.18);
    opacity: 0.4;
  }
  66% {
    transform: translateX(-50%) translateY(-20px) scale(0.88);
    opacity: 0.15;
  }
}

/* ============================================================
 * 性能与无障碍 — 减少动态模式
 * ============================================================ */

@media (prefers-reduced-motion: reduce) {
  .ai-bg__gradient {
    animation: none;
    /* 保留静态多色渐变，禁用位置移动 */
    background: linear-gradient(
      135deg,
      #0a0e2a 0%,
      #102A72 12%,
      #1268E8 22%,
      #3A32A3 35%,
      #7234D8 48%,
      #B336D9 60%,
      #08A8C8 72%,
      #18B8A0 84%,
      #102A72 96%,
      #0a0e2a 100%
    );
    background-size: 400% 400%;
    background-position: 50% 50%;
  }

  .ai-bg__gradient-secondary {
    animation: none;
    opacity: 0.4;
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
    filter: blur(100px);
  }

  .ai-bg__orb--deepblue,
  .ai-bg__orb--purple,
  .ai-bg__orb--magenta,
  .ai-bg__orb--cyan,
  .ai-bg__orb--teal {
    opacity: 0.25;
  }
}
</style>
