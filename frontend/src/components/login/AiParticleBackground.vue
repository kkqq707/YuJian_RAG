<template>
  <!--
    AiParticleBackground — AI 粒子网络背景

    使用原生 Canvas 实现：
    - 80-120 个粒子（根据屏幕/性能动态调整）
    - 白色为主 + 淡蓝/淡紫/淡青/极少量淡粉
    - 部分粒子颜色缓慢渐变
    - 缓慢漂浮 + 粒子间自动连接
    - 鼠标移动产生轻微吸引效果
    - 粒子呼吸效果（大小/透明度周期性变化）
    - 尊重 prefers-reduced-motion
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
  // 颜色相关
  r: number
  g: number
  b: number
  targetR: number
  targetG: number
  targetB: number
  baseOpacity: number
  opacity: number
  breathPhase: number
  breathSpeed: number
  // 颜色渐变速度
  colorShiftSpeed: number
}

// ---- 配置 ----
// 基础颜色：白色为主，淡蓝/淡紫/淡青/淡粉为辅
const BASE_COLORS = [
  { r: 255, g: 255, b: 255, weight: 5 },   // 白色（高权重，占多数）
  { r: 240, g: 245, b: 255, weight: 3 },    // 冷白
  { r: 180, g: 210, b: 240, weight: 2 },    // 淡蓝
  { r: 200, g: 220, b: 250, weight: 2 },    // 浅蓝白
  { r: 160, g: 200, b: 235, weight: 2 },    // 柔和蓝
  { r: 200, g: 185, b: 235, weight: 1.5 },  // 淡紫
  { r: 180, g: 210, b: 240, weight: 1 },    // 淡青
  { r: 235, g: 200, b: 230, weight: 0.5 },  // 极淡粉（极少量）
]

// 颜色目标池（粒子会缓慢变向这些颜色）
const COLOR_TARGETS = [
  { r: 200, g: 220, b: 250 },  // 淡蓝
  { r: 210, g: 195, b: 240 },  // 淡紫
  { r: 185, g: 215, b: 245 },  // 淡青
  { r: 240, g: 210, b: 235 },  // 淡粉
]

// 加权随机选择基础颜色
function pickBaseColor(): { r: number; g: number; b: number } {
  const totalWeight = BASE_COLORS.reduce((sum, c) => sum + c.weight, 0)
  let rand = Math.random() * totalWeight
  for (const c of BASE_COLORS) {
    rand -= c.weight
    if (rand <= 0) return { r: c.r, g: c.g, b: c.b }
  }
  return BASE_COLORS[0]
}

const canvasRef = ref<HTMLCanvasElement | null>(null)
let animationId = 0
let particles: Particle[] = []
let mouseX = -9999
let mouseY = -9999
let mouseActive = false
let reducedMotion = false
let width = 0
let height = 0
let resizeTimer: ReturnType<typeof setTimeout> | null = null
let pageVisible = true

// ---- 粒子数量计算 ----
function getParticleCount(): number {
  const w = window.innerWidth
  const h = window.innerHeight
  const area = w * h
  const lowPerf = navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 4
  const isMobile = w < 768
  const isTablet = w >= 768 && w < 1200

  if (reducedMotion) return 15
  if (lowPerf) return isMobile ? 30 : isTablet ? 45 : 60
  if (isMobile) return 40
  if (isTablet) return 65
  if (area > 2500000) return 120
  if (area > 1500000) return 100
  if (area > 1000000) return 90
  return 80
}

// ---- 初始化粒子 ----
function initParticles(): void {
  const count = getParticleCount()
  particles = Array.from({ length: count }, () => {
    const baseColor = pickBaseColor()
    const targetColor = COLOR_TARGETS[Math.floor(Math.random() * COLOR_TARGETS.length)]
    const baseOpacity = 0.2 + Math.random() * 0.4
    const baseSize = 0.8 + Math.random() * 2.0
    return {
      x: Math.random() * width,
      y: Math.random() * height,
      baseX: 0,
      baseY: 0,
      vx: (Math.random() - 0.5) * 0.2,
      vy: (Math.random() - 0.5) * 0.2,
      baseSize,
      size: baseSize,
      r: baseColor.r,
      g: baseColor.g,
      b: baseColor.b,
      targetR: targetColor.r,
      targetG: targetColor.g,
      targetB: targetColor.b,
      baseOpacity,
      opacity: baseOpacity,
      breathPhase: Math.random() * Math.PI * 2,
      breathSpeed: 0.003 + Math.random() * 0.005,
      colorShiftSpeed: 0.0005 + Math.random() * 0.002,  // 颜色变化速度
    }
  })
}

// ---- 颜色插值 ----
function lerpColor(a: number, b: number, t: number): number {
  return Math.round(a + (b - a) * t)
}

// ---- 更新粒子颜色（缓慢向目标颜色渐变，到达后切换目标） ----
function updateParticleColors(): void {
  for (const p of particles) {
    // 线性插值当前颜色 → 目标颜色
    p.r = lerpColor(p.r, p.targetR, p.colorShiftSpeed)
    p.g = lerpColor(p.g, p.targetG, p.colorShiftSpeed)
    p.b = lerpColor(p.b, p.targetB, p.colorShiftSpeed)

    // 接近目标时，随机切换到新目标
    const diffR = Math.abs(p.r - p.targetR)
    const diffG = Math.abs(p.g - p.targetG)
    const diffB = Math.abs(p.b - p.targetB)

    if (diffR < 3 && diffG < 3 && diffB < 3) {
      const newTarget = COLOR_TARGETS[Math.floor(Math.random() * COLOR_TARGETS.length)]
      p.targetR = newTarget.r
      p.targetG = newTarget.g
      p.targetB = newTarget.b
      p.colorShiftSpeed = 0.0005 + Math.random() * 0.002
    }
  }
}

// ---- 绘制 ----
function draw(ctx: CanvasRenderingContext2D): void {
  ctx.clearRect(0, 0, width, height)

  if (reducedMotion) {
    for (const p of particles) {
      ctx.beginPath()
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(${p.r},${p.g},${p.b},${p.opacity})`
      ctx.fill()
    }
    return
  }

  // ---- 粒子间连线 ----
  const maxDist = 140
  ctx.lineWidth = 0.25
  for (let i = 0; i < particles.length; i++) {
    for (let j = i + 1; j < particles.length; j++) {
      const dx = particles[i].x - particles[j].x
      const dy = particles[i].y - particles[j].y
      const dist = Math.sqrt(dx * dx + dy * dy)

      if (dist < maxDist) {
        const alpha = (1 - dist / maxDist) * 0.06
        // 连线颜色使用两个粒子颜色的混合
        const mr = Math.round((particles[i].r + particles[j].r) / 2)
        const mg = Math.round((particles[i].g + particles[j].g) / 2)
        const mb = Math.round((particles[i].b + particles[j].b) / 2)
        ctx.strokeStyle = `rgba(${mr},${mg},${mb},${alpha})`
        ctx.beginPath()
        ctx.moveTo(particles[i].x, particles[i].y)
        ctx.lineTo(particles[j].x, particles[j].y)
        ctx.stroke()
      }
    }
  }

  // ---- 绘制粒子 ----
  for (const p of particles) {
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(${p.r},${p.g},${p.b},${p.opacity})`
    ctx.fill()

    // 微光晕（较大粒子才有）
    if (p.size > 1.5) {
      ctx.beginPath()
      ctx.arc(p.x, p.y, p.size * 2.5, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(${p.r},${p.g},${p.b},${p.opacity * 0.06})`
      ctx.fill()
    }
  }
}

// ---- 更新 ----
function update(): void {
  const mouseInfluenceRadius = 180
  const mouseAttractForce = 0.015

  // 更新粒子颜色渐变
  updateParticleColors()

  for (const p of particles) {
    // 呼吸效果
    p.breathPhase += p.breathSpeed
    const breathFactor = 1 + Math.sin(p.breathPhase) * 0.25
    p.size = p.baseSize * breathFactor
    p.opacity = Math.min(0.65, Math.max(0.15, p.baseOpacity * breathFactor))

    // 基础漂移
    p.x += p.vx
    p.y += p.vy

    // 鼠标吸引
    if (mouseActive) {
      const dx = mouseX - p.x
      const dy = mouseY - p.y
      const dist = Math.sqrt(dx * dx + dy * dy)

      if (dist < mouseInfluenceRadius && dist > 10) {
        const force = (1 - dist / mouseInfluenceRadius) * mouseAttractForce
        p.vx += dx / dist * force * 0.1
        p.vy += dy / dist * force * 0.1
      }

      p.vx *= 0.995
      p.vy *= 0.995

      const maxSpeed = 0.5
      const speed = Math.sqrt(p.vx * p.vx + p.vy * p.vy)
      if (speed > maxSpeed) {
        p.vx = (p.vx / speed) * maxSpeed
        p.vy = (p.vy / speed) * maxSpeed
      }
    }

    // 边界回绕
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

// ---- 尺寸调整（防抖） ----
function resize(): void {
  // 清除上一次的定时器，避免频繁重建粒子
  if (resizeTimer) {
    clearTimeout(resizeTimer)
  }

  resizeTimer = setTimeout(() => {
    const canvas = canvasRef.value
    if (!canvas) return

    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    const newWidth = window.innerWidth
    const newHeight = window.innerHeight

    // 尺寸没变化则跳过
    if (newWidth === width && newHeight === height) return

    width = newWidth
    height = newHeight
    canvas.width = width * dpr
    canvas.height = height * dpr
    canvas.style.width = `${width}px`
    canvas.style.height = `${height}px`

    const ctx = canvas.getContext('2d')
    if (ctx) {
      ctx.scale(dpr, dpr)
      initParticles()
    }

    resizeTimer = null
  }, 150)
}

// ---- 页面可见性 ----
function onVisibilityChange(): void {
  pageVisible = document.visibilityState === 'visible'
  if (!pageVisible) {
    // 页面隐藏时暂停动画
    if (animationId) {
      cancelAnimationFrame(animationId)
      animationId = 0
    }
  } else {
    // 页面重新可见时恢复动画
    if (!animationId) {
      animate()
    }
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
  document.addEventListener('visibilitychange', onVisibilityChange)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(animationId)
  if (resizeTimer) {
    clearTimeout(resizeTimer)
    resizeTimer = null
  }
  window.removeEventListener('resize', resize)
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseleave', onMouseLeave)
  document.removeEventListener('visibilitychange', onVisibilityChange)
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
