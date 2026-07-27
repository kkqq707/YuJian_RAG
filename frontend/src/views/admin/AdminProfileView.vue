<template>
  <div class="admin-profile-wrapper">
    <div class="admin-profile-page">
      <PageHeader title="个人中心" description="管理您的账户信息和安全设置" />

      <div class="profile-grid">
        <!-- 卡片一：基本信息 -->
        <div class="app-card profile-info-card">
          <h3 class="card-title">基本信息</h3>
          <div class="profile-info">
            <el-avatar :size="72" icon="UserFilled" class="profile-avatar" />
            <div class="profile-details">
              <div class="detail-row">
                <span class="detail-label">用户名</span>
                <span class="detail-value">{{ authStore.user?.username || '--' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">显示名称</span>
                <span class="detail-value">{{ authStore.displayName || '--' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">角色</span>
                <el-tag size="small" type="danger">管理员</el-tag>
              </div>
              <div class="detail-row">
                <span class="detail-label">账号状态</span>
                <span class="detail-value">
                  <span class="status-dot online" />
                  正常
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- 卡片二：账户安全 -->
        <div class="app-card profile-security-card">
          <h3 class="card-title">账户安全</h3>
          <p class="card-desc">修改您的登录密码，密码需至少 10 个字符且包含字母和数字</p>

          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-width="100px"
            label-position="top"
            class="password-form"
          >
            <el-form-item label="旧密码" prop="oldPassword">
              <el-input
                v-model="form.oldPassword"
                type="password"
                placeholder="请输入旧密码"
                show-password
                autocomplete="current-password"
              />
            </el-form-item>

            <el-form-item label="新密码" prop="newPassword">
              <el-input
                v-model="form.newPassword"
                type="password"
                placeholder="至少 10 个字符，需包含字母和数字"
                show-password
                autocomplete="new-password"
              />
            </el-form-item>

            <el-form-item label="确认新密码" prop="confirmPassword">
              <el-input
                v-model="form.confirmPassword"
                type="password"
                placeholder="请再次输入新密码"
                show-password
                autocomplete="new-password"
              />
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                :loading="changing"
                :disabled="changing"
                @click="handleChangePassword"
              >
                修改密码
              </el-button>
            </el-form-item>
          </el-form>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { validateNewPassword } from '@/utils/validators'
import PageHeader from '@/components/common/PageHeader.vue'

const router = useRouter()
const authStore = useAuthStore()

// ---- 修改密码表单 ----
const formRef = ref<FormInstance>()
const changing = ref(false)

const form = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const validateConfirmPassword = (_rule: unknown, value: string, callback: (error?: Error) => void) => {
  if (!value) {
    callback(new Error('请确认新密码'))
  } else if (value !== form.newPassword) {
    callback(new Error('两次输入的新密码不一致'))
  } else {
    callback()
  }
}

const rules: FormRules = {
  oldPassword: [
    { required: true, message: '请输入旧密码', trigger: 'blur' },
  ],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        const result = validateNewPassword(value)
        if (result === true) {
          callback()
        } else {
          callback(new Error(result))
        }
      },
      trigger: 'blur',
    },
  ],
  confirmPassword: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

async function handleChangePassword() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  changing.value = true
  try {
    await authStore.changePassword(form.oldPassword, form.newPassword)
    ElMessage.success('密码修改成功，请重新登录')
    router.push('/login')
  } catch (error: unknown) {
    const msg = (error as { response?: { data?: { message?: string } } })?.response?.data?.message
      || '密码修改失败'
    ElMessage.error(msg)
  } finally {
    changing.value = false
  }
}
</script>

<style lang="scss" scoped>
// ---- 外层居中容器 ----
.admin-profile-wrapper {
  display: flex;
  justify-content: center;
}

.admin-profile-page {
  max-width: 800px;
  width: 100%;
}

.profile-grid {
  display: flex;
  flex-direction: column;
  gap: $spacing-lg;
}

// ---- 卡片通用 ----
.card-title {
  font-size: $font-size-lg;
  font-weight: 600;
  color: $color-text-primary;
  margin-bottom: $spacing-lg;
}

.card-desc {
  font-size: $font-size-sm;
  color: $color-text-secondary;
  margin-bottom: $spacing-lg;
}

// ---- 基本信息卡片 ----
.profile-info {
  display: flex;
  align-items: flex-start;
  gap: $spacing-xl;
}

.profile-avatar {
  flex-shrink: 0;
}

.profile-details {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: $spacing-md;
}

.detail-row {
  display: flex;
  align-items: center;
  gap: $spacing-md;
}

.detail-label {
  width: 80px;
  flex-shrink: 0;
  font-size: $font-size-sm;
  color: $color-text-secondary;
}

.detail-value {
  font-size: $font-size-sm;
  color: $color-text-primary;
  display: flex;
  align-items: center;
  gap: $spacing-xs;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;

  &.online {
    background: $color-success;
  }
}

// ---- 账户安全卡片 ----
.password-form {
  max-width: 420px;
}
</style>
