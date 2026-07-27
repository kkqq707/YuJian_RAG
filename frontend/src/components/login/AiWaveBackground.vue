<template>
  <!--
    AiWaveBackground — 底部多色数据波浪效果

    多层 SVG 填充波浪叠加：
    - 第一层：深蓝（底层，最慢，12s）
    - 第二层：紫色（中层，10s）
    - 第三层：品红（中上层，9s）
    - 第四层：青蓝（中下层，8s）
    - 第五层：青绿（顶层，最快，7s）
    - 点阵粒子数据流
    - 占页面底部 20%-25% 高度
    - 配合多色渐变背景，增强色彩层次
  -->
  <div class="ai-wave" aria-hidden="true">
    <!-- SVG 波浪层 -->
    <div class="ai-wave__layers">
      <!-- Layer 1: 深蓝波浪 -->
      <svg
        class="ai-wave__svg ai-wave__svg--deepblue"
        viewBox="0 0 1440 200"
        preserveAspectRatio="none"
      >
        <path
          class="ai-wave__path"
          d="M0,120 C180,160 360,80 540,110 C720,140 900,170 1080,120 C1260,70 1380,90 1440,110 L1440,200 L0,200 Z"
        />
      </svg>

      <!-- Layer 2: 紫色波浪 -->
      <svg
        class="ai-wave__svg ai-wave__svg--purple"
        viewBox="0 0 1440 200"
        preserveAspectRatio="none"
      >
        <path
          class="ai-wave__path"
          d="M0,140 C150,100 300,170 480,130 C660,90 840,160 1020,120 C1200,80 1350,140 1440,120 L1440,200 L0,200 Z"
        />
      </svg>

      <!-- Layer 3: 品红波浪 -->
      <svg
        class="ai-wave__svg ai-wave__svg--magenta"
        viewBox="0 0 1440 200"
        preserveAspectRatio="none"
      >
        <path
          class="ai-wave__path"
          d="M0,130 C200,160 350,90 500,135 C650,180 800,110 960,145 C1120,180 1280,95 1440,125 L1440,200 L0,200 Z"
        />
      </svg>

      <!-- Layer 4: 青蓝波浪 -->
      <svg
        class="ai-wave__svg ai-wave__svg--cyan"
        viewBox="0 0 1440 200"
        preserveAspectRatio="none"
      >
        <path
          class="ai-wave__path"
          d="M0,155 C120,120 240,180 380,145 C520,110 660,165 800,135 C940,105 1080,150 1220,128 C1360,106 1400,140 1440,135 L1440,200 L0,200 Z"
        />
      </svg>

      <!-- Layer 5: 青绿波浪 -->
      <svg
        class="ai-wave__svg ai-wave__svg--teal"
        viewBox="0 0 1440 200"
        preserveAspectRatio="none"
      >
        <path
          class="ai-wave__path"
          d="M0,160 C100,140 220,175 360,150 C500,125 640,168 780,140 C920,112 1060,155 1200,132 C1340,109 1400,145 1440,140 L1440,200 L0,200 Z"
        />
      </svg>
    </div>

    <!-- 点阵粒子数据流 -->
    <canvas
      ref="dotsCanvasRef"
      class="ai-wave__dots"
      aria-hidden="true"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

// ---- 点阵粒子 ----
interface DotParticle {
  x: number
  y: number
  size: number
  opacity: number
  vx: number
  vy: number
  life: number
  maxLife: number
  // 颜色：淡蓝 / 淡紫 / 淡青
  r: number
  g: number
  b: number
}

// 点阵颜色方案
const DOT_COLORS = [
  { r: 140, g: 200, b: 240 },  // 淡蓝
  { r: 180, g: 170, b: 230 },  // 淡紫
  { r: 120, g: 210, b: 220 },  // 淡青
  { r: 200, g: 180, b: 225 },  // 淡紫蓝
  { r: 150, g: 215, b: 230 },  // 淡水蓝
]

const dotsCanvasRef = ref<HTMLCanvasElement | null>(null)
let dotsAnimId = 0
let dotParticles: DotParticle[] = []
let dotsWidth = 0
let dotsHeight = 0
let reducedMotion = false

function initDotParticles(): void {
  const count = reducedMotion ? 10 : 50
  dotParticles = Array.from({ length: count }, () => {
    const color = DOT_COLORS[Math.floor(Math.random() * DOT_COLORS.length)]
    return {
      x: Math.random() * dotsWidth,
      y: dotsHeight - Math.random() * dotsHeight * 0.6,
      size: 0.5 + Math.random() * 1.5,
      opacity: 0.1 + Math.random() * 0.25,
      vx: (Math.random() - 0.5) * 0.3,
      vy: -(0.1 + Math.random() * 0.3),
      life: 0,
      maxLife: 150 + Math.random() * 250,
      r: color.r,
      g: color.g,
      b: color.b,
    }
  })
}

function drawDots(ctx: CanvasRenderingContext2D): void {
  ctx.clearRect(0, 0, dotsWidth, dotsHeight)

  for (const p of dotParticles) {
    let fadeMultiplier = 1
    const fadeIn = 30
    const fadeOut = 40
    if (p.life < fadeIn) {
      fadeMultiplier = p.life / fadeIn
    } else if (p.life > p.maxLife - fadeOut) {
      fadeMultiplier = (p.maxLife - p.life) / fadeOut
    }

    const alpha = Math.max(0, p.opacity * fadeMultiplier)

    // 绘制多色光点
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(${p.r},${p.g},${p.b},${alpha})`
    ctx.fill()

    // 微光晕
    if (p.size > 0.8) {
      ctx.beginPath()
      ctx.arc(p.x, p.y, p.size * 3, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(${p.r},${p.g},${p.b},${alpha * 0.06})`
      ctx.fill()
    }
  }
}

function updateDots(): void {
  for (let i = dotParticles.length - 1; i >= 0; i--) {
    const p = dotParticles[i]
    p.x += p.vx
    p.y += p.vy
    p.life++

    if (p.life >= p.maxLife) {
      p.x = Math.random() * dotsWidth
      p.y = dotsHeight - Math.random() * dotsHeight * 0.3
      p.life = 0
      p.maxLife = 150 + Math.random() * 250
    }

    if (p.x < 0) p.x = dotsWidth
    if (p.x > dotsWidth) p.x = 0
    if (p.y < 0) {
      p.y = dotsHeight
      p.life = 0
    }
  }
}

function animateDots(): void {
  const canvas = dotsCanvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  if (!reducedMotion) {
    updateDots()
  }
  drawDots(ctx)
  dotsAnimId = requestAnimationFrame(animateDots)
}

function resizeDots(): void {
  const canvas = dotsCanvasRef.value
  if (!canvas) return

  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const waveHeight = window.innerHeight * 0.22
  dotsWidth = window.innerWidth
  dotsHeight = waveHeight

  canvas.width = dotsWidth * dpr
  canvas.height = dotsHeight * dpr
  canvas.style.width = `${dotsWidth}px`
  canvas.style.height = `${dotsHeight}px`

  const ctx = canvas.getContext('2d')
  if (ctx) {
    ctx.scale(dpr, dpr)
    initDotParticles()
  }
}

onMounted(() => {
  const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
  reducedMotion = mq.matches
  mq.addEventListener('change', (e) => {
    reducedMotion = e.matches
    resizeDots()
  })

  resizeDots()
  animateDots()
  window.addEventListener('resize', resizeDots)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(dotsAnimId)
  window.removeEventListener('resize', resizeDots)
})
</script>

<style lang="scss" scoped>
/* ============================================================
 * AiWaveBackground — 多色 AI 数据流波浪
 * 5 层 SVG 叠加：深蓝 → 紫 → 品红 → 青蓝 → 青绿
 * 配合背景多色渐变，形成完整的多色交替效果
 * ============================================================ */

.ai-wave {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 0;
  pointer-events: none;
  height: 22vh;
  min-height: 160px;
  max-height: 280px;
  overflow: hidden;
}

/* ---- 波浪图层容器 ---- */
.ai-wave__layers {
  position: absolute;
  bottom: 0;
  left: -2%;
  right: -2%;
  height: 100%;
}

.ai-wave__svg {
  position: absolute;
  bottom: 0;
  width: 104%;
  height: 100%;
  display: block;
}

.ai-wave__path {
  fill-opacity: 0.35;
}

/* ---- Layer 1: 深蓝波浪（底层，最慢） ---- */
.ai-wave__svg--deepblue {
  z-index: 1;

  .ai-wave__path {
    fill: rgba(16, 42, 114, 0.3);
  }

  animation: wave-drift-1 13s ease-in-out infinite;
}

/* ---- Layer 2: 紫色波浪 ---- */
.ai-wave__svg--purple {
  z-index: 2;

  .ai-wave__path {
    fill: rgba(114, 52, 216, 0.28);
  }

  animation: wave-drift-2 11s ease-in-out infinite;
}

/* ---- Layer 3: 品红波浪 ---- */
.ai-wave__svg--magenta {
  z-index: 3;

  .ai-wave__path {
    fill: rgba(179, 54, 217, 0.22);
  }

  animation: wave-drift-3 9s ease-in-out infinite;
}

/* ---- Layer 4: 青蓝波浪 ---- */
.ai-wave__svg--cyan {
  z-index: 4;

  .ai-wave__path {
    fill: rgba(8, 168, 200, 0.24);
  }

  animation: wave-drift-4 8s ease-in-out infinite;
}

/* ---- Layer 5: 青绿波浪（顶层，最快） ---- */
.ai-wave__svg--teal {
  z-index: 5;

  .ai-wave__path {
    fill: rgba(24, 184, 160, 0.18);
  }

  animation: wave-drift-5 7s ease-in-out infinite;
}

/* ---- 波浪动画关键帧 ---- */
@keyframes wave-drift-1 {
  0%, 100% {
    transform: translateX(0) translateY(0) scaleX(1);
  }
  25% {
    transform: translateX(-15px) translateY(-6px) scaleX(1.03);
  }
  50% {
    transform: translateX(10px) translateY(-3px) scaleX(0.98);
  }
  75% {
    transform: translateX(-8px) translateY(-8px) scaleX(1.02);
  }
}

@keyframes wave-drift-2 {
  0%, 100% {
    transform: translateX(0) translateY(0) scaleX(1);
  }
  33% {
    transform: translateX(14px) translateY(-5px) scaleX(1.02);
  }
  66% {
    transform: translateX(-12px) translateY(-7px) scaleX(0.97);
  }
}

@keyframes wave-drift-3 {
  0%, 100% {
    transform: translateX(0) translateY(0) scaleX(1);
  }
  30% {
    transform: translateX(-10px) translateY(-4px) scaleX(1.015);
  }
  60% {
    transform: translateX(8px) translateY(-6px) scaleX(0.985);
  }
}

@keyframes wave-drift-4 {
  0%, 100% {
    transform: translateX(0) translateY(0) scaleX(1);
  }
  50% {
    transform: translateX(-8px) translateY(-3px) scaleX(1.01);
  }
}

@keyframes wave-drift-5 {
  0%, 100% {
    transform: translateX(0) translateY(0) scaleX(1);
  }
  50% {
    transform: translateX(6px) translateY(-5px) scaleX(1.008);
  }
}

/* ---- 点阵粒子 Canvas ---- */
.ai-wave__dots {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 6;
}

/* ============================================================
 * 性能与无障碍
 * ============================================================ */

@media (prefers-reduced-motion: reduce) {
  .ai-wave__svg {
    animation: none;
  }
}

/* 移动端：降低波浪高度 */
@media (max-width: 768px) {
  .ai-wave {
    height: 16vh;
    min-height: 100px;
  }
}
</style>
