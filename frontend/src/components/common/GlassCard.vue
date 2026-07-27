<template>
  <div class="glass-card" :class="{ 'no-padding': !padding, 'no-hover': !hoverable }">
    <!-- 顶部微光线 -->
    <div class="glass-card__shine" />
    <!-- 边缘发光 -->
    <div class="glass-card__glow" />
    <div class="glass-card__content">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  padding?: boolean
  hoverable?: boolean
}>(), {
  padding: true,
  hoverable: true,
})
</script>

<style lang="scss" scoped>
.glass-card {
  position: relative;
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(30px);
  -webkit-backdrop-filter: blur(30px);
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: var(--radius-xl);
  overflow: hidden;
  transition:
    border-color var(--transition-slow),
    box-shadow var(--transition-slow);

  &.no-hover {
    // 卡片不浮起，仅边框微调
    &:hover {
      border-color: rgba(255, 255, 255, 0.15);
      box-shadow:
        0 8px 40px rgba(0, 0, 0, 0.2),
        inset 0 1px 0 rgba(255, 255, 255, 0.06);
    }
  }

  &:not(.no-hover):hover {
    transform: translateY(-4px);
    border-color: rgba(255, 255, 255, 0.16);
    box-shadow:
      0 20px 60px rgba(80, 120, 220, 0.12),
      0 8px 24px rgba(0, 0, 0, 0.25);
  }
}

/* 顶部微光线条 */
.glass-card__shine {
  position: absolute;
  top: 0;
  left: 8%;
  right: 8%;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(122, 158, 232, 0.4),
    rgba(167, 139, 250, 0.4),
    transparent
  );
  opacity: 0.7;
  pointer-events: none;
  z-index: 2;
}

/* 边缘发光层 */
.glass-card__glow {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.06),
    0 0 50px rgba(80, 120, 220, 0.05);
  pointer-events: none;
}

.glass-card__content {
  position: relative;
  z-index: 1;
}

.glass-card:not(.no-padding) .glass-card__content {
  padding: 40px 36px;
}

@media (max-width: 768px) {
  .glass-card:not(.no-padding) .glass-card__content {
    padding: 32px 24px;
  }
}
</style>
