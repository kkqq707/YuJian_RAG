<template>
  <!--
    FeatureList — AI 平台功能介绍列表

    4 项核心能力，每项含图标 + 标题 + 描述
    设计：克制、专业、企业级
  -->
  <div class="feature-list">
    <div
      v-for="(feature, index) in features"
      :key="index"
      class="feature-item"
      :style="{ animationDelay: `${0.1 + index * 0.1}s` }"
    >
      <!-- 图标 -->
      <div class="feature-item__icon">
        <component :is="feature.icon" :size="18" />
      </div>

      <!-- 文字 -->
      <div class="feature-item__text">
        <h4 class="feature-item__title">{{ feature.title }}</h4>
        <p class="feature-item__desc">{{ feature.description }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Search, Shield, Bot, Lock } from '@lucide/vue'

interface Feature {
  icon: typeof Search
  title: string
  description: string
}

const features: Feature[] = [
  {
    icon: Search,
    title: 'RAG 智能检索增强生成',
    description: '快速精准获取知识，提升效率',
  },
  {
    icon: Shield,
    title: '企业级知识管理',
    description: '安全、权限、合规的知识资产管理',
  },
  {
    icon: Bot,
    title: '多模型 AI 智能对话',
    description: '结合多种大模型，回答更全面',
  },
  {
    icon: Lock,
    title: '数据安全与隐私保护',
    description: '企业级安全保障',
  },
]
</script>

<style lang="scss" scoped>
/* ============================================================
 * FeatureList — AI 平台功能介绍
 * ============================================================ */

.feature-list {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.feature-item {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  opacity: 0;
  animation: feature-fade-in 0.5s ease-out forwards;

  &:hover {
    .feature-item__icon {
      transform: scale(1.1);
      box-shadow: 0 0 16px rgba(80, 140, 220, 0.2);
      border-color: rgba(140, 180, 230, 0.3);
    }
  }
}

@keyframes feature-fade-in {
  from {
    opacity: 0;
    transform: translateX(-12px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

/* ---- 图标 ---- */
.feature-item__icon {
  flex-shrink: 0;
  width: 38px;
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: rgba(80, 140, 220, 0.1);
  border: 1px solid rgba(140, 180, 230, 0.15);
  color: rgba(140, 180, 230, 0.65);
  transition:
    transform 0.3s ease,
    box-shadow 0.3s ease,
    border-color 0.3s ease;
}

/* ---- 文字 ---- */
.feature-item__text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.feature-item__title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: rgba(200, 215, 240, 0.8);
  letter-spacing: 0.5px;
  line-height: 1.3;
}

.feature-item__desc {
  margin: 0;
  font-size: 12px;
  color: rgba(150, 180, 210, 0.5);
  letter-spacing: 0.3px;
  line-height: 1.5;
}

/* ============================================================
 * 响应式 — 使用统一断点体系
 * ============================================================ */

/* 平板：压缩间距但保留功能列表 */
@media (min-width: 768px) and (max-width: 1199px) {
  .feature-list {
    gap: 12px;
  }

  .feature-item {
    gap: 10px;
  }

  .feature-item__icon {
    width: 32px;
    height: 32px;
    border-radius: 8px;
  }

  .feature-item__title {
    font-size: 12px;
  }

  .feature-item__desc {
    font-size: 11px;
  }
}

/* 移动端：隐藏功能列表，精简品牌区域 */
@media (max-width: 767px) {
  .feature-list {
    display: none;
  }
}

/* 低性能设备：关闭动画 */
@media (prefers-reduced-motion: reduce) {
  .feature-item {
    animation: none;
    opacity: 1;
    transform: none;
  }
}
</style>
