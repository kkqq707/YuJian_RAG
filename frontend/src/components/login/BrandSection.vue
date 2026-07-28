<template>
  <!--
    BrandSection — 左侧品牌展示区域

    包含：品牌名称（煜见AI）、平台定位、宣传语、功能介绍列表

    设计：企业级 AI 知识平台 · 高端克制
  -->
  <div class="brand-section">
    <!-- 淡化 AI 网络背景点缀 -->
    <div class="brand-section__bg" aria-hidden="true">
      <div
        v-for="i in 10"
        :key="i"
        class="brand-bg-dot"
        :style="dotStyle(i)"
      />
    </div>

    <!-- 品牌名称 — 渐变文字 -->
    <h1 class="brand-section__name">
      煜见AI
    </h1>

    <!-- 平台定位 -->
    <p class="brand-section__title">
      企业知识智能平台
    </p>

    <!-- 分割线 -->
    <div class="brand-section__divider" />

    <!-- 宣传语 -->
    <p class="brand-section__tagline">
      让知识驱动智能，让智能创造价值
    </p>

    <!-- 功能介绍列表 -->
    <FeatureList />
  </div>
</template>

<script setup lang="ts">
import FeatureList from './FeatureList.vue'

/** 为淡化背景点生成随机位置样式 */
function dotStyle(i: number): Record<string, string> {
  const x = 8 + ((i * 41 + 11) % 82)
  const y = 5 + ((i * 47 + 9) % 85)
  const size = 2 + (i % 3) * 1.5
  const opacity = 0.12 + (i % 5) * 0.03
  return {
    left: `${x}%`,
    top: `${y}%`,
    width: `${size}px`,
    height: `${size}px`,
    opacity: `${opacity}`,
  }
}
</script>

<style lang="scss" scoped>
/* ============================================================
 * BrandSection — 企业 AI 品牌展示
 * ============================================================ */

.brand-section {
  position: relative;
  user-select: none;
  padding: 0;
}

/* ---- 淡化背景点 ---- */
.brand-section__bg {
  position: absolute;
  inset: -60px -40px -60px -60px;
  pointer-events: none;
  z-index: 0;
  overflow: hidden;
}

.brand-bg-dot {
  position: absolute;
  border-radius: 50%;
  background: rgba(140, 180, 230, 0.45);
  box-shadow: 0 0 5px rgba(140, 180, 230, 0.15);
  animation: brand-dot-breathe 4.5s ease-in-out infinite;
}

/* 不同的动画延迟 */
.brand-bg-dot:nth-child(1) { animation-delay: 0s; }
.brand-bg-dot:nth-child(2) { animation-delay: 0.4s; }
.brand-bg-dot:nth-child(3) { animation-delay: 0.8s; }
.brand-bg-dot:nth-child(4) { animation-delay: 1.2s; }
.brand-bg-dot:nth-child(5) { animation-delay: 1.6s; }
.brand-bg-dot:nth-child(6) { animation-delay: 2.0s; }
.brand-bg-dot:nth-child(7) { animation-delay: 2.4s; }
.brand-bg-dot:nth-child(8) { animation-delay: 2.8s; }
.brand-bg-dot:nth-child(9) { animation-delay: 3.2s; }
.brand-bg-dot:nth-child(10) { animation-delay: 3.6s; }

@keyframes brand-dot-breathe {
  0%, 100% { opacity: 0.12; transform: scale(1); }
  50% { opacity: 0.3; transform: scale(1.4); }
}

/* ---- 品牌名称 — 渐变文字（紫蓝渐变） ---- */
.brand-section__name {
  position: relative;
  z-index: 1;
  font-size: 42px;
  font-weight: 800;
  margin: 0 0 14px;
  background: linear-gradient(135deg, #8baef0 0%, #a78bfa 40%, #c4b5fd 70%, #818cf8 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: 3px;
  line-height: 1.2;
}

/* ---- 平台定位 ---- */
.brand-section__title {
  position: relative;
  z-index: 1;
  font-size: 16px;
  color: rgba(180, 200, 230, 0.65);
  margin: 0 0 36px;
  letter-spacing: 4px;
  font-weight: 400;
}

/* ---- 分割线 ---- */
.brand-section__divider {
  position: relative;
  z-index: 1;
  width: 60px;
  height: 2px;
  background: linear-gradient(90deg, rgba(80, 140, 220, 0.55), rgba(138, 43, 226, 0.3), transparent);
  margin-bottom: 32px;
  border-radius: 1px;
}

/* ---- 宣传语 ---- */
.brand-section__tagline {
  position: relative;
  z-index: 1;
  font-size: 15px;
  color: rgba(160, 190, 220, 0.55);
  margin: 0 0 48px;
  line-height: 1.7;
  letter-spacing: 1px;
  font-weight: 300;
}

/* ============================================================
 * 响应式 — 使用统一断点体系
 * ============================================================ */

/* 平板：居中品牌内容，缩小字号 */
@media (min-width: 768px) and (max-width: 1199px) {
  .brand-section {
    text-align: center;
  }

  .brand-section__name {
    font-size: clamp(26px, 5vw, 36px);
    letter-spacing: 2px;
    margin-bottom: 8px;
  }

  .brand-section__title {
    font-size: clamp(12px, 2vw, 15px);
    margin-bottom: 18px;
    letter-spacing: 2px;
  }

  .brand-section__divider {
    margin: 0 auto 18px;
  }

  .brand-section__tagline {
    margin-bottom: 16px;
    font-size: 12px;
  }

  .brand-bg-dot {
    display: none;
  }
}

/* 移动端：精简品牌展示，仅保留品牌名和简短说明 */
@media (max-width: 767px) {
  .brand-section {
    text-align: center;
  }

  .brand-section__name {
    font-size: clamp(22px, 7vw, 28px);
    letter-spacing: 1.5px;
    margin-bottom: 6px;
  }

  .brand-section__title {
    font-size: clamp(11px, 3.5vw, 14px);
    margin-bottom: 12px;
    letter-spacing: 1.5px;
  }

  .brand-section__divider {
    width: 40px;
    margin: 0 auto 12px;
  }

  .brand-section__tagline {
    font-size: 11px;
    margin-bottom: 8px;
  }

  .brand-bg-dot {
    display: none;
  }
}

/* 低性能设备：关闭动画 */
@media (prefers-reduced-motion: reduce) {
  .brand-bg-dot {
    animation: none;
  }
}
</style>
