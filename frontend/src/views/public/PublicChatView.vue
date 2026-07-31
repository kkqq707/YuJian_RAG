<template>
  <div class="public-chat-view">
    <!-- 顶部栏 -->
    <header class="public-chat-view__header">
      <div class="public-chat-view__header-info">
        <img
          src="/logo.png"
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
    </header>

    <!-- 消息区 -->
    <div
      ref="messageAreaRef"
      class="public-chat-view__messages"
      @scroll="handleScroll"
    >
      <!-- 品牌欢迎卡片 -->
      <PublicWelcomeCard
        v-if="!store.hasMessages"
        :sending="store.sending"
        :is-mobile="isMobile"
        @select="handleFillInput"
      />

      <!-- 消息列表 -->
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

    <!-- 回到底部浮动按钮 -->
    <transition name="fade">
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

    <!-- 输入区 -->
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
import PublicWelcomeCard from '@/components/chat/PublicWelcomeCard.vue'
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
.public-chat-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  min-height: 0;
  overflow: hidden;
  background: $color-page-bg;
}

// ---- 顶部栏 ----
.public-chat-view__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 $spacing-lg;
  height: 56px;
  background: $color-card-bg;
  border-bottom: 1px solid $color-border;
  flex: 0 0 auto;
  min-width: 0;
  gap: $spacing-sm;
}

.public-chat-view__header-info {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
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
  gap: $spacing-sm;
  min-width: 0;
}

.public-chat-view__title {
  font-size: $font-size-lg;
  font-weight: 600;
  color: $color-text-primary;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.public-chat-view__status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: $font-size-xs;
  color: $color-success;
  flex-shrink: 0;

  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: $color-success;
    flex-shrink: 0;
  }
}

// ---- 消息区 ----
.public-chat-view__messages {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
  padding: $spacing-lg;
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
  margin: $spacing-md 0;
  font-size: $font-size-sm;
  color: $color-text-tertiary;
  background: #f0f4ff;
  border-radius: 8px;
  max-width: 500px;
  margin-left: auto;
  margin-right: auto;
}

// ---- 回到底部 ----
.public-chat-view {
  position: relative;
}

.public-chat-view__scroll-btn {
  position: absolute;
  bottom: 140px;
  left: 50%;
  transform: translateX(-50%);
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: $color-card-bg;
  box-shadow: $shadow-dropdown;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 10;
  color: $color-text-secondary;
  transition: all $transition-fast;

  &:hover {
    color: $color-primary;
    box-shadow: 0 4px 20px rgba(16, 24, 40, 0.12);
  }

  &:focus-visible {
    outline: 2px solid $color-primary;
    outline-offset: 2px;
  }
}

// ---- 输入区 ----
.public-chat-view__input {
  flex: 0 0 auto;
  padding: 0 $spacing-lg $spacing-sm;
  background: $color-page-bg;

  :deep(.chat-input) {
    width: min(100%, 960px);
    margin: 0 auto;
  }
}

// ================================================================
// 平板端适配
// ================================================================
@media (min-width: 768px) and (max-width: 1199px) {
  .public-chat-view__header {
    padding: 0 $spacing-md;
  }

  .public-chat-view__messages {
    padding: $spacing-md;
  }

  .public-chat-view__message-list {
    width: min(100%, 800px);
  }

  .public-chat-view__disclaimer {
    width: min(100%, 800px);
    padding-left: 48px;
  }

  .public-chat-view__input {
    padding: 0 $spacing-md $spacing-sm;

    :deep(.chat-input) {
      width: min(100%, 800px);
    }
  }
}

// ================================================================
// 移动端适配
// ================================================================
@media (max-width: 767px) {
  .public-chat-view__header {
    padding: 0 $spacing-sm;
    height: 52px;
  }

  .public-chat-view__logo {
    width: 28px;
    height: 28px;
    border-radius: 6px;
  }

  .public-chat-view__title {
    font-size: $font-size-sm;
  }

  .public-chat-view__status-text {
    display: none;
  }

  .public-chat-view__messages {
    padding: $spacing-sm;
  }

  .public-chat-view__message-list {
    width: 100%;
  }

  .public-chat-view__disclaimer {
    width: 100%;
    padding-left: 10px;
    font-size: 10px;
    color: #c0c8d0;
  }

  .public-chat-view__scroll-btn {
    bottom: 120px;
  }

  .public-chat-view__input {
    padding: 0 $spacing-sm;
    padding-bottom: max($spacing-sm, env(safe-area-inset-bottom, 8px));

    :deep(.chat-input) {
      width: 100%;
    }
  }
}

// ---- 助手回复免责声明 ----
.public-chat-view__disclaimer {
  width: min(100%, 960px);
  margin: 0 auto;
  font-size: 11px;
  color: #b0b8c1;
  text-align: left;
  padding: 2px 0 $spacing-md 56px;

  .disclaimer-divider {
    width: 100%;
    height: 1px;
    background: #eef0f2;
    margin-bottom: $spacing-xs;
  }

  p {
    margin: 1px 0;
    line-height: 1.4;
  }
}

@media (prefers-reduced-motion: reduce) {
  .public-chat-view__scroll-btn {
    transition: none;
  }
}
</style>
