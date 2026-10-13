<template>
  <div class="file-status-tracker">
    <div class="steps-row">
      <div
        v-for="(step, idx) in steps"
        :key="step.key"
        class="step-item"
        :class="getStepClass(idx)"
      >
        <div v-if="idx > 0" class="step-line" :class="getLineClass(idx)"></div>

        <div class="step-dot" :class="getDotClass(idx)">
          <svg v-if="isCompleted(idx)" viewBox="0 0 24 24" class="icon-check">
            <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" fill="currentColor"/>
          </svg>
          <svg v-else-if="isCurrent(idx) && !isError" viewBox="0 0 24 24" class="icon-loading">
            <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" fill="none" stroke-dasharray="31.4 31.4" stroke-linecap="round"/>
          </svg>
          <svg v-else-if="isCurrent(idx) && isError" viewBox="0 0 24 24" class="icon-error">
            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" fill="currentColor"/>
          </svg>
          <span v-else class="step-number">{{ idx + 1 }}</span>
        </div>

        <div class="step-label" :class="getLabelClass(idx)">
          {{ step.label }}
        </div>
      </div>
    </div>

    <div v-if="isError" class="error-tip">
      <el-tooltip :content="errorMessage || '处理失败，请点击重试'" placement="top">
        <span class="error-text">
          <el-icon><WarningFilled /></el-icon>
          {{ errorMessage ? (errorMessage.length > 30 ? errorMessage.substring(0, 30) + '...' : errorMessage) : '处理失败' }}
        </span>
      </el-tooltip>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { WarningFilled } from '@element-plus/icons-vue'

const props = defineProps({
  status: {
    type: String,
    required: true,
  },
  errorMessage: {
    type: String,
    default: '',
  },
})

// 定义步骤（与后端 FileStatus 完全对应）
const steps = [
  { key: 'uploaded',  label: '已上传' },
  { key: 'parsing',   label: '解析中' },
  { key: 'parsed',    label: '已解析' },
  { key: 'indexing',  label: '索引中' },
  { key: 'indexed',   label: '已完成' },
]

const statusToStepIndex = {
  uploaded:       0,
  parsing:        1,
  parsed:         2,
  indexing:       3,
  indexed:        4,
  error_parsing:  1,   // 解析阶段出错
  error_indexing: 3,   // 索引阶段出错
}

const currentIndex = computed(() => {
  return statusToStepIndex[props.status] ?? 0
})

const isError = computed(() => {
  return props.status === 'error_parsing' || props.status === 'error_indexing'
})

const isCompleted = (idx) => {
  if (isError.value) {
    return idx < currentIndex.value
  }
  return idx < currentIndex.value || (idx === currentIndex.value && props.status === 'indexed')
}

const isCurrent = (idx) => {
  return idx === currentIndex.value && props.status !== 'indexed'
}

const getStepClass = (idx) => {
  return {
    'is-completed': isCompleted(idx),
    'is-current': isCurrent(idx),
    'is-error': isCurrent(idx) && isError.value,
    'is-waiting': idx > currentIndex.value,
  }
}

const getDotClass = (idx) => {
  if (isCompleted(idx)) return 'dot-completed'
  if (isCurrent(idx) && isError.value) return 'dot-error'
  if (isCurrent(idx)) return 'dot-active'
  return 'dot-waiting'
}

const getLineClass = (idx) => {
  if (idx <= currentIndex.value && !isError.value) return 'line-completed'
  if (idx <= currentIndex.value && isError.value && idx < currentIndex.value) return 'line-completed'
  if (idx === currentIndex.value && isError.value) return 'line-error'
  return 'line-waiting'
}

const getLabelClass = (idx) => {
  if (isCompleted(idx)) return 'label-completed'
  if (isCurrent(idx) && isError.value) return 'label-error'
  if (isCurrent(idx)) return 'label-active'
  return 'label-waiting'
}
</script>

<style scoped>
.file-status-tracker {
  padding: 4px 0;
}

.steps-row {
  display: flex;
  align-items: center;
}

.step-item {
  display: flex;
  align-items: center;
  position: relative;
}

/* ---- 连接线 ---- */
.step-line {
  width: 24px;
  height: 2px;
  margin: 0 2px;
  border-radius: 1px;
  transition: background-color 0.3s;
}
.line-completed { background-color: #67c23a; }
.line-error     { background-color: #f56c6c; }
.line-waiting   { background-color: #dcdfe6; }

/* ---- 圆点 ---- */
.step-dot {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
  transition: all 0.3s;
  position: relative;
}

.dot-completed {
  background-color: #67c23a;
  color: white;
}

.dot-active {
  background-color: #0f766e;
  color: white;
  box-shadow: 0 0 0 4px rgba(15, 118, 110, 0.2);
  animation: pulse-accent 2s infinite;
}

.dot-error {
  background-color: #f56c6c;
  color: white;
  box-shadow: 0 0 0 4px rgba(245, 108, 108, 0.2);
}

.dot-waiting {
  background-color: #e4e7ed;
  color: #c0c4cc;
}

/* ---- 图标 ---- */
.icon-check {
  width: 14px;
  height: 14px;
}

.icon-loading {
  width: 14px;
  height: 14px;
  animation: spin 1s linear infinite;
}

.icon-error {
  width: 12px;
  height: 12px;
}

.step-number {
  font-size: 10px;
}

/* ---- 标签 ---- */
.step-label {
  font-size: 11px;
  margin-left: 4px;
  margin-right: 4px;
  white-space: nowrap;
  transition: color 0.3s;
}

.label-completed { color: #67c23a; font-weight: 500; }
.label-active    { color: #0f766e; font-weight: 600; }
.label-error     { color: #f56c6c; font-weight: 600; }
.label-waiting   { color: #c0c4cc; }

/* ---- 错误提示 ---- */
.error-tip {
  margin-top: 4px;
  padding-left: 4px;
}

.error-text {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #f56c6c;
  cursor: pointer;
  line-height: 1.2;
}

.error-text:hover {
  text-decoration: underline;
}

/* ---- 动画 ---- */
@keyframes spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}

@keyframes pulse-accent {
  0%   { box-shadow: 0 0 0 0 rgba(15, 118, 110, 0.4); }
  70%  { box-shadow: 0 0 0 8px rgba(15, 118, 110, 0); }
  100% { box-shadow: 0 0 0 0 rgba(15, 118, 110, 0); }
}
</style>
