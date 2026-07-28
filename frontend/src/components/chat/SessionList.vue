<template>
  <div class="session-list">
    <!-- 顶部：新建对话 -->
    <div class="session-list__header">
      <el-button
        type="primary"
        class="new-chat-btn touch-target"
        aria-label="新建对话"
        @click="$emit('create')"
      >
        <Plus :size="16" />
        <span>新建对话</span>
      </el-button>
    </div>

    <!-- 会话列表 -->
    <div class="session-list__body" v-if="sessions.length > 0">
      <div
        v-for="session in sortedSessions"
        :key="session.id"
        class="session-item"
        :class="{ 'session-item--active': session.id === activeId }"
        role="button"
        :tabindex="0"
        :aria-label="`${session.title}${session.id === activeId ? '，当前对话' : ''}`"
        :aria-current="session.id === activeId ? 'true' : undefined"
        @click="$emit('switch', session.id)"
        @keydown.enter="$emit('switch', session.id)"
        @keydown.space.prevent="$emit('switch', session.id)"
      >
        <div class="session-item__content">
          <div class="session-item__title">
            <MessageSquare :size="14" class="session-item__icon" />
            <span class="truncate">{{ session.title }}</span>
          </div>
          <span class="session-item__time">{{ formatDate(session.updatedAt) }}</span>
        </div>

        <!-- 操作按钮：桌面端 hover 显示，移动端始终可见 -->
        <div class="session-item__actions" :class="{ 'session-item__actions--visible': isMobile }">
          <el-tooltip content="重命名" :show-after="500" :disabled="isMobile">
            <el-button
              size="small"
              text
              class="session-item__action-btn touch-target-min"
              aria-label="重命名对话"
              @click.stop="startRename(session)"
            >
              <Pencil :size="13" />
            </el-button>
          </el-tooltip>
          <el-tooltip content="删除" :show-after="500" :disabled="isMobile">
            <el-popconfirm
              title="确定要删除此对话吗？"
              confirm-button-text="删除"
              cancel-button-text="取消"
              width="220"
              @confirm="$emit('delete', session.id)"
            >
              <template #reference>
                <el-button
                  size="small"
                  text
                  class="session-item__action-btn session-item__action-btn--danger touch-target-min"
                  aria-label="删除对话"
                  @click.stop
                >
                  <Trash2 :size="13" />
                </el-button>
              </template>
            </el-popconfirm>
          </el-tooltip>
        </div>
      </div>
    </div>

    <!-- 无会话 -->
    <div v-else class="session-list__empty">
      <span class="text-tertiary text-sm">暂无对话记录</span>
    </div>

    <!-- 重命名弹窗 -->
    <el-dialog
      v-model="renameVisible"
      title="重命名对话"
      :width="isMobile ? '90vw' : '360px'"
      :close-on-click-modal="false"
      @closed="renameValue = ''"
    >
      <el-input
        v-model="renameValue"
        placeholder="请输入新名称（1-30 字符）"
        :maxlength="30"
        :minlength="1"
        aria-label="对话新名称"
        @keyup.enter="confirmRename"
      />
      <template #footer>
        <el-button @click="renameVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!renameValue.trim()" @click="confirmRename">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Plus, MessageSquare, Pencil, Trash2 } from '@lucide/vue'
import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import type { ChatSession } from '@/types/chat'

dayjs.extend(utc)

const props = defineProps<{
  sessions: ChatSession[]
  activeId: string | null
  isMobile?: boolean
}>()

const emit = defineEmits<{
  create: []
  switch: [sessionId: string]
  delete: [sessionId: string]
  rename: [sessionId: string, newTitle: string]
}>()

const sortedSessions = computed(() => {
  return [...props.sessions].sort(
    (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
  )
})

// 重命名
const renameVisible = ref(false)
const renameTargetId = ref<string | null>(null)
const renameValue = ref('')

function startRename(session: ChatSession) {
  renameTargetId.value = session.id
  renameValue.value = session.title
  renameVisible.value = true
}

function confirmRename() {
  const title = renameValue.value.trim()
  if (title && renameTargetId.value) {
    emit('rename', renameTargetId.value, title)
  }
  renameVisible.value = false
  renameValue.value = ''
}

function formatDate(iso: string): string {
  try {
    return dayjs.utc(iso).local().format('MM-DD')
  } catch {
    return ''
  }
}
</script>

<style lang="scss" scoped>
.session-list {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.session-list__header {
  padding: $spacing-md;
  border-bottom: 1px solid $color-border;
  flex-shrink: 0;
}

.new-chat-btn {
  width: 100%;
}

.session-list__body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
  padding: $spacing-xs 0;
}

.session-item {
  position: relative;
  display: flex;
  align-items: center;
  padding: 10px $spacing-md;
  margin: 2px $spacing-sm;
  border-radius: $control-radius;
  cursor: pointer;
  transition: all $transition-fast;
  gap: $spacing-xs;
  min-height: var(--touch-target-min);

  &:hover {
    background: #f1f5f9;

    .session-item__actions {
      opacity: 1;
    }
  }

  &:focus-visible {
    outline: 2px solid $color-primary;
    outline-offset: -2px;
  }

  &--active {
    background: $color-primary-light;
    color: $color-primary;

    .session-item__title {
      color: $color-primary;
    }
  }
}

.session-item__content {
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.session-item__title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: $font-size-sm;
  color: $color-text-primary;
  margin-bottom: 2px;
}

.session-item__icon {
  flex-shrink: 0;
  color: $color-text-tertiary;
}

.session-item__time {
  font-size: $font-size-xs;
  color: $color-text-tertiary;
  padding-left: 20px;
}

.session-item__actions {
  display: flex;
  align-items: center;
  gap: 2px;
  opacity: 0;
  transition: opacity $transition-fast;
  flex-shrink: 0;

  &--visible {
    opacity: 1;
  }
}

.session-item__action-btn {
  color: $color-text-tertiary;
  padding: 2px !important;
  min-height: auto !important;

  &:hover {
    color: $color-text-primary;
    background: rgba(0, 0, 0, 0.04);
  }

  &--danger:hover {
    color: $color-danger;
    background: #fef2f2;
  }
}

.touch-target-min {
  min-height: var(--touch-target-min);
  min-width: var(--touch-target-min);
}

.session-list__empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: $color-text-tertiary;
}

// ================================================================
// 移动端适配 (< 768px)
// ================================================================
@media (max-width: 767px) {
  .session-list__header {
    padding: $spacing-sm;
  }

  .session-item {
    padding: 12px $spacing-sm;
    margin: 2px $spacing-xs;
  }
}
</style>
