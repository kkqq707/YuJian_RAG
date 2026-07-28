<template>
  <el-dialog
    v-model="visible"
    title="新增用户"
    :width="isMobile ? 'calc(100vw - 24px)' : '520px'"
    :close-on-click-modal="false"
    @closed="handleClosed"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      :label-width="isMobile ? '80px' : '100px'"
      label-position="left"
    >
      <el-form-item label="用户名" prop="username">
        <el-input
          v-model="form.username"
          placeholder="请输入用户名"
          :maxlength="150"
          clearable
        />
      </el-form-item>

      <el-form-item label="显示名称" prop="display_name">
        <el-input
          v-model="form.display_name"
          placeholder="请输入显示名称"
          :maxlength="255"
          clearable
        />
      </el-form-item>

      <el-form-item label="邮箱" prop="email">
        <el-input
          v-model="form.email"
          placeholder="请输入邮箱（选填）"
          :maxlength="320"
          clearable
        />
      </el-form-item>

      <el-form-item label="角色" prop="role">
        <el-select v-model="form.role" style="width: 100%">
          <el-option label="普通用户" value="user" />
          <el-option label="管理员" value="admin" />
        </el-select>
      </el-form-item>

      <el-form-item label="初始密码" prop="password">
        <el-input
          v-model="form.password"
          type="password"
          placeholder="至少10位，需包含字母和数字"
          show-password
          autocomplete="new-password"
        />
      </el-form-item>

      <el-form-item label="确认密码" prop="confirmPassword">
        <el-input
          v-model="form.confirmPassword"
          type="password"
          placeholder="请再次输入密码"
          show-password
          autocomplete="new-password"
        />
      </el-form-item>

      <el-form-item label="启用状态">
        <el-switch v-model="form.is_active" active-text="启用" inactive-text="禁用" />
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleCancel" :disabled="submitting">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          创建用户
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch, inject } from 'vue'
import type { Ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { useUsersStore } from '@/stores/users'
import { extractErrorMessage } from '@/utils/error'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  created: []
}>()

const usersStore = useUsersStore()

const visible = ref(props.modelValue)
const isMobile = inject<Ref<boolean>>('isMobile', ref(false))
const formRef = ref<FormInstance>()
const submitting = ref(false)

const form = reactive({
  username: '',
  display_name: '',
  email: '',
  role: 'user',
  password: '',
  confirmPassword: '',
  is_active: true,
})

const validateConfirmPassword = (_rule: unknown, value: string, callback: (err?: Error) => void) => {
  if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const validatePasswordStrength = (_rule: unknown, value: string, callback: (err?: Error) => void) => {
  if (!value) {
    callback(new Error('请输入密码'))
    return
  }
  if (value.length < 10) {
    callback(new Error('密码至少需要10个字符'))
    return
  }
  if (!/[a-zA-Z]/.test(value)) {
    callback(new Error('密码必须包含字母'))
    return
  }
  if (!/[0-9]/.test(value)) {
    callback(new Error('密码必须包含数字'))
    return
  }
  callback()
}

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 1, max: 150, message: '用户名长度在1-150个字符之间', trigger: 'blur' },
  ],
  password: [
    { required: true, validator: validatePasswordStrength, trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
  email: [
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' },
  ],
}

watch(() => props.modelValue, (val) => {
  visible.value = val
})
watch(visible, (val) => {
  emit('update:modelValue', val)
})

async function handleSubmit(): Promise<void> {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    await usersStore.createUser({
      username: form.username,
      password: form.password,
      display_name: form.display_name || undefined,
      email: form.email || undefined,
      role: form.role,
    })
    ElMessage.success('用户创建成功')
    emit('created')
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
  formRef.value?.resetFields()
  form.username = ''
  form.display_name = ''
  form.email = ''
  form.role = 'user'
  form.password = ''
  form.confirmPassword = ''
  form.is_active = true
}
</script>

<style lang="scss" scoped>
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: $spacing-sm;

  @media (max-width: 767px) {
    flex-direction: column;

    .el-button {
      width: 100%;
      margin-left: 0 !important;
      min-height: var(--touch-target-min);
    }
  }
}
</style>
