<template>
  <div class="welcome-hero">
    <!-- ============================================================
    Hero 区域 — Logo + 问候语
    ============================================================ -->
    <div class="welcome-hero__brand">
      <div class="welcome-hero__logo-wrap">
        <img
          src="/logo.png"
          alt="煜见科技"
          class="welcome-hero__logo"
        />
      </div>
      <h1 class="welcome-hero__title">
        您好，我是煜见科技
      </h1>
      <p class="welcome-hero__highlight">AI 智能助手</p>
      <p class="welcome-hero__subtitle">
        我可以基于企业知识库，为您解答业务、产品、技术方案等问题。
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
          <span class="quick-prompt-btn__icon">
            <component :is="prompt.icon" :size="18" />
          </span>
          <span class="quick-prompt-btn__text">
            <span class="quick-prompt-btn__label">{{ prompt.label }}</span>
            <span class="quick-prompt-btn__question">{{ prompt.question }}</span>
          </span>
          <span class="quick-prompt-btn__arrow">
            <ChevronRight :size="14" />
          </span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Building2, Package, FileText, Handshake, ChevronRight } from '@lucide/vue'

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
    question: '煜见科技是做什么的？',
  },
  {
    icon: Package,
    label: '产品信息',
    question: '煜见科技有哪些产品？',
  },
  {
    icon: FileText,
    label: '服务流程',
    question: '公司提供什么样的服务？',
  },
  {
    icon: Handshake,
    label: '合作政策',
    question: '如何与公司合作？',
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
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes logoGlow {
  0%, 100% {
    box-shadow: 0 0 20px rgba(37, 99, 235, 0.12), 0 0 40px rgba(37, 99, 235, 0.04);
  }
  50% {
    box-shadow: 0 0 28px rgba(37, 99, 235, 0.20), 0 0 56px rgba(37, 99, 235, 0.08);
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
  max-width: 720px;
  margin: 0 auto;
  width: 100%;
  min-height: 100%;
  animation: heroFadeIn 0.5s ease;
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
  margin-bottom: 28px;
}

.welcome-hero__logo {
  width: 72px;
  height: 72px;
  object-fit: contain;
  border-radius: 18px;
  animation: logoGlow 4s ease-in-out infinite;
  background: #fff;
}

.welcome-hero__title {
  font-size: 28px;
  font-weight: 700;
  color: #0F172A;
  margin: 0;
  line-height: 1.4;
  letter-spacing: -0.4px;
}

.welcome-hero__highlight {
  font-size: 28px;
  font-weight: 700;
  margin: 0;
  line-height: 1.4;
  letter-spacing: -0.4px;
  background: linear-gradient(135deg, #2563EB 0%, #4F46E5 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.welcome-hero__subtitle {
  font-size: 15px;
  color: #94A3B8;
  margin: 16px 0 0;
  line-height: 1.7;
  font-weight: 400;
  max-width: 480px;
}

// ================================================================
// 推荐问题按钮
// ================================================================
.welcome-hero__quick-prompts {
  width: 100%;
  max-width: 560px;
}

.welcome-hero__quick-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.quick-prompt-btn {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  padding: 14px 18px;
  background: #FFFFFF;
  border: 1px solid #F1F5F9;
  border-radius: 14px;
  cursor: pointer;
  transition: all 0.25s ease;
  font-family: inherit;
  text-align: left;
  color: #334155;

  &:hover:not(:disabled) {
    border-color: #BFDBFE;
    box-shadow: 0 4px 16px rgba(37, 99, 235, 0.10);
    transform: translateX(4px);

    .quick-prompt-btn__icon {
      background: #DBEAFE;
      color: #2563EB;
    }

    .quick-prompt-btn__label {
      color: #2563EB;
    }

    .quick-prompt-btn__arrow {
      opacity: 1;
      color: #2563EB;
    }
  }

  &:active:not(:disabled) {
    transform: translateX(2px);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.quick-prompt-btn__icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: #F8FAFC;
  color: #64748B;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.25s ease;
}

.quick-prompt-btn__text {
  flex: 1;
  min-width: 0;
}

.quick-prompt-btn__label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: #334155;
  line-height: 1.3;
  transition: color 0.25s ease;
}

.quick-prompt-btn__question {
  display: block;
  font-size: 12px;
  color: #94A3B8;
  margin-top: 2px;
  line-height: 1.4;
}

.quick-prompt-btn__arrow {
  color: #CBD5E1;
  flex-shrink: 0;
  opacity: 0;
  transition: all 0.25s ease;
}

// ================================================================
// 平板端适配 (768px - 1199px)
// ================================================================
@media (min-width: 768px) and (max-width: 1199px) {
  .welcome-hero {
    padding: 0 20px;
    max-width: 600px;
  }

  .welcome-hero__logo {
    width: 64px;
    height: 64px;
    border-radius: 16px;
  }

  .welcome-hero__title,
  .welcome-hero__highlight {
    font-size: 24px;
  }

  .welcome-hero__subtitle {
    font-size: 14px;
  }

  .quick-prompt-btn {
    padding: 12px 16px;
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
    padding-top: 32px;
  }

  .welcome-hero__brand {
    margin-bottom: 32px;
  }

  .welcome-hero__logo {
    width: 56px;
    height: 56px;
    border-radius: 14px;
  }

  .welcome-hero__logo-wrap {
    margin-bottom: 20px;
  }

  .welcome-hero__title,
  .welcome-hero__highlight {
    font-size: 22px;
    letter-spacing: -0.3px;
  }

  .welcome-hero__subtitle {
    font-size: 13px;
    margin-top: 12px;
    max-width: 320px;
  }

  .welcome-hero__quick-prompts {
    max-width: 100%;
  }

  .quick-prompt-btn {
    padding: 12px 14px;
    gap: 12px;
    border-radius: 12px;
  }

  .quick-prompt-btn__icon {
    width: 36px;
    height: 36px;
    border-radius: 8px;
  }

  .quick-prompt-btn__label {
    font-size: 13px;
  }

  .quick-prompt-btn__question {
    font-size: 11px;
  }

  .quick-prompt-btn__arrow {
    opacity: 0.3;
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

  .quick-prompt-btn {
    transition: none;
  }
}
</style>
