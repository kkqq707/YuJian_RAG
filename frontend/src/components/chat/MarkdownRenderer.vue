<template>
  <div class="markdown-body" v-html="renderedHtml" />
</template>

<script setup lang="ts">
/**
 * 安全 Markdown 渲染组件
 *
 * 安全策略:
 * - 禁止执行 HTML、script、iframe
 * - 禁止 javascript: URL
 * - 链接默认新窗口打开并带安全 rel 属性
 * - 代码块可横向滚动
 * - 长链接自动换行
 * - 表格可横向滚动
 * - 图片自适应宽度
 */
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'

const props = defineProps<{
  content: string
}>()

// 创建 markdown-it 实例（不启用 HTML 标签）
const md = new MarkdownIt({
  html: false,        // 禁止 HTML 标签
  linkify: true,      // 自动识别链接
  breaks: true,       // 换行转为 <br>
  typographer: true,  // 智能引号等
})

// 自定义链接渲染：新窗口打开 + 安全 rel
const defaultRender =
  md.renderer.rules.link_open ||
  function (tokens, idx, options, _env, self) {
    return self.renderToken(tokens, idx, options)
  }

md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
  const token = tokens[idx]
  if (!token) return defaultRender(tokens, idx, options, env, self)

  const existingHref = token.attrGet('href') || ''

  // 检测危险协议
  const dangerousProtocols = /^(javascript|data|vbscript):/i
  if (dangerousProtocols.test(existingHref)) {
    token.attrSet('href', '#')
    token.attrSet('title', '链接已被移除（危险协议）')
  }

  token.attrSet('target', '_blank')
  token.attrSet('rel', 'noopener noreferrer nofollow')
  return defaultRender(tokens, idx, options, env, self)
}

// 渲染并清理
const renderedHtml = computed(() => {
  if (!props.content) return ''
  const rawHtml = md.render(props.content)
  return DOMPurify.sanitize(rawHtml, {
    ALLOWED_TAGS: [
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'p', 'br', 'hr',
      'ul', 'ol', 'li',
      'blockquote', 'pre', 'code',
      'strong', 'em', 'del', 's', 'sub', 'sup',
      'a', 'img',
      'table', 'thead', 'tbody', 'tr', 'th', 'td', 'caption',
      'div', 'span',
    ],
    ALLOWED_ATTR: ['href', 'target', 'rel', 'src', 'alt', 'title', 'class'],
    ALLOW_DATA_ATTR: false,
  })
})
</script>

<style lang="scss" scoped>
.markdown-body {
  font-size: $font-size-base;
  line-height: 1.75;
  color: $color-text-primary;
  word-wrap: break-word;
  overflow-wrap: anywhere;
  word-break: break-word;

  // 标题
  :deep(h1), :deep(h2), :deep(h3), :deep(h4), :deep(h5), :deep(h6) {
    margin: 1em 0 0.5em;
    font-weight: 600;
    color: $color-text-primary;
    line-height: 1.4;
  }
  :deep(h1) { font-size: 1.4em; }
  :deep(h2) { font-size: 1.25em; }
  :deep(h3) { font-size: 1.1em; }

  // 段落
  :deep(p) {
    margin: 0.5em 0;
    &:first-child { margin-top: 0; }
    &:last-child { margin-bottom: 0; }
  }

  // 列表
  :deep(ul), :deep(ol) {
    padding-left: 1.5em;
    margin: 0.5em 0;
  }
  :deep(li) {
    margin: 0.25em 0;
  }

  // 加粗
  :deep(strong) {
    font-weight: 600;
  }

  // 图片
  :deep(img) {
    max-width: 100%;
    height: auto;
    border-radius: 6px;
  }

  // 代码块
  :deep(pre) {
    max-width: 100%;
    background: #f8f9fa;
    border: 1px solid $color-border;
    border-radius: 6px;
    padding: $spacing-md;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    margin: 0.75em 0;
    font-size: 13px;
    line-height: 1.5;
  }

  :deep(code) {
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 0.9em;
    overflow-wrap: anywhere;
    word-break: break-word;
  }

  :deep(p code), :deep(li code) {
    background: #f0f0f0;
    padding: 2px 6px;
    border-radius: 3px;
  }

  // 引用
  :deep(blockquote) {
    border-left: 3px solid $color-primary;
    padding-left: $spacing-md;
    margin: 0.75em 0;
    color: $color-text-secondary;
    overflow-wrap: anywhere;
  }

  // 链接
  :deep(a) {
    color: $color-primary;
    text-decoration: none;
    word-break: break-all;
    overflow-wrap: anywhere;

    &:hover {
      text-decoration: underline;
    }
  }

  // 分割线
  :deep(hr) {
    border: none;
    border-top: 1px solid $color-border;
    margin: 1em 0;
  }

  // 表格 — 外层横向滚动
  :deep(table) {
    border-collapse: collapse;
    width: 100%;
    max-width: 100%;
    margin: 0.75em 0;
    display: block;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }
  :deep(th), :deep(td) {
    border: 1px solid $color-border;
    padding: 8px 12px;
    text-align: left;
    white-space: nowrap;
  }
  :deep(th) {
    background: #f8f9fa;
    font-weight: 600;
  }
}

// ================================================================
// 移动端适配 (< 768px)
// ================================================================
@media (max-width: 767px) {
  .markdown-body {
    font-size: 14px;
    line-height: 1.65;

    :deep(h1) { font-size: 1.25em; }
    :deep(h2) { font-size: 1.15em; }
    :deep(h3) { font-size: 1.05em; }

    :deep(pre) {
      padding: $spacing-sm;
      font-size: 12px;
    }

    :deep(blockquote) {
      padding-left: $spacing-sm;
      margin: 0.5em 0;
    }

    :deep(th), :deep(td) {
      padding: 6px 8px;
      font-size: $font-size-sm;
    }
  }
}
</style>
