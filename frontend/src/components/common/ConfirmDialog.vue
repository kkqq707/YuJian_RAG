<template>
  <el-dialog
    v-model="visible"
    :title="title"
    :width="width"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    @closed="handleClosed"
  >
    <p class="confirm-body">{{ message }}</p>
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleCancel" class="touch-target">{{ cancelText }}</el-button>
        <el-button :type="confirmType" :loading="loading" @click="handleConfirm" class="touch-target">
          {{ confirmText }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  modelValue: boolean
  title?: string
  message?: string
  confirmText?: string
  cancelText?: string
  confirmType?: 'primary' | 'danger' | 'warning'
  width?: string
}>(), {
  title: '确认操作',
  message: '确定要执行此操作吗？',
  confirmText: '确定',
  cancelText: '取消',
  confirmType: 'danger',
  width: '420px',
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  confirm: []
  cancel: []
}>()

const visible = ref(props.modelValue)
const loading = ref(false)

watch(() => props.modelValue, (val) => {
  visible.value = val
})

watch(visible, (val) => {
  emit('update:modelValue', val)
})

function handleConfirm() {
  loading.value = true
  emit('confirm')
}

function handleCancel() {
  visible.value = false
  emit('cancel')
}

function handleClosed() {
  loading.value = false
}

defineExpose({ setLoading: (val: boolean) => { loading.value = val } })
</script>

<style lang="scss" scoped>
.confirm-body {
  font-size: $font-size-base;
  color: $color-text-secondary;
  line-height: 1.6;
  word-break: break-word;
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
    }
  }
}
</style>
