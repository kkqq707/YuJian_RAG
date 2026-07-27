<template>
  <el-dropdown trigger="click" @command="handleCommand">
    <div class="user-dropdown-trigger">
      <el-avatar :size="32" icon="UserFilled" />
      <span class="trigger-name">{{ authStore.displayName }}</span>
      <el-icon class="trigger-arrow"><ArrowDown /></el-icon>
    </div>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item command="profile">
          <el-icon><User /></el-icon>
          个人信息
        </el-dropdown-item>
        <el-dropdown-item divided command="logout">
          <el-icon><SwitchButton /></el-icon>
          退出登录
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { useChatStore } from '@/stores/chat'
import { ElMessageBox } from 'element-plus'

const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()
const chatStore = useChatStore()

async function handleCommand(command: string) {
  switch (command) {
    case 'profile':
      router.push(authStore.isAdmin ? '/admin/profile' : '/profile')
      break
    case 'logout':
      try {
        await ElMessageBox.confirm('确定要退出登录吗？', '退出确认', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning',
        })
      } catch {
        return
      }
      // 1. 重置用户相关 store
      chatStore.reset()
      // 2. 退出登录
      await authStore.logout()
      // 3. 重置应用 UI 状态
      appStore.reset()
      // 4. 跳转
      router.push('/login')
      break
  }
}
</script>

<style lang="scss" scoped>
.user-dropdown-trigger {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  cursor: pointer;
  padding: 4px $spacing-sm;
  border-radius: $control-radius;
  transition: background $transition-fast;

  &:hover {
    background: #f1f5f9;
  }
}

.trigger-name {
  font-size: $font-size-sm;
  color: $color-text-primary;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trigger-arrow {
  font-size: $font-size-xs;
  color: $color-text-tertiary;
}
</style>
