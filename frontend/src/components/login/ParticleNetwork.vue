<template>
  <!--
    ParticleNetwork — 自定义 AI 粒子网络

    不依赖 tsParticles 默认效果，使用原生 Canvas 实现：
    - 40-80 个粒子（根据屏幕尺寸/性能动态调整）
    - 白色 + 浅蓝色、低透明度
    - 缓慢运动、弱连接线
    - 尊重 prefers-reduced-motion
  -->
  <canvas
    ref="canvasRef"
    class="particle-canvas"
    aria-hidden="true"
  />
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

// ---- 粒子接口 ----
interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  size: number
  color: string
  opacity: number
}

// ---- 配置 ----
const COLORS = [
  'rgba(255, 255, 255, var-alpha)',
  'rgba(180, 200, 240, var-alpha)',
  'rgba(140, 170, 230, var-alpha)',
  'rgba(200, 220, 255, var-alpha)',
]

const canvasRef = ref<HTMLCanvasElement | null>(null)
let animationId = 0
let particles: Particle[] = []
let reducedMotion = false

// ---- 根据屏幕/性能计算粒子数量 ----
function getParticleCount(): number {
  const width = window.innerWidth
  const height = window.innerHeight
  const area = width * height

  // 低性能设备标记（通过硬件并发数粗略判断）
  const lowPerf = navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 4
  const isMobile = width < 768

  if (reducedMotion) return 15
  if (lowPerf || isMobile) return 40
  if (area > 2000000) return 80 // 2K+ 屏幕
  if (area > 1000000) return 65 // 1080p+
  return 50
}

// ---- 初始化粒子 ----
function initParticles(ctx: CanvasRenderingContext2D): void {
  const count = getParticleCount()
  const { width, height } = ctx.canvas

  particles = Array.from({ length: count }, () => {
    const baseColor = COLORS[Math.floor(Math.random() * COLORS.length)]
    const alpha = (0.2 + Math.random() * 0.3).toFixed(2) // 0.2 ~ 0.5
    return {
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.3, // 慢速运动
      vy: (Math.random() - 0.5) * 0.3,
      size: 0.8 + Math.random() * 1.8, // 0.8 ~ 2.6px
      color: baseColor.replace('var-alpha', alpha),
      opacity: parseFloat(alpha),
    }
  })
}

// ---- 绘制 ----
function draw(ctx: CanvasRenderingContext2D): void {
  const { width, height } = ctx.canvas

  ctx.clearRect(0, 0, width, height)

  // 绘制连线（弱连接）
  ctx.lineWidth = 0.3
  for (let i = 0; i < particles.length; i++) {
    for (let j = i + 1; j < particles.length; j++) {
      const dx = particles[i].x - particles[j].x
      const dy = particles[i].y - particles[j].y
      const dist = Math.sqrt(dx * dx + dy * dy)
      const maxDist = 130

      if (dist < maxDist) {
        const alpha = (1 - dist / maxDist) * 0.08 // 极弱的连线
        ctx.strokeStyle = `rgba(140, 180, 230, ${alpha})`
        ctx.beginPath()
        ctx.moveTo(particles[i].x, particles[i].y)
        ctx.lineTo(particles[j].x, particles[j].y)
        ctx.stroke()
      }
    }
  }

  // 绘制粒子
  for (const p of particles) {
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
    ctx.fillStyle = p.color
    ctx.fill()
  }
}

// ---- 更新位置 ----
function update(ctx: CanvasRenderingContext2D): void {
  const { width, height } = ctx.canvas

  for (const p of particles) {
    p.x += p.vx
    p.y += p.vy

    // 边界反弹（柔和回绕）
    if (p.x < -20) p.x = width + 20
    if (p.x > width + 20) p.x = -20
    if (p.y < -20) p.y = height + 20
    if (p.y > height + 20) p.y = -20
  }
}

// ---- 动画循环 ----
function animate(): void {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  if (!reducedMotion) {
    update(ctx)
  }
  draw(ctx)
  animationId = requestAnimationFrame(animate)
}

// ---- 尺寸调整 ----
function resize(): void {
  const canvas = canvasRef.value
  if (!canvas) return

  const dpr = Math.min(window.devicePixelRatio || 1, 2) // 限制 DPR 保护性能
  canvas.width = window.innerWidth * dpr
  canvas.height = window.innerHeight * dpr
  canvas.style.width = `${window.innerWidth}px`
  canvas.style.height = `${window.innerHeight}px`

  const ctx = canvas.getContext('2d')
  if (ctx) {
    ctx.scale(dpr, dpr)
    initParticles(ctx)
  }
}

// ---- 生命周期 ----
onMounted(() => {
  const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
  reducedMotion = mq.matches
  mq.addEventListener('change', (e) => {
    reducedMotion = e.matches
    resize()
  })

  resize()
  animate()
  window.addEventListener('resize', resize)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(animationId)
  window.removeEventListener('resize', resize)
})
</script>

<style lang="scss" scoped>
.particle-canvas {
  position: fixed;
  inset: 0;
  z-index: 1;
  pointer-events: none;
}
</style>
