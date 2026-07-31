<template>
  <div class="public-chat-view">
    <!-- ==========================================================
    顶部栏 — 品牌展示
    ========================================================== -->
    <header class="public-chat-view__header">
      <div class="public-chat-view__header-inner">
        <div class="public-chat-view__header-info">
          <img
            src="/image/logo.png"
            alt="煜见科技"
            class="public-chat-view__logo"
          />
          <div class="public-chat-view__brand">
            <h2 class="public-chat-view__title">煜见科技 AI 智能助手</h2>
            <span class="public-chat-view__status">
              <span class="status-dot" />
              <span class="public-chat-view__status-text">在线</span>
            </span>
          </div>
        </div>
      </div>
    </header>

    <!-- ==========================================================
    消息区
    ========================================================== -->
    <div
      ref="messageAreaRef"
      class="public-chat-view__messages"
      :class="{ 'public-chat-view__messages--has-content': store.hasMessages }"
      @scroll="handleScroll"
    >
      <!-- ---------- 品牌欢迎卡片（Hero） ---------- -->
      <PublicWelcomeHero
        v-if="!store.hasMessages"
        :sending="store.sending"
        @select="handleFillInput"
      />

      <!-- ---------- 消息列表 ---------- -->
      <div v-else class="public-chat-view__message-list">
        <div
          v-for="msg in store.messages"
          :key="msg.id"
          class="public-chat-view__message-wrapper"
        >
          <!-- 系统消息 -->
          <div
            v-if="msg.role === 'system'"
            class="public-chat-view__system-msg"
          >
            {{ msg.content }}
          </div>

          <!-- 用户/助手消息 -->
          <ChatMessage
            v-else
            :message="msg"
            :sending="store.sending"
            :is-mobile="isMobile"
            @retry="handleRetry(msg)"
          />

          <!-- 助手回复后免责声明 -->
          <div
            v-if="msg.role === 'assistant' && msg.status === 'success'"
            class="public-chat-view__disclaimer"
          >
            <div class="disclaimer-divider" />
            <p>以上内容由 AI 基于企业知识库生成，仅供参考。</p>
            <p>如需正式业务咨询，请联系煜见科技工作人员。</p>
          </div>
        </div>
      </div>
    </div>

    <!-- ==========================================================
    回到底部浮动按钮
    ========================================================== -->
    <transition name="scroll-btn-fade">
      <div
        v-if="showScrollToBottom"
        class="public-chat-view__scroll-btn touch-target"
        role="button"
        tabindex="0"
        aria-label="回到底部"
        @click="scrollToBottom()"
        @keydown.enter="scrollToBottom()"
        @keydown.space.prevent="scrollToBottom()"
      >
        <ChevronDown :size="20" />
      </div>
    </transition>

    <!-- ==========================================================
    输入区
    ========================================================== -->
    <div class="public-chat-view__input">
      <ChatInput
        ref="chatInputRef"
        :sending="store.sending"
        :max-length="maxQuestionLength"
        :is-mobile="isMobile"
        @send="handleSend"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch, inject, type Ref } from 'vue'
import { ChevronDown } from '@lucide/vue'
import { usePublicChatStore } from '@/stores/publicChatStore'
import PublicWelcomeHero from '@/components/public/PublicWelcomeHero.vue'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import type { PublicChatMessage } from '@/stores/publicChatStore'

const store = usePublicChatStore()

// ---- 响应式 ----
const isMobile = inject<Ref<boolean>>('isMobile', ref(false))

// ---- 输入 ----
const chatInputRef = ref<InstanceType<typeof ChatInput>>()
const maxQuestionLength = 2000

// ---- 滚动 ----
const messageAreaRef = ref<HTMLElement>()
const showScrollToBottom = ref(false)
let userScrolledUp = false
let lastScrollTime = 0
const SCROLL_THROTTLE_MS = 16

function scrollToBottom(smooth = true) {
  const now = performance.now()
  if (now - lastScrollTime < SCROLL_THROTTLE_MS) {
    requestAnimationFrame(() => doScrollToBottom(smooth))
    return
  }
  doScrollToBottom(smooth)
}

function doScrollToBottom(smooth: boolean) {
  nextTick(() => {
    const el = messageAreaRef.value
    if (el) {
      el.scrollTo({
        top: el.scrollHeight,
        behavior: smooth ? 'smooth' : 'instant',
      })
    }
    showScrollToBottom.value = false
    userScrolledUp = false
    lastScrollTime = performance.now()
  })
}

function handleScroll() {
  const el = messageAreaRef.value
  if (!el) return
  const threshold = 120
  const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold
  userScrolledUp = !isNearBottom
  showScrollToBottom.value = userScrolledUp
}

// 新消息后自动滚动
watch(
  () => store.messages.length,
  () => {
    if (!userScrolledUp) scrollToBottom(false)
  },
)

watch(
  () => {
    const msgs = store.messages
    if (msgs.length === 0) return ''
    const last = msgs[msgs.length - 1]
    return last?.content + last?.status
  },
  () => {
    if (!userScrolledUp) scrollToBottom(false)
  },
)

// ---- 操作 ----

async function handleSend(question: string) {
  await store.sendQuestion(question)
  userScrolledUp = false
  scrollToBottom()
}

function handleFillInput(question: string) {
  chatInputRef.value?.setText(question)
}

async function handleRetry(_msg: PublicChatMessage) {
  await store.retryLastFailed()
  userScrolledUp = false
  scrollToBottom()
}

// ---- 生命周期 ----
onMounted(() => {
  nextTick(() => scrollToBottom(false))
})

onUnmounted(() => {
  userScrolledUp = true
})
</script>

<style lang="scss" scoped>
// ================================================================
// 整体布局
// ================================================================
.public-chat-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  min-height: 0;
  overflow: hidden;
  background: linear-gradient(180deg, #F0F5FF 0%, #F8FAFE 30%, #F0F5FF 70%, #F8FAFE 100%);
  position: relative;
}

// ================================================================
// 顶部栏 — 简洁品牌风
// ================================================================
.public-chat-view__header {
  display: flex;
  align-items: center;
  height: 56px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(229, 231, 235, 0.6);
  flex: 0 0 auto;
  min-width: 0;
  z-index: 20;
}

.public-chat-view__header-inner {
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.public-chat-view__header-info {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.public-chat-view__logo {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  object-fit: contain;
  flex-shrink: 0;
}

.public-chat-view__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.public-chat-view__title {
  font-size: 15px;
  font-weight: 600;
  color: #0F172A;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  letter-spacing: -0.2px;
}

.public-chat-view__status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #16A34A;
  flex-shrink: 0;
  padding: 2px 10px;
  background: #F0FDF4;
  border-radius: 20px;

  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #16A34A;
    flex-shrink: 0;
    animation: statusPulse 2s ease-in-out infinite;
  }
}

@keyframes statusPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

// ================================================================
// 消息区
// ================================================================
.public-chat-view__messages {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
  padding: 0;

  &--has-content {
    padding: 24px;
  }
}

.public-chat-view__message-list {
  width: min(100%, 960px);
  margin: 0 auto;
}

.public-chat-view__message-wrapper {
  margin-bottom: 0;
}

.public-chat-view__system-msg {
  text-align: center;
  padding: 8px 16px;
  margin: 16px 0;
  font-size: 13px;
  color: #94A3B8;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 8px;
  max-width: 500px;
  margin-left: auto;
  margin-right: auto;
  backdrop-filter: blur(4px);
}

// ================================================================
// 回到底部按钮
// ================================================================
.public-chat-view__scroll-btn {
  position: absolute;
  bottom: 140px;
  left: 50%;
  transform: translateX(-50%);
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #FFFFFF;
  box-shadow: 0 2px 12px rgba(16, 24, 40, 0.1), 0 0 0 1px rgba(229, 231, 235, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 10;
  color: #64748B;
  transition: all 0.2s ease;

  &:hover {
    color: #2563EB;
    box-shadow: 0 4px 20px rgba(37, 99, 235, 0.2), 0 0 0 1px rgba(37, 99, 235, 0.2);
    transform: translateX(-50%) translateY(-2px);
  }

  &:focus-visible {
    outline: 2px solid #2563EB;
    outline-offset: 2px;
  }
}

.scroll-btn-fade-enter-active,
.scroll-btn-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.scroll-btn-fade-enter-from,
.scroll-btn-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}

// ================================================================
// 输入区 — ChatGPT 风格深度定制
// ================================================================
.public-chat-view__input {
  flex: 0 0 auto;
  padding: 0 24px 16px;
  background: transparent;

  :deep(.chat-input) {
    width: min(100%, 900px);
    margin: 0 auto;
  }

  // 客服提示
  :deep(.chat-input__hint) {
    font-size: 11px;
    color: #94A3B8;
  }

  // 输入框容器 — 大圆角 + 阴影 + AI 科技感
  :deep(.chat-input__wrapper) {
    background: #FFFFFF;
    border-radius: 24px;
    box-shadow:
      0 8px 30px rgba(16, 24, 40, 0.08),
      0 2px 8px rgba(16, 24, 40, 0.04),
      0 0 0 1px rgba(37, 99, 235, 0.08);
    padding: 14px 20px;
    transition: all 0.25s ease;

    &:focus-within {
      box-shadow:
        0 8px 36px rgba(37, 99, 235, 0.14),
        0 2px 12px rgba(37, 99, 235, 0.06),
        0 0 0 2px rgba(37, 99, 235, 0.15);
    }
  }

  // 隐藏 Element textarea 默认边框
  :deep(.el-textarea__inner) {
    border: none !important;
    box-shadow: none !important;
    background: transparent;
    font-size: 15px;
    line-height: 1.6;
    padding: 4px 0;
    min-height: 28px;
    max-height: 160px;
    color: #334155;
    resize: none;

    &::placeholder {
      color: #94A3B8;
    }

    &:focus {
      box-shadow: none !important;
      border: none !important;
    }
  }

  // 底部工具栏
  :deep(.chat-input__footer) {
    border-top-color: #F1F5F9;
    margin-top: 8px;
    padding-top: 8px;
  }

  // 发送按钮 — 圆润风格
  :deep(.chat-input__send-btn) {
    border-radius: 10px !important;
    padding: 6px 18px !important;
    font-weight: 500;
    font-size: 13px;
    background: #2563EB !important;
    border-color: #2563EB !important;
    transition: all 0.2s ease;

    &:hover:not(:disabled) {
      background: #1D4ED8 !important;
      border-color: #1D4ED8 !important;
      box-shadow: 0 2px 8px rgba(37, 99, 235, 0.3);
    }

    &:disabled {
      opacity: 0.4;
    }
  }

  :deep(.el-button--primary) {
    --el-button-bg-color: #2563EB;
    --el-button-border-color: #2563EB;
    --el-button-hover-bg-color: #1D4ED8;
    --el-button-hover-border-color: #1D4ED8;
  }
}

// ================================================================
// 免责声明
// ================================================================
.public-chat-view__disclaimer {
  width: min(100%, 960px);
  margin: 0 auto;
  font-size: 11px;
  color: #B0B8C1;
  text-align: left;
  padding: 2px 0 16px 56px;

  .disclaimer-divider {
    width: 100%;
    height: 1px;
    background: #EEF0F2;
    margin-bottom: 8px;
  }

  p {
    margin: 1px 0;
    line-height: 1.4;
  }
}

// ================================================================
// 平板端适配 (768px - 1199px)
// ================================================================
@media (min-width: 768px) and (max-width: 1199px) {
  .public-chat-view__header-inner {
    max-width: 800px;
    padding: 0 20px;
  }

  .public-chat-view__messages--has-content {
    padding: 20px;
  }

  .public-chat-view__message-list {
    width: min(100%, 800px);
  }

  .public-chat-view__disclaimer {
    width: min(100%, 800px);
    padding-left: 48px;
  }

  .public-chat-view__input {
    padding: 0 20px 12px;

    :deep(.chat-input) {
      width: min(100%, 800px);
    }
  }
}

// ================================================================
// 移动端适配 (< 768px)
// ================================================================
@media (max-width: 767px) {
  .public-chat-view__header {
    height: 52px;
  }

  .public-chat-view__header-inner {
    padding: 0 16px;
  }

  .public-chat-view__logo {
    width: 28px;
    height: 28px;
    border-radius: 6px;
  }

  .public-chat-view__title {
    font-size: 14px;
  }

  .public-chat-view__status {
    padding: 1px 8px;
    font-size: 11px;
  }

  .public-chat-view__status-text {
    display: none;
  }

  .public-chat-view__messages--has-content {
    padding: 12px;
  }

  .public-chat-view__message-list {
    width: 100%;
  }

  .public-chat-view__disclaimer {
    width: 100%;
    padding-left: 10px;
    font-size: 10px;
    color: #C0C8D0;
  }

  .public-chat-view__scroll-btn {
    bottom: 120px;
  }

  .public-chat-view__input {
    padding: 0 12px 12px;
    padding-bottom: max(12px, env(safe-area-inset-bottom, 8px));

    :deep(.chat-input) {
      width: 100%;
    }

    :deep(.chat-input__wrapper) {
      border-radius: 20px;
      padding: 10px 14px;
    }

    :deep(.el-textarea__inner) {
      font-size: 16px; // 防止 iOS 缩放
    }

    :deep(.chat-input__send-btn) {
      border-radius: 50% !important;
      padding: 0 !important;
      min-width: 36px;
      min-height: 36px;
    }

    :deep(.chat-input__send-text) {
      display: none;
    }

    :deep(.chat-input__send-icon) {
      display: block;
    }
  }
}

// ================================================================
// prefers-reduced-motion
// ================================================================
@media (prefers-reduced-motion: reduce) {
  .public-chat-view__status .status-dot {
    animation: none;
  }

  .public-chat-view__scroll-btn {
    transition: none;
  }

  :deep(.chat-input__wrapper) {
    transition: none;
  }
}
</style>
