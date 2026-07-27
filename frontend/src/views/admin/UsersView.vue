<template>
  <div class="users-page">
    <!-- 页面头部 -->
    <PageHeader
      title="用户管理"
      description="管理系统账号、角色和启用状态。"
    >
      <template #extra>
        <div class="header-actions">
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>
            新增用户
          </el-button>
          <el-button :loading="refreshing" @click="handleRefresh">
            <el-icon><RefreshCw /></el-icon>
            刷新
          </el-button>
        </div>
      </template>
    </PageHeader>

    <!-- 统计卡片 -->
    <div v-if="!store.error" class="stat-grid">
      <StatisticCard
        label="用户总数"
        :value="store.statistics.total_users"
        :icon="Users"
        icon-class="default"
        :loading="store.loading"
      />
      <StatisticCard
        label="管理员数"
        :value="store.statistics.admin_users"
        :icon="Shield"
        icon-class="danger"
        :loading="store.loading"
      />
      <StatisticCard
        label="普通用户数"
        :value="store.statistics.regular_users"
        :icon="User"
        icon-class="success"
        :loading="store.loading"
      />
      <StatisticCard
        label="已禁用用户数"
        :value="store.statistics.disabled_users"
        :icon="UserX"
        icon-class="warning"
        :loading="store.loading"
      />
    </div>

    <!-- 搜索与筛选 -->
    <div class="app-card filter-card">
      <div class="filter-row">
        <el-input
          v-model="store.filters.search"
          placeholder="搜索用户名或显示名称..."
          clearable
          class="filter-input"
          @clear="handleFilterChange"
          @keyup.enter="handleFilterChange"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>

        <el-select
          v-model="store.filters.role"
          placeholder="角色"
          clearable
          class="filter-select"
          @change="handleFilterChange"
        >
          <el-option label="全部角色" value="" />
          <el-option label="管理员" value="admin" />
          <el-option label="普通用户" value="user" />
        </el-select>

        <el-select
          v-model="store.filters.isActive"
          placeholder="状态"
          clearable
          class="filter-select"
          @change="handleFilterChange"
        >
          <el-option label="全部状态" value="" />
          <el-option label="正常" value="active" />
          <el-option label="已禁用" value="inactive" />
        </el-select>

        <el-button @click="handleResetFilters">重置筛选</el-button>
      </div>
    </div>

    <!-- 用户列表 -->
    <div class="app-card">
      <!-- Error state -->
      <div v-if="store.error" class="error-block">
        <EmptyState
          title="加载失败"
          :description="store.error"
          type="search"
        >
          <el-button type="primary" @click="handleRefresh">重新加载</el-button>
        </EmptyState>
      </div>

      <!-- Empty state -->
      <EmptyState
        v-else-if="!store.loading && store.users.length === 0"
        title="暂无用户"
        description='点击「新增用户」创建系统账号'
        type="default"
      >
        <el-button type="primary" @click="showCreateDialog = true">新增用户</el-button>
      </EmptyState>

      <!-- User table -->
      <UserTable
        v-else
        :users="store.users"
        :loading="store.loading"
        :total="store.pagination.total"
        :page-size="store.pagination.pageSize"
        :current-page="store.pagination.page"
        :current-user-id="authStore.user?.id || 0"
        @edit="handleEdit"
        @command="handleCommand"
        @page-change="handlePageChange"
      />
    </div>

    <!-- 新增用户 Dialog -->
    <CreateUserDialog
      v-model="showCreateDialog"
      @created="handleUserCreated"
    />

    <!-- 编辑用户 Dialog -->
    <EditUserDialog
      v-model="showEditDialog"
      :user="selectedUser"
      @updated="handleUserUpdated"
    />

    <!-- 修改角色 Dialog -->
    <ChangeRoleDialog
      v-model="showRoleDialog"
      :user="selectedUser"
      @changed="handleRoleChanged"
    />

    <!-- 重置密码 Dialog -->
    <ResetPasswordDialog
      v-model="showPasswordDialog"
      :user="selectedUser"
      @reset="handlePasswordReset"
    />

    <!-- 禁用确认 Dialog -->
    <ConfirmDialog
      v-model="showDisableDialog"
      title="禁用用户"
      :message="disableMessage"
      confirm-text="确认禁用"
      confirm-type="warning"
      @confirm="handleDisableConfirm"
    />

    <!-- 删除确认 Dialog -->
    <ConfirmDialog
      v-model="showDeleteDialog"
      title="删除用户"
      :message="deleteMessage"
      confirm-text="确认删除"
      confirm-type="danger"
      @confirm="handleDeleteConfirm"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useUsersStore } from '@/stores/users'
import { useAuthStore } from '@/stores/auth'
import { extractErrorMessage } from '@/utils/error'
import type { AdminUserItem } from '@/types/api'

import PageHeader from '@/components/common/PageHeader.vue'
import StatisticCard from '@/components/dashboard/StatisticCard.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import UserTable from '@/components/users/UserTable.vue'
import CreateUserDialog from '@/components/users/CreateUserDialog.vue'
import EditUserDialog from '@/components/users/EditUserDialog.vue'
import ChangeRoleDialog from '@/components/users/ChangeRoleDialog.vue'
import ResetPasswordDialog from '@/components/users/ResetPasswordDialog.vue'

import { Users, Shield, User, UserX, Plus, RefreshCw, Search } from '@lucide/vue'

const store = useUsersStore()
const authStore = useAuthStore()

const refreshing = ref(false)
const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const showRoleDialog = ref(false)
const showPasswordDialog = ref(false)
const showDisableDialog = ref(false)
const showDeleteDialog = ref(false)
const selectedUser = ref<AdminUserItem | null>(null)

const disableMessage = computed(() => {
  const name = selectedUser.value?.username || ''
  return `禁用后，用户 "${name}" 将无法继续登录，已有会话也将失效。`
})

const deleteMessage = computed(() => {
  const name = selectedUser.value?.username || ''
  return `删除后，用户 "${name}" 将无法登录，相关账号将进入停用状态。`
})

// ---- Lifecycle ----

onMounted(() => {
  store.refreshAll()
})

// ---- Actions ----

async function handleRefresh(): Promise<void> {
  refreshing.value = true
  try {
    await store.refreshAll()
  } finally {
    refreshing.value = false
  }
}

function handleFilterChange(): void {
  store.pagination.page = 1
  store.fetchUsers()
}

function handleResetFilters(): void {
  store.resetFilters()
  store.fetchUsers()
}

function handlePageChange(page: number): void {
  store.setPage(page)
  store.fetchUsers()
}

// ---- User operations ----

function handleEdit(user: AdminUserItem): void {
  selectedUser.value = user
  showEditDialog.value = true
}

function handleCommand(cmd: string, user: AdminUserItem): void {
  selectedUser.value = user

  switch (cmd) {
    case 'role':
      showRoleDialog.value = true
      break
    case 'reset-password':
      showPasswordDialog.value = true
      break
    case 'disable':
      showDisableDialog.value = true
      break
    case 'enable':
      handleEnableUser(user)
      break
    case 'delete':
      showDeleteDialog.value = true
      break
  }
}

async function handleEnableUser(user: AdminUserItem): Promise<void> {
  try {
    await store.enableUser(user.id)
    ElMessage.success('用户已启用')
  } catch (err: unknown) {
    ElMessage.error(extractErrorMessage(err))
  }
}

async function handleDisableConfirm(): Promise<void> {
  if (!selectedUser.value) return
  try {
    await store.disableUser(selectedUser.value.id)
    ElMessage.success('用户已禁用')
    showDisableDialog.value = false
  } catch (err: unknown) {
    ElMessage.error(extractErrorMessage(err))
  }
}

async function handleDeleteConfirm(): Promise<void> {
  if (!selectedUser.value) return
  try {
    await store.deleteUser(selectedUser.value.id)
    ElMessage.success('用户已删除')
    showDeleteDialog.value = false
  } catch (err: unknown) {
    ElMessage.error(extractErrorMessage(err))
  }
}

function handleUserCreated(): void {
  showCreateDialog.value = false
}

function handleUserUpdated(): void {
  showEditDialog.value = false
}

function handleRoleChanged(): void {
  showRoleDialog.value = false
}

function handlePasswordReset(): void {
  showPasswordDialog.value = false
}
</script>

<style lang="scss" scoped>
.users-page {
  max-width: 1440px;
}

.header-actions {
  display: flex;
  gap: $spacing-sm;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: $spacing-md;
  margin-bottom: $spacing-lg;
}

.filter-card {
  margin-bottom: $spacing-lg;
}

.filter-row {
  display: flex;
  gap: $spacing-sm;
  align-items: center;
  flex-wrap: wrap;
}

.filter-input {
  width: 260px;
  flex-shrink: 0;
}

.filter-select {
  width: 150px;
  flex-shrink: 0;
}

.error-block {
  padding: $spacing-lg 0;
}

@media (max-width: 1200px) {
  .stat-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .stat-grid {
    grid-template-columns: 1fr;
  }

  .filter-row {
    flex-direction: column;
  }

  .filter-input,
  .filter-select {
    width: 100%;
  }
}
</style>
