<template>
  <!--
    AiWaveBackground — 底部 AI 数据波浪效果

    多层 SVG 填充波浪叠加：
    - 第一层：紫色（底层，最慢）
    - 第二层：蓝色（中层）
    - 第三层：青色（顶层，最快）
    - 点阵粒子数据流
    - 占页面底部 20%-25% 高度
    - 8-15 秒循环动画
    - 不遮挡内容
  -->
  <div class="ai-wave" aria-hidden="true">
    <!-- SVG 波浪层 -->
    <div class="ai-wave__layers">
      <svg
        class="ai-wave__svg ai-wave__svg--purple"
        viewBox="0 0 1440 200"
        preserveAspectRatio="none"
      >
        <path
          class="ai-wave__path"
          d="M0,120 C180,160 360,80 540,110 C720,140 900,170 1080,120 C1260,70 1380,90 1440,110 L1440,200 L0,200 Z"
        />
      </svg>

      <svg
        class="ai-wave__svg ai-wave__svg--blue"
        viewBox="0 0 1440 200"
        preserveAspectRatio="none"
      >
        <path
          class="ai-wave__path"
          d="M0,140 C150,100 300,170 480,130 C660,90 840,160 1020,120 C1200,80 1350,140 1440,120 L1440,200 L0,200 Z"
        />
      </svg>

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
}

const dotsCanvasRef = ref<HTMLCanvasElement | null>(null)
let dotsAnimId = 0
let dotParticles: DotParticle[] = []
let dotsWidth = 0
let dotsHeight = 0
let reducedMotion = false

function initDotParticles(): void {
  const count = reducedMotion ? 10 : 50
  dotParticles = Array.from({ length: count }, () => ({
    x: Math.random() * dotsWidth,
    y: dotsHeight - Math.random() * dotsHeight * 0.6, // 集中在波浪区域
    size: 0.5 + Math.random() * 1.5,
    opacity: 0.1 + Math.random() * 0.25,
    vx: (Math.random() - 0.5) * 0.3,
    vy: -(0.1 + Math.random() * 0.3), // 向上浮动
    life: 0,
    maxLife: 150 + Math.random() * 250,
  }))
}

function drawDots(ctx: CanvasRenderingContext2D): void {
  ctx.clearRect(0, 0, dotsWidth, dotsHeight)

  for (const p of dotParticles) {
    // 生命周期：淡入 → 保持 → 淡出
    let fadeMultiplier = 1
    const fadeIn = 30
    const fadeOut = 40
    if (p.life < fadeIn) {
      fadeMultiplier = p.life / fadeIn
    } else if (p.life > p.maxLife - fadeOut) {
      fadeMultiplier = (p.maxLife - p.life) / fadeOut
    }

    const alpha = Math.max(0, p.opacity * fadeMultiplier)

    // 绘制光点
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(140,200,240,${alpha})`
    ctx.fill()

    // 微光晕
    if (p.size > 0.8) {
      ctx.beginPath()
      ctx.arc(p.x, p.y, p.size * 3, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(80,180,230,${alpha * 0.06})`
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

    // 生命周期结束 → 重置
    if (p.life >= p.maxLife) {
      p.x = Math.random() * dotsWidth
      p.y = dotsHeight - Math.random() * dotsHeight * 0.3
      p.life = 0
      p.maxLife = 150 + Math.random() * 250
    }

    // 边界处理
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

// ---- 生命周期 ----
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
 * AiWaveBackground — AI 数据流波浪
 * ============================================================ */

.ai-wave {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 0;
  pointer-events: none;
  height: 22vh;          /* 页面 22% 高度 */
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

/* ---- 第一层：紫色波浪（底层，最慢） ---- */
.ai-wave__svg--purple {
  z-index: 1;

  .ai-wave__path {
    fill: rgba(138, 43, 226, 0.28);
  }

  animation: wave-drift-1 12s ease-in-out infinite;
}

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

/* ---- 第二层：蓝色波浪（中层） ---- */
.ai-wave__svg--blue {
  z-index: 2;

  .ai-wave__path {
    fill: rgba(40, 53, 147, 0.32);
  }

  animation: wave-drift-2 10s ease-in-out infinite;
}

@keyframes wave-drift-2 {
  0%, 100% {
    transform: translateX(0) translateY(0) scaleX(1);
  }
  33% {
    transform: translateX(12px) translateY(-5px) scaleX(1.02);
  }
  66% {
    transform: translateX(-10px) translateY(-7px) scaleX(0.97);
  }
}

/* ---- 第三层：青色波浪（顶层，最快） ---- */
.ai-wave__svg--cyan {
  z-index: 3;

  .ai-wave__path {
    fill: rgba(0, 207, 255, 0.22);
  }

  animation: wave-drift-3 8s ease-in-out infinite;
}

@keyframes wave-drift-3 {
  0%, 100% {
    transform: translateX(0) translateY(0) scaleX(1);
  }
  50% {
    transform: translateX(-8px) translateY(-4px) scaleX(1.01);
  }
}

/* ---- 点阵粒子 Canvas ---- */
.ai-wave__dots {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 4;
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
