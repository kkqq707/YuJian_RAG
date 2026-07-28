<template>
  <div class="system-logs-page">
    <PageHeader title="系统日志" description="查看系统运行状态、异常信息和关键事件" />

    <!-- 筛选区域 -->
    <div class="app-card filter-card">
      <el-form :model="filters" inline class="filter-form">
        <el-form-item label="模块">
          <el-select
            v-model="filters.module"
            placeholder="全部模块"
            clearable
            style="width: 160px"
            @change="handleFilter"
          >
            <el-option label="全部" value="" />
            <el-option
              v-for="m in modules"
              :key="m.value"
              :label="m.label"
              :value="m.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="filters.status"
            placeholder="全部状态"
            clearable
            style="width: 130px"
            @change="handleFilter"
          >
            <el-option label="全部" value="" />
            <el-option label="成功" value="success" />
            <el-option label="失败" value="failed" />
            <el-option label="警告" value="warning" />
          </el-select>
        </el-form-item>
        <el-form-item label="用户">
          <el-input
            v-model="filters.username"
            placeholder="搜索用户名"
            clearable
            style="width: 180px"
            @clear="handleFilter"
            @keyup.enter="handleFilter"
          />
        </el-form-item>
        <el-form-item label="时间">
          <el-date-picker
            v-model="filters.timeRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 340px"
            @change="handleFilter"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleFilter">
            <el-icon><Search /></el-icon>
            查询
          </el-button>
          <el-button @click="handleReset">
            <el-icon><RefreshCw /></el-icon>
            重置
          </el-button>
          <el-button @click="fetchData" :loading="loading">
            <el-icon><RefreshCw /></el-icon>
            刷新
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 日志表格 -->
    <div class="app-card">
      <div v-if="loading" class="loading-area">
        <LoadingBlock variant="skeleton" :lines="10" />
      </div>

      <div v-else-if="error" class="error-area">
        <EmptyState title="加载失败" :description="error" type="search">
          <el-button type="primary" @click="fetchData">重新加载</el-button>
        </EmptyState>
      </div>

      <div v-else-if="items.length === 0" class="empty-area">
        <EmptyState title="暂无日志" description="当前筛选条件下没有找到系统日志" type="default" />
      </div>

      <template v-else>
        <el-table :data="items" stripe style="width: 100%" @row-click="handleRowClick">
          <el-table-column prop="created_at" label="时间" width="170">
            <template #default="{ row }">
              {{ formatTime(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column prop="username" label="用户" width="120" />
          <el-table-column prop="module" label="模块" width="110">
            <template #default="{ row }">
              <el-tag size="small" type="info" v-if="row.module">
                {{ moduleLabel(row.module) }}
              </el-tag>
              <span v-else>--</span>
            </template>
          </el-table-column>
          <el-table-column prop="action" label="操作" width="130">
            <template #default="{ row }">
              {{ actionLabel(row.action) }}
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <StatusBadge :status="row.status || 'success'" />
            </template>
          </el-table-column>
          <el-table-column prop="ip_address" label="IP" width="140" />
          <el-table-column prop="detail" label="详情" min-width="200" show-overflow-tooltip />
          <el-table-column label="操作" width="70" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click.stop="handleRowClick(row)">
                详情
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页 -->
        <div class="pagination-wrap">
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.pageSize"
            :total="total"
            :page-sizes="[20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="onPageSizeChange"
            @current-change="onPageChange"
          />
        </div>
      </template>
    </div>

    <!-- 详情 Drawer -->
    <el-drawer
      v-model="drawerVisible"
      title="日志详情"
      direction="rtl"
      :size="logDrawerSize"
    >
      <template v-if="selectedLog">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="日志 ID">
            {{ selectedLog.id }}
          </el-descriptions-item>
          <el-descriptions-item label="时间">
            {{ formatTime(selectedLog.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="用户">
            {{ selectedLog.username || '--' }}
          </el-descriptions-item>
          <el-descriptions-item label="模块">
            <el-tag size="small" v-if="selectedLog.module">
              {{ moduleLabel(selectedLog.module) }}
            </el-tag>
            <span v-else>--</span>
          </el-descriptions-item>
          <el-descriptions-item label="操作">
            {{ actionLabel(selectedLog.action) }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <StatusBadge :status="selectedLog.status || 'success'" />
          </el-descriptions-item>
          <el-descriptions-item label="目标类型">
            {{ selectedLog.target_type || '--' }}
          </el-descriptions-item>
          <el-descriptions-item label="目标 ID">
            {{ selectedLog.target_id || '--' }}
          </el-descriptions-item>
          <el-descriptions-item label="IP 地址">
            {{ selectedLog.ip_address || '--' }}
          </el-descriptions-item>
          <el-descriptions-item label="User-Agent" :span="1">
            <span class="ua-text">{{ selectedLog.user_agent || '--' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="详情">
            <div class="detail-text">{{ selectedLog.detail || '--' }}</div>
          </el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed, inject } from 'vue'
import type { Ref } from 'vue'
import adminSystemApi from '@/api/adminSystem'
import type { SystemLogItem, SystemLogDetail, ModuleItem } from '@/types/api'
import PageHeader from '@/components/common/PageHeader.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingBlock from '@/components/common/LoadingBlock.vue'
import { Search, RefreshCw } from '@lucide/vue'
import { extractErrorMessage } from '@/utils/error'
import dayjs from 'dayjs'

// ---- 响应式 ----
const isMobile = inject<Ref<boolean>>('isMobile', ref(false))
const logDrawerSize = computed(() => isMobile.value ? 'calc(100vw - 24px)' : '480px')

const loading = ref(true)
const error = ref('')
const items = ref<SystemLogItem[]>([])
const total = ref(0)
const modules = ref<ModuleItem[]>([])

const pagination = reactive({
  page: 1,
  pageSize: 50,
})

const filters = reactive({
  module: '',
  status: '',
  username: '',
  timeRange: null as [string, string] | null,
})

const drawerVisible = ref(false)
const selectedLog = ref<SystemLogDetail | null>(null)

// 模块标签映射
function moduleLabel(key: string): string {
  const map: Record<string, string> = {
    user_management: '用户管理',
    knowledge_base: '知识库',
    ai_service: 'AI服务',
    chat: '聊天',
    system: '系统',
  }
  return map[key] || key
}

// 操作标签映射
function actionLabel(action: string): string {
  const map: Record<string, string> = {
    admin_login: '管理员登录',
    login_success: '登录成功',
    login_failed: '登录失败',
    logout: '退出登录',
    file_upload: '上传文件',
    file_delete: '删除文件',
    file_index: '文件索引',
    index_rebuild: '重建索引',
    user_create: '创建用户',
    user_delete: '删除用户',
    user_disable: '禁用用户',
    user_enable: '启用用户',
    user_update: '修改用户',
    user_role_change: '修改角色',
    user_password_reset: '重置密码',
    llm_config_update: '修改AI配置',
    llm_connection_test: '测试API连接',
    model_switch: '切换模型',
    system_setting_update: '修改系统设置',
    jwt_regenerate: '重新生成JWT密钥',
  }
  return map[action] || action
}

function formatTime(time: string | null): string {
  if (!time) return '--'
  return dayjs(time).format('YYYY-MM-DD HH:mm:ss')
}

async function fetchData() {
  loading.value = true
  error.value = ''
  try {
    const params: Record<string, unknown> = {
      page: pagination.page,
      page_size: pagination.pageSize,
    }
    if (filters.module) params.module = filters.module
    if (filters.status) params.status = filters.status
    if (filters.username) params.username = filters.username
    if (filters.timeRange && filters.timeRange.length === 2) {
      params.start_time = filters.timeRange[0]
      params.end_time = filters.timeRange[1]
    }

    const result = await adminSystemApi.getSystemLogs(params)
    items.value = result.items
    total.value = result.total
  } catch (err: unknown) {
    error.value = extractErrorMessage(err)
  } finally {
    loading.value = false
  }
}

async function loadModules() {
  try {
    const result = await adminSystemApi.getModules()
    modules.value = result.modules
  } catch {
    // 模块列表加载失败不影响主功能
  }
}

function handleRowClick(row: unknown) {
  showDetail(row as SystemLogItem)
}

async function showDetail(row: SystemLogItem) {
  try {
    const detail = await adminSystemApi.getLogDetail(row.id)
    selectedLog.value = detail
    drawerVisible.value = true
  } catch {
    // 如果详情 API 失败，用列表数据填充
    selectedLog.value = { ...row, user_agent: null }
    drawerVisible.value = true
  }
}

function handleFilter() {
  pagination.page = 1
  fetchData()
}

function handleReset() {
  filters.module = ''
  filters.status = ''
  filters.username = ''
  filters.timeRange = null
  pagination.page = 1
  fetchData()
}

function onPageChange() {
  fetchData()
}

function onPageSizeChange() {
  pagination.page = 1
  fetchData()
}

onMounted(() => {
  loadModules()
  fetchData()
})
</script>

<style lang="scss" scoped>
.system-logs-page {
  width: 100%;
  max-width: var(--content-max-width);
  margin: 0 auto;
}

.filter-card {
  margin-bottom: $spacing-md;
}

.filter-form {
  .el-form-item {
    margin-bottom: 0;
  }
}

.loading-area,
.error-area,
.empty-area {
  padding: $spacing-xl 0;
}

// 表格横向滚动容器
:deep(.app-card > .el-table) {
  max-width: 100%;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: $spacing-md;
  padding: $spacing-sm 0;
}

.ua-text {
  font-size: $font-size-xs;
  word-break: break-all;
  color: $color-text-secondary;
}

.detail-text {
  white-space: pre-wrap;
  word-break: break-word;
  overflow-x: auto;
  max-width: 100%;
}

// ---- 移动端适配 ----
@media (max-width: 767px) {
  .filter-form {
    :deep(.el-form-item) {
      display: block;
      margin-bottom: $spacing-sm;
      width: 100%;

      .el-form-item__content {
        width: 100%;

        .el-select,
        .el-input,
        .el-date-editor {
          width: 100% !important;
        }
      }
    }
  }

  .pagination-wrap {
    justify-content: center;

    :deep(.el-pagination) {
      .el-pagination__sizes,
      .el-pagination__total {
        display: none;
      }
    }
  }
}
</style>
