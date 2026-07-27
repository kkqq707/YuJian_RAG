<template>
  <!--
    AiParticleBackground — AI 粒子网络背景

    使用原生 Canvas 实现：
    - 80-120 个粒子（根据屏幕/性能动态调整）
    - 白色 + 淡蓝色，透明度 0.2-0.6
    - 缓慢漂浮 + 粒子间自动连接
    - 鼠标移动产生轻微吸引效果
    - 粒子呼吸效果（大小/透明度周期性变化）
    - 尊重 prefers-reduced-motion
    - 禁止：蜘蛛网过密、高速运动
  -->
  <canvas
    ref="canvasRef"
    class="ai-particle-canvas"
    aria-hidden="true"
  />
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

// ---- 类型 ----
interface Particle {
  x: number
  y: number
  baseX: number
  baseY: number
  vx: number
  vy: number
  baseSize: number
  size: number
  color: string
  baseOpacity: number
  opacity: number
  breathPhase: number     // 呼吸相位
  breathSpeed: number     // 呼吸速度
}

// ---- 配置 ----
const PARTICLE_COLORS = [
  { r: 255, g: 255, b: 255 },  // 白色
  { r: 180, g: 210, b: 240 },  // 淡蓝
  { r: 200, g: 220, b: 250 },  // 浅蓝白
  { r: 160, g: 200, b: 235 },  // 柔和蓝
]

const canvasRef = ref<HTMLCanvasElement | null>(null)
let animationId = 0
let particles: Particle[] = []
let mouseX = -9999
let mouseY = -9999
let mouseActive = false
let reducedMotion = false
let width = 0
let height = 0

// ---- 粒子数量计算 ----
function getParticleCount(): number {
  const w = window.innerWidth
  const h = window.innerHeight
  const area = w * h
  const lowPerf = navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 4
  const isMobile = w < 768

  if (reducedMotion) return 15
  if (lowPerf || isMobile) return 60
  if (area > 2500000) return 120  // 2K+
  if (area > 1500000) return 100  // 1440p+
  if (area > 1000000) return 90   // 1080p+
  return 80
}

// ---- 初始化粒子 ----
function initParticles(): void {
  const count = getParticleCount()
  particles = Array.from({ length: count }, () => {
    const colorDef = PARTICLE_COLORS[Math.floor(Math.random() * PARTICLE_COLORS.length)]
    const baseOpacity = 0.2 + Math.random() * 0.4  // 0.2 ~ 0.6
    const baseSize = 0.8 + Math.random() * 2.0      // 0.8 ~ 2.8px
    return {
      x: Math.random() * width,
      y: Math.random() * height,
      baseX: 0,
      baseY: 0,
      vx: (Math.random() - 0.5) * 0.2,   // 极慢速
      vy: (Math.random() - 0.5) * 0.2,
      baseSize,
      size: baseSize,
      color: `rgba(${colorDef.r},${colorDef.g},${colorDef.b},${baseOpacity.toFixed(2)})`,
      baseOpacity,
      opacity: baseOpacity,
      breathPhase: Math.random() * Math.PI * 2,
      breathSpeed: 0.003 + Math.random() * 0.005,  // 呼吸速度（很慢）
    }
  })
}

// ---- 绘制 ----
function draw(ctx: CanvasRenderingContext2D): void {
  ctx.clearRect(0, 0, width, height)

  if (reducedMotion) {
    // 简化绘制：仅画粒子，无连线
    for (const p of particles) {
      ctx.beginPath()
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
      ctx.fillStyle = p.color
      ctx.fill()
    }
    return
  }

  // ---- 连线（弱连接，最大距离 140px） ----
  const maxDist = 140
  ctx.lineWidth = 0.25
  for (let i = 0; i < particles.length; i++) {
    for (let j = i + 1; j < particles.length; j++) {
      const dx = particles[i].x - particles[j].x
      const dy = particles[i].y - particles[j].y
      const dist = Math.sqrt(dx * dx + dy * dy)

      if (dist < maxDist) {
        const alpha = (1 - dist / maxDist) * 0.06  // 极弱
        ctx.strokeStyle = `rgba(140,180,230,${alpha})`
        ctx.beginPath()
        ctx.moveTo(particles[i].x, particles[i].y)
        ctx.lineTo(particles[j].x, particles[j].y)
        ctx.stroke()
      }
    }
  }

  // ---- 粒子 ----
  for (const p of particles) {
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(${getColorString(p)}, ${p.opacity})`
    ctx.fill()

    // 微光晕
    if (p.size > 1.5) {
      ctx.beginPath()
      ctx.arc(p.x, p.y, p.size * 2.5, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(${getColorString(p)}, ${p.opacity * 0.08})`
      ctx.fill()
    }
  }
}

function getColorString(p: Particle): string {
  // 从 rgba 字符串中提取 RGB 部分
  const match = p.color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
  if (match) {
    return `${match[1]},${match[2]},${match[3]}`
  }
  return '180,210,240'
}

// ---- 更新（含呼吸 + 鼠标吸引） ----
function update(): void {
  const mouseInfluenceRadius = 180
  const mouseAttractForce = 0.015

  for (const p of particles) {
    // 呼吸效果：大小和透明度周期性变化
    p.breathPhase += p.breathSpeed
    const breathFactor = 1 + Math.sin(p.breathPhase) * 0.25  // ±25% 变化
    p.size = p.baseSize * breathFactor
    p.opacity = Math.min(0.65, Math.max(0.15, p.baseOpacity * breathFactor))

    // 基础漂移
    p.x += p.vx
    p.y += p.vy

    // 鼠标吸引效果
    if (mouseActive) {
      const dx = mouseX - p.x
      const dy = mouseY - p.y
      const dist = Math.sqrt(dx * dx + dy * dy)

      if (dist < mouseInfluenceRadius && dist > 10) {
        const force = (1 - dist / mouseInfluenceRadius) * mouseAttractForce
        p.vx += dx / dist * force * 0.1
        p.vy += dy / dist * force * 0.1
      }

      // 速度阻尼
      p.vx *= 0.995
      p.vy *= 0.995

      // 速度上限
      const maxSpeed = 0.5
      const speed = Math.sqrt(p.vx * p.vx + p.vy * p.vy)
      if (speed > maxSpeed) {
        p.vx = (p.vx / speed) * maxSpeed
        p.vy = (p.vy / speed) * maxSpeed
      }
    }

    // 边界回绕（柔和）
    const margin = 30
    if (p.x < -margin) p.x = width + margin
    if (p.x > width + margin) p.x = -margin
    if (p.y < -margin) p.y = height + margin
    if (p.y > height + margin) p.y = -margin
  }
}

// ---- 动画循环 ----
function animate(): void {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  if (!reducedMotion) {
    update()
  }
  draw(ctx)
  animationId = requestAnimationFrame(animate)
}

// ---- 尺寸调整 ----
function resize(): void {
  const canvas = canvasRef.value
  if (!canvas) return

  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  width = window.innerWidth
  height = window.innerHeight
  canvas.width = width * dpr
  canvas.height = height * dpr
  canvas.style.width = `${width}px`
  canvas.style.height = `${height}px`

  const ctx = canvas.getContext('2d')
  if (ctx) {
    ctx.scale(dpr, dpr)
    initParticles()
  }
}

// ---- 鼠标事件 ----
function onMouseMove(e: MouseEvent): void {
  mouseX = e.clientX
  mouseY = e.clientY
  mouseActive = true
}

function onMouseLeave(): void {
  mouseActive = false
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
  window.addEventListener('mousemove', onMouseMove, { passive: true })
  window.addEventListener('mouseleave', onMouseLeave)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(animationId)
  window.removeEventListener('resize', resize)
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseleave', onMouseLeave)
})
</script>

<style lang="scss" scoped>
.ai-particle-canvas {
  position: fixed;
  inset: 0;
  z-index: 1;
  pointer-events: none;
}
</style>
