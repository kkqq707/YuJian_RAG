<template>
  <div class="welcome-hero">
    <!-- ============================================================
    Hero 区域 — Logo卡片 + 标题
    ============================================================ -->
    <div class="welcome-hero__brand">
      <!-- Logo 白色卡片容器 -->
      <div class="welcome-hero__logo-card">
        <img
          src="/image/logo01.png"
          alt="煜见科技"
          class="welcome-hero__logo"
        />
      </div>
      <h1 class="welcome-hero__title">
        您好，我是煜见科技
      </h1>
      <p class="welcome-hero__highlight">AI 智能助手</p>
      <p class="welcome-hero__subtitle">
        基于企业知识库，为您解答业务、产品、技术方案等问题。
      </p>
    </div>

    <!-- ============================================================
    推荐问题 — 卡片按钮
    ============================================================ -->
    <div class="welcome-hero__quick-prompts">
      <div class="welcome-hero__quick-grid">
        <button
          v-for="prompt in quickPrompts"
          :key="prompt.label"
          class="quick-prompt-btn"
          :disabled="sending"
          :aria-label="prompt.label"
          @click="$emit('select', prompt.question)"
        >
          <span class="quick-prompt-btn__icon" :style="{ background: prompt.iconBg, color: prompt.iconColor }">
            <component :is="prompt.icon" :size="20" />
          </span>
          <span class="quick-prompt-btn__text">
            <span class="quick-prompt-btn__label">{{ prompt.label }}</span>
            <span class="quick-prompt-btn__desc">{{ prompt.desc }}</span>
          </span>
          <span class="quick-prompt-btn__arrow">
            <ChevronRight :size="16" />
          </span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Building2, Package, Cpu, MessageCircle, ChevronRight } from '@lucide/vue'

defineProps<{
  sending?: boolean
}>()

defineEmits<{
  select: [question: string]
}>()

// ---- 推荐问题数据 ----
const quickPrompts = [
  {
    icon: Building2,
    label: '公司介绍',
    desc: '了解煜见科技业务方向',
    question: '煜见科技是做什么的？',
    iconBg: '#EEF2FF',
    iconColor: '#4F46E5',
  },
  {
    icon: Package,
    label: '产品信息',
    desc: '探索产品与服务能力',
    question: '煜见科技有哪些产品？',
    iconBg: '#F0F9FF',
    iconColor: '#0284C7',
  },
  {
    icon: Cpu,
    label: '技术方案',
    desc: '查看 AI 与数字化解决方案',
    question: '公司有哪些技术服务？',
    iconBg: '#FFF7ED',
    iconColor: '#EA580C',
  },
  {
    icon: MessageCircle,
    label: '合作咨询',
    desc: '了解合作方式与流程',
    question: '如何与煜见科技合作？',
    iconBg: '#F0FDF4',
    iconColor: '#16A34A',
  },
]
</script>

<style lang="scss" scoped>
// ================================================================
// 动画
// ================================================================
@keyframes heroFadeIn {
  from {
    opacity: 0;
    transform: translateY(24px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes logoCardGlow {
  0%, 100% {
    box-shadow:
      0 4px 16px rgba(37, 99, 235, 0.06),
      0 1px 4px rgba(16, 24, 40, 0.04);
  }
  50% {
    box-shadow:
      0 4px 24px rgba(37, 99, 235, 0.12),
      0 1px 8px rgba(16, 24, 40, 0.06);
  }
}

// ================================================================
// 容器 — 上下居中
// ================================================================
.welcome-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 0 24px;
  max-width: 740px;
  margin: 0 auto;
  width: 100%;
  min-height: 100%;
  animation: heroFadeIn 0.6s ease;
}

// ================================================================
// Hero Brand — Logo + 标题 + 副标题
// ================================================================
.welcome-hero__brand {
  text-align: center;
  margin-bottom: 48px;
}

// Logo 白色卡片 — 缩小外层留白，图像占主体
.welcome-hero__logo-card {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  background: #FFFFFF;
  border-radius: 20px;
  margin-bottom: 32px;
  animation: logoCardGlow 4s ease-in-out infinite;
}

.welcome-hero__logo {
  width: 58px;
  height: 58px;
  object-fit: contain;
  border-radius: 14px;
}

// 标题: "您好，我是煜见科技" — 32px #111827
.welcome-hero__title {
  font-size: 32px;
  font-weight: 700;
  color: #111827;
  margin: 0;
  line-height: 1.35;
  letter-spacing: -0.5px;
}

// "AI 智能助手" — 36px 品牌蓝色
.welcome-hero__highlight {
  font-size: 36px;
  font-weight: 700;
  color: #2563EB;
  margin: 4px 0 0;
  line-height: 1.35;
  letter-spacing: -0.5px;
}

// 副标题
.welcome-hero__subtitle {
  font-size: 15px;
  color: #94A3B8;
  margin: 20px 0 0;
  line-height: 1.7;
  font-weight: 400;
  max-width: 480px;
}

// ================================================================
// 推荐问题 — 2列网格
// ================================================================
.welcome-hero__quick-prompts {
  width: 100%;
  max-width: 640px;
}

.welcome-hero__quick-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.quick-prompt-btn {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  height: 90px;
  padding: 16px 18px;
  background: #FFFFFF;
  border: 1.5px solid transparent;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.3s ease;
  font-family: inherit;
  text-align: left;
  color: #334155;
  box-shadow:
    0 1px 3px rgba(16, 24, 40, 0.04),
    0 0 0 1px rgba(229, 231, 235, 0.4);

  &:hover:not(:disabled) {
    border-color: #93C5FD;
    box-shadow:
      0 8px 24px rgba(37, 99, 235, 0.10),
      0 2px 6px rgba(16, 24, 40, 0.06);
    transform: translateY(-2px);

    .quick-prompt-btn__label {
      color: #2563EB;
    }
  }

  &:active:not(:disabled) {
    transform: translateY(0);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.quick-prompt-btn__icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: transform 0.3s ease;

  .quick-prompt-btn:hover & {
    transform: scale(1.06);
  }
}

.quick-prompt-btn__text {
  flex: 1;
  min-width: 0;
}

.quick-prompt-btn__label {
  display: block;
  font-size: 15px;
  font-weight: 600;
  color: #0F172A;
  line-height: 1.3;
  transition: color 0.25s ease;
}

.quick-prompt-btn__desc {
  display: block;
  font-size: 12.5px;
  color: #94A3B8;
  margin-top: 4px;
  line-height: 1.4;
}

// 隐藏箭头（2列卡片不需要箭头）
.quick-prompt-btn__arrow {
  display: none;
}

// ================================================================
// 平板端适配 (768px - 1199px)
// ================================================================
@media (min-width: 768px) and (max-width: 1199px) {
  .welcome-hero {
    padding: 0 20px;
    max-width: 640px;
  }

  .welcome-hero__logo-card {
    width: 72px;
    height: 72px;
    border-radius: 18px;
    margin-bottom: 28px;
  }

  .welcome-hero__logo {
    width: 52px;
    height: 52px;
    border-radius: 12px;
  }

  .welcome-hero__title {
    font-size: 28px;
  }

  .welcome-hero__highlight {
    font-size: 32px;
  }

  .welcome-hero__subtitle {
    font-size: 14px;
  }

  .welcome-hero__quick-prompts {
    max-width: 560px;
  }

  .quick-prompt-btn {
    height: 84px;
    padding: 14px 16px;
    gap: 12px;
  }

  .quick-prompt-btn__icon {
    width: 40px;
    height: 40px;
    border-radius: 10px;
  }
}

// ================================================================
// 移动端适配 (< 768px)
// ================================================================
@media (max-width: 767px) {
  .welcome-hero {
    padding: 0 16px;
    max-width: 100%;
    justify-content: flex-start;
    padding-top: 28px;
  }

  .welcome-hero__brand {
    margin-bottom: 32px;
  }

  .welcome-hero__logo-card {
    width: 64px;
    height: 64px;
    border-radius: 16px;
    margin-bottom: 24px;
  }

  .welcome-hero__logo {
    width: 46px;
    height: 46px;
    border-radius: 10px;
  }

  .welcome-hero__title {
    font-size: 24px;
    letter-spacing: -0.3px;
  }

  .welcome-hero__highlight {
    font-size: 28px;
    letter-spacing: -0.3px;
  }

  .welcome-hero__subtitle {
    font-size: 13px;
    margin-top: 16px;
    max-width: 320px;
  }

  // 移动端：推荐问题变1列
  .welcome-hero__quick-prompts {
    max-width: 100%;
  }

  .welcome-hero__quick-grid {
    grid-template-columns: 1fr;
    gap: 10px;
  }

  .quick-prompt-btn {
    height: auto;
    min-height: 78px;
    padding: 14px 16px;
    gap: 14px;
    border-radius: 14px;
  }

  .quick-prompt-btn__icon {
    width: 38px;
    height: 38px;
    border-radius: 10px;
  }

  .quick-prompt-btn__label {
    font-size: 14px;
  }

  .quick-prompt-btn__desc {
    font-size: 12px;
  }
}

// ================================================================
// prefers-reduced-motion
// ================================================================
@media (prefers-reduced-motion: reduce) {
  .welcome-hero {
    animation: none;
  }

  .welcome-hero__logo-card {
    animation: none;
  }

  .quick-prompt-btn {
    transition: none;
  }
}
</style>
