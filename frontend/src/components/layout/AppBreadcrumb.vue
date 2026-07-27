<template>
  <el-breadcrumb separator="/" class="app-breadcrumb">
    <el-breadcrumb-item v-for="item in breadcrumbs" :key="item.path" :to="item.path">
      {{ item.title }}
    </el-breadcrumb-item>
  </el-breadcrumb>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const breadcrumbs = computed(() => {
  const items: Array<{ path: string; title: string }> = []
  const matched = route.matched

  for (const record of matched) {
    const title = (record.meta?.title as string) || ''
    if (title && record.path) {
      items.push({
        path: record.path,
        title,
      })
    }
  }

  return items
})
</script>

<style lang="scss" scoped>
.app-breadcrumb {
  font-size: $font-size-sm;
}
</style>
