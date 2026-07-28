<template>
  <div class="user-table-wrapper">
    <el-table
      :data="users"
      style="width: 100%"
      v-loading="loading"
      stripe
    >
      <!-- 用户名 -->
      <el-table-column prop="username" label="用户名" min-width="130">
        <template #default="scope">
          <span class="user-name-cell">{{ u(scope.row).username }}</span>
        </template>
      </el-table-column>

      <!-- 显示名称 -->
      <el-table-column prop="display_name" label="显示名称" min-width="120">
        <template #default="scope">
          {{ u(scope.row).display_name || '--' }}
        </template>
      </el-table-column>

      <!-- 邮箱 -->
      <el-table-column prop="email" label="邮箱" min-width="180" show-overflow-tooltip>
        <template #default="scope">
          {{ u(scope.row).email || '--' }}
        </template>
      </el-table-column>

      <!-- 角色 -->
      <el-table-column prop="role" label="角色" width="90" align="center">
        <template #default="scope">
          <el-tag size="small" :type="u(scope.row).role === 'admin' ? 'danger' : 'info'">
            {{ u(scope.row).role === 'admin' ? '管理员' : '普通用户' }}
          </el-tag>
        </template>
      </el-table-column>

      <!-- 状态 -->
      <el-table-column prop="is_active" label="状态" width="90" align="center">
        <template #default="scope">
          <StatusBadge
            :status="u(scope.row).is_active ? 'active' : 'disabled'"
            :label="u(scope.row).is_active ? '正常' : '已禁用'"
          />
        </template>
      </el-table-column>

      <!-- 最近登录 -->
      <el-table-column prop="last_login_at" label="最近登录" width="170">
        <template #default="scope">
          <span class="cell-time">{{ formatTime(u(scope.row).last_login_at) }}</span>
        </template>
      </el-table-column>

      <!-- 创建时间 -->
      <el-table-column prop="created_at" label="创建时间" width="170">
        <template #default="scope">
          <span class="cell-time">{{ formatTime(u(scope.row).created_at) }}</span>
        </template>
      </el-table-column>

      <!-- 操作 -->
      <el-table-column label="操作" width="280" align="center" fixed="right">
        <template #default="scope">
          <div class="action-group">
            <el-button
              link type="primary" size="small"
              @click="handleEdit(u(scope.row))"
            >
              编辑
            </el-button>
            <el-dropdown trigger="click" @command="(cmd: string) => handleCommand(cmd, u(scope.row))">
              <el-button link type="primary" size="small">
                更多<el-icon><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="role">修改角色</el-dropdown-item>
                  <el-dropdown-item command="reset-password">重置密码</el-dropdown-item>
                  <el-dropdown-item
                    v-if="u(scope.row).is_active"
                    command="disable"
                    :disabled="u(scope.row).id === currentUserId"
                  >
                    禁用
                  </el-dropdown-item>
                  <el-dropdown-item
                    v-else
                    command="enable"
                  >
                    启用
                  </el-dropdown-item>
                  <el-dropdown-item
                    command="delete"
                    divided
                    :disabled="u(scope.row).id === currentUserId"
                  >
                    <span class="delete-text">删除</span>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div v-if="total > 0" class="table-pagination">
      <el-pagination
        :current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ArrowDown } from '@element-plus/icons-vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import type { AdminUserItem } from '@/types/api'

defineProps<{
  users: AdminUserItem[]
  loading: boolean
  total: number
  pageSize: number
  currentPage: number
  currentUserId: number
}>()

const emit = defineEmits<{
  'edit': [user: AdminUserItem]
  'command': [command: string, user: AdminUserItem]
  'page-change': [page: number]
}>()

/** Type-safe row accessor for Element Plus table slots */
function u(row: unknown): AdminUserItem {
  return row as AdminUserItem
}

function formatTime(time: string | null): string {
  if (!time) return '--'
  return new Date(time).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function handleEdit(user: AdminUserItem): void {
  emit('edit', user)
}

function handleCommand(cmd: string, user: AdminUserItem): void {
  emit('command', cmd, user)
}

function handlePageChange(page: number): void {
  emit('page-change', page)
}
</script>

<style lang="scss" scoped>
.user-table-wrapper {
  // 横向滚动容器
  max-width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;

  .el-table {
    border-radius: $card-radius;
    min-width: 600px; // 保证小屏幕下表格可横向滚动
  }
}

.user-name-cell {
  font-weight: 500;
}

.cell-time {
  font-size: $font-size-sm;
  color: $color-text-secondary;
}

.action-group {
  display: flex;
  gap: 2px;
  justify-content: center;
  align-items: center;
}

.delete-text {
  color: #DC2626;
}

.table-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: $spacing-md;
}

// ---- 移动端适配 ----
@media (max-width: 767px) {
  .table-pagination {
    justify-content: center;

    :deep(.el-pagination) {
      .el-pagination__total {
        display: none;
      }
    }
  }
}
</style>
