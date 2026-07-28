<template>
  <el-dialog
    v-model="visible"
    title="重置密码"
    :width="isMobile ? 'calc(100vw - 24px)' : '460px'"
    :close-on-click-modal="false"
    @closed="handleClosed"
  >
    <p class="reset-info">
      为用户 <strong>{{ user?.username }}</strong> 设置新密码。
      密码重置后该用户所有设备将被登出。
    </p>

    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="100px"
      label-position="left"
    >
      <el-form-item label="新密码" prop="password">
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
          placeholder="请再次输入新密码"
          show-password
          autocomplete="new-password"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleCancel" :disabled="submitting">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          重置密码
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
import type { AdminUserItem } from '@/types/api'

const props = defineProps<{
  modelValue: boolean
  user: AdminUserItem | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  reset: []
}>()

const usersStore = useUsersStore()

const visible = ref(props.modelValue)
const isMobile = inject<Ref<boolean>>('isMobile', ref(false))
const formRef = ref<FormInstance>()
const submitting = ref(false)

const form = reactive({
  password: '',
  confirmPassword: '',
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
    callback(new Error('请输入新密码'))
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
  password: [
    { required: true, validator: validatePasswordStrength, trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

watch(() => props.modelValue, (val) => {
  visible.value = val
})
watch(visible, (val) => {
  emit('update:modelValue', val)
})

async function handleSubmit(): Promise<void> {
  if (!formRef.value || !props.user) return

  try {
    await formRef.value.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    await usersStore.resetPassword(props.user.id, form.password)
    ElMessage.success('密码已重置，用户需要重新登录')
    emit('reset')
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
  form.password = ''
  form.confirmPassword = ''
}
</script>

<style lang="scss" scoped>
.reset-info {
  font-size: $font-size-sm;
  color: $color-text-secondary;
  margin-bottom: $spacing-lg;
  line-height: 1.6;

  strong {
    color: $color-text-primary;
  }
}

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
