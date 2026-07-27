<template>
  <button
    class="glow-button"
    :class="{
      'is-loading': loading,
      'is-disabled': disabled,
      'is-block': block,
    }"
    :disabled="disabled || loading"
    :type="type"
    @click="handleClick"
  >
    <!-- 按钮微光层 -->
    <span class="glow-button__aura" />
    <!-- loading: AI 旋转环 -->
    <span v-if="loading" class="glow-button__loading">
      <span class="ai-ring" />
      <span class="ai-ring ai-ring--inner" />
    </span>
    <span v-else class="glow-button__text">
      <slot />
    </span>
  </button>
</template>

<script setup lang="ts">
defineProps<{
  loading?: boolean
  disabled?: boolean
  block?: boolean
  type?: 'button' | 'submit'
}>()

const emit = defineEmits<{
  click: []
}>()

function handleClick(e: MouseEvent) {
  const btn = e.currentTarget as HTMLElement
  const ripple = document.createElement('span')
  const rect = btn.getBoundingClientRect()
  const size = Math.max(rect.width, rect.height)
  ripple.style.cssText = `
    position: absolute;
    width: ${size}px;
    height: ${size}px;
    left: ${e.clientX - rect.left - size / 2}px;
    top: ${e.clientY - rect.top - size / 2}px;
    border-radius: 50%;
    background: rgba(255,255,255,0.25);
    pointer-events: none;
    animation: ripple-out 0.6s ease-out forwards;
  `
  ripple.className = 'glow-button__ripple'
  btn.appendChild(ripple)
  ripple.addEventListener('animationend', () => ripple.remove())

  emit('click')
}
</script>

<style lang="scss" scoped>
.glow-button {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 48px;
  padding: 0 36px;
  font-size: 15px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #4F7FF5 0%, #7B6AE8 50%, #8C64DC 100%);
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  letter-spacing: 4px;
  overflow: hidden;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    filter 0.2s ease;
  isolation: isolate;

  /* Hover: 轻微上浮 */
  &:hover:not(:disabled):not(.is-loading) {
    transform: translateY(-1px);
    filter: brightness(1.06);
    box-shadow:
      0 6px 24px rgba(79, 127, 245, 0.25),
      0 0 60px rgba(123, 106, 232, 0.12);
  }

  /* Active: 归位 + 微收缩 */
  &:active:not(:disabled):not(.is-loading) {
    transform: translateY(0) scale(0.98);
    filter: brightness(0.97);
  }

  &.is-block {
    width: 100%;
  }

  &.is-disabled {
    opacity: 0.4;
    cursor: not-allowed;
    filter: grayscale(0.2);
  }

  &.is-loading {
    cursor: wait;
    opacity: 0.85;
  }
}

/* 按钮光晕 — 仅 hover 时可见 */
.glow-button__aura {
  position: absolute;
  inset: -2px;
  border-radius: calc(var(--radius-md) + 2px);
  background: linear-gradient(135deg, rgba(122, 158, 232, 0.3), rgba(167, 139, 250, 0.3));
  z-index: -1;
  opacity: 0;
  transition: opacity 0.3s ease;
  filter: blur(10px);
}

.glow-button:hover:not(:disabled):not(.is-loading) .glow-button__aura {
  opacity: 0.6;
}

.glow-button__text {
  position: relative;
  z-index: 1;
}

/* AI 旋转 loading */
.glow-button__loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.ai-ring {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.25);
  border-top-color: #fff;
  animation: ai-spin 1s linear infinite;

  &--inner {
    width: 12px;
    height: 12px;
    border-width: 1.5px;
    animation-duration: 0.65s;
    animation-direction: reverse;
    position: absolute;
  }
}

@keyframes ai-spin {
  to { transform: rotate(360deg); }
}

/* 点击波纹 */
:global(.glow-button__ripple) {
  animation: ripple-out 0.6s ease-out forwards;
}

@keyframes ripple-out {
  0% {
    transform: scale(0);
    opacity: 1;
  }
  100% {
    transform: scale(4);
    opacity: 0;
  }
}
</style>
