<template>
  <div class="session-list">
    <!-- 顶部：新建对话 -->
    <div class="session-list__header">
      <el-button type="primary" class="new-chat-btn" @click="$emit('create')">
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
        @click="$emit('switch', session.id)"
      >
        <div class="session-item__content">
          <div class="session-item__title">
            <MessageSquare :size="14" class="session-item__icon" />
            <span class="truncate">{{ session.title }}</span>
          </div>
          <span class="session-item__time">{{ formatDate(session.updatedAt) }}</span>
        </div>

        <!-- Hover 操作按钮 -->
        <div class="session-item__actions">
          <el-tooltip content="重命名" :show-after="500">
            <el-button
              size="small"
              text
              class="session-item__action-btn"
              @click.stop="startRename(session)"
            >
              <Pencil :size="13" />
            </el-button>
          </el-tooltip>
          <el-tooltip content="删除" :show-after="500">
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
                  class="session-item__action-btn session-item__action-btn--danger"
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
      width="360px"
      :close-on-click-modal="false"
      @closed="renameValue = ''"
    >
      <el-input
        v-model="renameValue"
        placeholder="请输入新名称（1-30 字符）"
        :maxlength="30"
        :minlength="1"
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
}>()

const emit = defineEmits<{
  create: []
  switch: [sessionId: string]
  delete: [sessionId: string]
  rename: [sessionId: string, newTitle: string]
}>()

// 按 updatedAt 倒序
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
    return dayjs.utc(iso).local().format('YYYY-MM-DD')
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
}

.session-list__header {
  padding: $spacing-md;
  border-bottom: 1px solid $color-border;
}

.new-chat-btn {
  width: 100%;
}

.session-list__body {
  flex: 1;
  overflow-y: auto;
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

  &:hover {
    background: #f1f5f9;

    .session-item__actions {
      opacity: 1;
    }
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

.session-list__empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: $color-text-tertiary;
}
</style>
