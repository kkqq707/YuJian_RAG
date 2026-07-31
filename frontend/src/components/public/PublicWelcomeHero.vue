<template>
  <div class="welcome-hero">
    <!-- ============================================================
    Hero 区域 — Logo + 标题 + 副标题
    ============================================================ -->
    <div class="welcome-hero__brand">
      <div class="welcome-hero__logo-wrap">
        <img
          src="/logo.png"
          alt="煜见科技"
          class="welcome-hero__logo"
        />
      </div>
      <h1 class="welcome-hero__title">煜见科技 AI 智能助手</h1>
      <p class="welcome-hero__subtitle">
        企业知识库驱动的智能问答平台
      </p>
    </div>

    <!-- ============================================================
    产品介绍卡片 — 展示核心能力
    ============================================================ -->
    <div class="welcome-hero__features">
      <div
        v-for="feature in features"
        :key="feature.title"
        class="feature-card"
      >
        <div class="feature-card__icon" :style="{ background: feature.bg, color: feature.color }">
          <component :is="feature.icon" :size="22" />
        </div>
        <div class="feature-card__text">
          <h3 class="feature-card__title">{{ feature.title }}</h3>
          <p class="feature-card__desc">{{ feature.desc }}</p>
        </div>
      </div>
    </div>

    <!-- ============================================================
    AI 快捷入口 — 推荐问题按钮
    ============================================================ -->
    <div class="welcome-hero__quick-prompts">
      <p class="welcome-hero__quick-title">
        <Zap :size="14" class="welcome-hero__quick-title-icon" />
        AI 快捷入口
      </p>
      <div class="welcome-hero__quick-grid">
        <button
          v-for="prompt in quickPrompts"
          :key="prompt.label"
          class="quick-prompt-btn"
          :disabled="sending"
          :aria-label="prompt.label"
          @click="$emit('select', prompt.question)"
        >
          <span class="quick-prompt-btn__icon-wrap">
            <component :is="prompt.icon" :size="16" />
          </span>
          <span class="quick-prompt-btn__label">{{ prompt.label }}</span>
          <span class="quick-prompt-btn__arrow">
            <ArrowUpRight :size="12" />
          </span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  Bot,
  Database,
  ShieldCheck,
  Clock,
  Building2,
  Cpu,
  Package,
  Handshake,
  Zap,
  ArrowUpRight,
} from '@lucide/vue'

defineProps<{
  sending?: boolean
}>()

defineEmits<{
  select: [question: string]
}>()

// ---- 产品介绍卡片数据 ----
const features = [
  {
    icon: Bot,
    title: '智能问答',
    desc: '基于企业知识库的深度语义理解，精准回答业务问题',
    bg: '#EEF2FF',
    color: '#4F46E5',
  },
  {
    icon: Database,
    title: '知识检索',
    desc: '高效检索企业文档、技术方案与产品资料，秒级响应',
    bg: '#F0F9FF',
    color: '#0284C7',
  },
  {
    icon: ShieldCheck,
    title: '企业定制',
    desc: '支持私有化部署，保障数据安全与业务流程无缝集成',
    bg: '#F0FDF4',
    color: '#16A34A',
  },
  {
    icon: Clock,
    title: '即时响应',
    desc: '7×24 小时在线，随时获取企业信息，提升协作效率',
    bg: '#FFF7ED',
    color: '#EA580C',
  },
]

// ---- 快捷入口数据 ----
const quickPrompts = [
  {
    icon: Building2,
    label: '公司介绍',
    question: '煜见科技主要业务是什么？',
  },
  {
    icon: Cpu,
    label: '技术能力',
    question: '公司有哪些技术服务？',
  },
  {
    icon: Package,
    label: '产品方案',
    question: '有哪些 AI 解决方案？',
  },
  {
    icon: Handshake,
    label: '合作流程',
    question: '如何与煜见科技合作？',
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

@keyframes logoGlow {
  0%, 100% {
    box-shadow: 0 0 20px rgba(37, 99, 235, 0.15), 0 0 40px rgba(37, 99, 235, 0.06);
  }
  50% {
    box-shadow: 0 0 28px rgba(37, 99, 235, 0.25), 0 0 56px rgba(37, 99, 235, 0.10);
  }
}

// ================================================================
// 容器
// ================================================================
.welcome-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 48px 24px 40px;
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
  animation: heroFadeIn 0.6s ease;
  overflow-y: auto;
}

// ================================================================
// Hero Brand — Logo + 标题 + 副标题
// ================================================================
.welcome-hero__brand {
  text-align: center;
  margin-bottom: 40px;
}

.welcome-hero__logo-wrap {
  display: inline-block;
  margin-bottom: 24px;
}

.welcome-hero__logo {
  width: 80px;
  height: 80px;
  object-fit: contain;
  border-radius: 20px;
  animation: logoGlow 3s ease-in-out infinite;
  background: #fff;
}

.welcome-hero__title {
  font-size: 32px;
  font-weight: 700;
  color: #0F172A;
  margin: 0 0 12px;
  line-height: 1.3;
  letter-spacing: -0.5px;
  background: linear-gradient(135deg, #1E3A5F 0%, #2563EB 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.welcome-hero__subtitle {
  font-size: 16px;
  color: #64748B;
  margin: 0;
  line-height: 1.6;
  font-weight: 400;
}

// ================================================================
// 产品介绍卡片
// ================================================================
.welcome-hero__features {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  width: 100%;
  margin-bottom: 36px;
}

.feature-card {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  background: #FFFFFF;
  border: 1px solid #F1F5F9;
  border-radius: 16px;
  padding: 18px 20px;
  transition: all 0.25s ease;
  cursor: default;

  &:hover {
    border-color: #DBEAFE;
    box-shadow: 0 4px 16px rgba(37, 99, 235, 0.08);
    transform: translateY(-2px);
  }
}

.feature-card__icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.feature-card__text {
  min-width: 0;
}

.feature-card__title {
  font-size: 15px;
  font-weight: 600;
  color: #0F172A;
  margin: 0 0 4px;
  line-height: 1.3;
}

.feature-card__desc {
  font-size: 13px;
  color: #94A3B8;
  margin: 0;
  line-height: 1.55;
}

// ================================================================
// AI 快捷入口
// ================================================================
.welcome-hero__quick-prompts {
  width: 100%;
}

.welcome-hero__quick-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #94A3B8;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  margin: 0 0 14px;
}

.welcome-hero__quick-title-icon {
  color: #F59E0B;
  flex-shrink: 0;
}

.welcome-hero__quick-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.quick-prompt-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 14px 18px;
  background: #FFFFFF;
  border: 1px solid #F1F5F9;
  border-radius: 14px;
  font-size: 14px;
  font-weight: 500;
  color: #334155;
  cursor: pointer;
  transition: all 0.25s ease;
  font-family: inherit;
  text-align: left;
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: 14px;
    background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
    opacity: 0;
    transition: opacity 0.25s ease;
  }

  &:hover:not(:disabled) {
    border-color: #BFDBFE;
    box-shadow: 0 4px 20px rgba(37, 99, 235, 0.12);
    transform: translateY(-2px);

    .quick-prompt-btn__icon-wrap {
      background: #DBEAFE;
      color: #2563EB;
    }

    .quick-prompt-btn__label {
      color: #2563EB;
    }

    .quick-prompt-btn__arrow {
      opacity: 1;
      transform: translate(2px, -2px);
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

.quick-prompt-btn__icon-wrap {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: #F8FAFC;
  color: #64748B;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.25s ease;
  position: relative;
  z-index: 1;
}

.quick-prompt-btn__label {
  flex: 1;
  min-width: 0;
  position: relative;
  z-index: 1;
  transition: color 0.25s ease;
}

.quick-prompt-btn__arrow {
  color: #94A3B8;
  flex-shrink: 0;
  opacity: 0;
  transition: all 0.25s ease;
  position: relative;
  z-index: 1;
}

// ================================================================
// 平板端适配 (768px - 1199px)
// ================================================================
@media (min-width: 768px) and (max-width: 1199px) {
  .welcome-hero {
    padding: 36px 20px 32px;
    max-width: 640px;
  }

  .welcome-hero__logo {
    width: 68px;
    height: 68px;
    border-radius: 18px;
  }

  .welcome-hero__title {
    font-size: 26px;
  }

  .welcome-hero__subtitle {
    font-size: 15px;
  }

  .welcome-hero__features {
    gap: 12px;
  }

  .feature-card {
    padding: 14px 16px;
    border-radius: 14px;
  }
}

// ================================================================
// 移动端适配 (< 768px)
// ================================================================
@media (max-width: 767px) {
  .welcome-hero {
    padding: 24px 16px 28px;
    max-width: 100%;
    overflow-y: auto;
    justify-content: flex-start;
  }

  .welcome-hero__brand {
    margin-bottom: 28px;
  }

  .welcome-hero__logo {
    width: 56px;
    height: 56px;
    border-radius: 14px;
  }

  .welcome-hero__title {
    font-size: 22px;
    letter-spacing: -0.3px;
  }

  .welcome-hero__subtitle {
    font-size: 14px;
  }

  // 产品卡片 — 移动端单列
  .welcome-hero__features {
    grid-template-columns: 1fr;
    gap: 10px;
    margin-bottom: 28px;
  }

  .feature-card {
    padding: 14px 16px;
    border-radius: 14px;
    gap: 12px;
  }

  .feature-card__icon {
    width: 40px;
    height: 40px;
    border-radius: 10px;
  }

  .feature-card__title {
    font-size: 14px;
  }

  .feature-card__desc {
    font-size: 12px;
  }

  // 快捷入口 — 移动端单列
  .welcome-hero__quick-grid {
    grid-template-columns: 1fr;
    gap: 10px;
  }

  .quick-prompt-btn {
    padding: 12px 16px;
    border-radius: 12px;
    font-size: 13px;
  }

  .quick-prompt-btn__icon-wrap {
    width: 32px;
    height: 32px;
    border-radius: 8px;
  }

  .quick-prompt-btn__arrow {
    opacity: 0.4;
  }
}

// ================================================================
// prefers-reduced-motion
// ================================================================
@media (prefers-reduced-motion: reduce) {
  .welcome-hero {
    animation: none;
  }

  .welcome-hero__logo {
    animation: none;
  }

  .feature-card,
  .quick-prompt-btn {
    transition: none;
  }

  .quick-prompt-btn__arrow {
    opacity: 0.4;
  }
}
</style>
