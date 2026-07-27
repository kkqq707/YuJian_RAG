<template>
  <el-dialog
    v-model="visible"
    title="修改用户角色"
    width="460px"
    :close-on-click-modal="false"
    @closed="handleClosed"
  >
    <div class="role-info">
      <p class="role-user">用户: <strong>{{ user?.username }}</strong></p>
      <p class="role-current">
        当前角色:
        <el-tag size="small" :type="user?.role === 'admin' ? 'danger' : 'info'">
          {{ user?.role === 'admin' ? '管理员' : '普通用户' }}
        </el-tag>
      </p>
    </div>

    <el-form label-width="80px" label-position="left" class="role-form">
      <el-form-item label="新角色">
        <el-select v-model="selectedRole" style="width: 100%">
          <el-option label="普通用户" value="user" />
          <el-option label="管理员" value="admin" />
        </el-select>
      </el-form-item>
    </el-form>

    <el-alert
      v-if="isDowngrade"
      type="warning"
      :closable="false"
      show-icon
      title="角色降低后，用户所有 Token 将被撤销，需重新登录。"
      class="role-alert"
    />

    <el-alert
      v-if="isUpgrade"
      type="info"
      :closable="false"
      show-icon
      title="提升为管理员后，用户将获得完整管理权限。"
      class="role-alert"
    />

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleCancel" :disabled="submitting">取消</el-button>
        <el-button
          :type="isDowngrade ? 'warning' : 'primary'"
          :loading="submitting"
          :disabled="selectedRole === user?.role"
          @click="handleSubmit"
        >
          确认修改
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useUsersStore } from '@/stores/users'
import { extractErrorMessage } from '@/utils/error'
import type { AdminUserItem } from '@/types/api'

const props = defineProps<{
  modelValue: boolean
  user: AdminUserItem | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  changed: []
}>()

const usersStore = useUsersStore()

const visible = ref(props.modelValue)
const selectedRole = ref('')
const submitting = ref(false)

const isDowngrade = computed(() => {
  return props.user?.role === 'admin' && selectedRole.value === 'user'
})

const isUpgrade = computed(() => {
  return props.user?.role === 'user' && selectedRole.value === 'admin'
})

watch(() => props.modelValue, (val) => {
  visible.value = val
  if (val && props.user) {
    selectedRole.value = props.user.role
  }
})
watch(visible, (val) => {
  emit('update:modelValue', val)
})

async function handleSubmit(): Promise<void> {
  if (!props.user || selectedRole.value === props.user.role) return

  submitting.value = true
  try {
    await usersStore.changeRole(props.user.id, selectedRole.value)
    ElMessage.success('角色修改成功')
    emit('changed')
    visible.value = false
  } catch (err: unknown) {
    ElMessage.error(extractErrorMessage(err))
  } finally {
    submitting.value = false
  }
}

function handleCancel(): void {
  visible.value = false
}

function handleClosed(): void {
  selectedRole.value = ''
}
</script>

<style lang="scss" scoped>
.role-info {
  margin-bottom: $spacing-md;
}

.role-user {
  font-size: $font-size-base;
  margin-bottom: $spacing-sm;
}

.role-current {
  font-size: $font-size-sm;
  color: $color-text-secondary;
  display: flex;
  align-items: center;
  gap: $spacing-sm;
}

.role-form {
  margin-top: $spacing-md;
}

.role-alert {
  margin-top: $spacing-sm;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: $spacing-sm;
}
</style>
