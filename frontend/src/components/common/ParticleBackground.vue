<template>
  <div class="particle-container" aria-hidden="true">
    <vue-particles
      :id="id"
      :options="particleOptions"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

defineProps<{ id: string }>()

const prefersReducedMotion = ref(false)
const isMobile = ref(false)

onMounted(() => {
  const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
  prefersReducedMotion.value = mq.matches
  mq.addEventListener('change', (e) => { prefersReducedMotion.value = e.matches })

  const mm = window.matchMedia('(max-width: 768px)')
  isMobile.value = mm.matches
  mm.addEventListener('change', (e) => { isMobile.value = e.matches })
})

const particleOptions = computed(() => {
  const reduced = prefersReducedMotion.value
  const mobile = isMobile.value

  return {
    fpsLimit: reduced ? 30 : 60,
    particles: {
      number: {
        value: reduced ? 15 : mobile ? 35 : 60,
        density: { enable: true },
      },
      color: {
        value: ['#5078DC', '#8C64DC', '#7A9EE8', '#A78BFA'],
      },
      opacity: {
        value: reduced ? 0.2 : { min: 0.2, max: 0.45 },
        animation: reduced
          ? { enable: false }
          : { enable: true, speed: 0.3, minimumValue: 0.08, sync: false },
      },
      size: {
        value: { min: 1, max: 2.5 },
        animation: reduced
          ? { enable: false }
          : { enable: true, speed: 1, minimumValue: 0.5, sync: false },
      },
      links: {
        enable: !reduced,
        color: 'rgba(100, 140, 220, 0.12)',
        distance: 130,
        opacity: 0.12,
        width: 0.4,
      },
      move: {
        enable: !reduced,
        speed: 0.3,
        direction: 'none' as const,
        random: true,
        straight: false,
        outModes: { default: 'bounce' as const },
      },
    },
    interactivity: {
      events: {
        onHover: {
          enable: !reduced,
          mode: 'grab',
        },
      },
      modes: {
        grab: {
          distance: 160,
          links: {
            opacity: 0.2,
            color: '#8C64DC',
          },
        },
      },
    },
    detectRetina: true,
    background: { color: 'transparent' },
    fullScreen: false,
  }
})
</script>

<style lang="scss" scoped>
.particle-container {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;

  :deep(canvas) {
    pointer-events: auto;
  }
}
</style>
