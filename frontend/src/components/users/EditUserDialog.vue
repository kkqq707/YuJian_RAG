<template>
  <el-dialog
    v-model="visible"
    title="编辑用户信息"
    width="480px"
    :close-on-click-modal="false"
    @closed="handleClosed"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="100px"
      label-position="left"
    >
      <el-form-item label="用户名">
        <el-input :model-value="user?.username" disabled />
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
          placeholder="请输入邮箱"
          :maxlength="320"
          clearable
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleCancel" :disabled="submitting">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          保存
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
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
  updated: []
}>()

const usersStore = useUsersStore()

const visible = ref(props.modelValue)
const isMobile = inject<Ref<boolean>>('isMobile', ref(false))
const formRef = ref<FormInstance>()
const submitting = ref(false)

const form = reactive({
  display_name: '',
  email: '',
})

const rules: FormRules = {
  email: [
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' },
  ],
}

watch(() => props.modelValue, (val) => {
  visible.value = val
  if (val && props.user) {
    form.display_name = props.user.display_name || ''
    form.email = props.user.email || ''
  }
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
    await usersStore.updateUser(props.user.id, {
      display_name: form.display_name || undefined,
      email: form.email || undefined,
    })
    ElMessage.success('用户信息已更新')
    emit('updated')
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
  form.display_name = ''
  form.email = ''
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
