<template>
  <div class="admin-page">
    <div class="page-header">
      <div>
        <h2>审计日志</h2>
        <p>记录关键操作，支持筛选与详情查看</p>
      </div>
      <div class="header-actions">
        <el-button @click="loadLogs" :loading="loading">刷新</el-button>
      </div>
    </div>

    <el-card shadow="never">
      <div class="toolbar">
        <el-select
          v-model="filters.userId"
          clearable
          filterable
          placeholder="筛选操作者"
          style="width: 200px"
        >
          <el-option
            v-for="u in users"
            :key="u.id"
            :label="`${u.username} (ID:${u.id})`"
            :value="u.id"
          />
        </el-select>
        <el-select v-model="filters.action" clearable placeholder="筛选动作" style="width: 200px">
          <el-option
            v-for="item in actionOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-select v-model="filters.status" clearable placeholder="筛选结果" style="width: 140px">
          <el-option label="成功" value="success" />
          <el-option label="失败" value="failed" />
        </el-select>
        <el-date-picker
          v-model="filters.dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
        />
        <el-input
          v-model="filters.keyword"
          placeholder="资源名/操作者"
          clearable
          style="width: 200px"
        />
        <el-button type="primary" @click="applyFilters">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>

      <el-table :data="logs" v-loading="loading" border>
        <el-table-column label="时间" min-width="170">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="actor_username" label="操作者" min-width="140" />
        <el-table-column label="动作" min-width="160">
          <template #default="{ row }">
            {{ formatAction(row.action) }}
          </template>
        </el-table-column>
        <el-table-column label="资源" min-width="200">
          <template #default="{ row }">
            <div class="resource-cell">
              <span class="resource-type">{{ row.resource_type }}</span>
              <span class="resource-name">
                {{ row.resource_name || row.resource_id || '-' }}
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="结果" width="120">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : 'danger'">
              {{ formatStatus(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ip" label="IP" width="140" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          @current-change="loadLogs"
          @size-change="handleSizeChange"
        />
      </div>
    </el-card>

    <el-drawer v-model="drawerVisible" size="40%" title="日志详情">
      <div class="detail-meta">
        <div><strong>动作:</strong> {{ formatAction(selectedLog.action) }}</div>
        <div><strong>操作者:</strong> {{ selectedLog.actor_username || '-' }}</div>
        <div><strong>资源:</strong> {{ selectedLog.resource_name || selectedLog.resource_id || '-' }}</div>
        <div><strong>结果:</strong> {{ formatStatus(selectedLog.status) }}</div>
        <div><strong>IP:</strong> {{ selectedLog.ip || '-' }}</div>
        <div><strong>UA:</strong> {{ selectedLog.user_agent || '-' }}</div>
      </div>
      <div class="detail-json">
        <div class="detail-title">详情</div>
        <pre>{{ formattedDetail }}</pre>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchAllUsers, fetchAuditLogs } from '@/api/index'

const loading = ref(false)
const users = ref([])
const logs = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const filters = ref({
  userId: null,
  action: '',
  status: '',
  dateRange: null,
  keyword: '',
})

const ACTION_LABEL_MAP = {
  'user.update': '用户更新',
  'user.status.change': '用户状态变更',
  'user.profile.update': '个人资料修改',
  'user.password.change': '修改密码',
  'user.avatar.upload': '上传头像',
  'kb.create': '创建知识库',
  'kb.update': '更新知识库',
  'kb.delete': '删除知识库',
  'file.upload': '上传文件',
  'file.replace': '覆盖文件',
  'file.delete': '删除文件',
  'file.retry': '重试文件',
  'session.delete': '删除会话',
  'session.rename': '重命名会话',
  'agent.intent.classify': '意图分类',
}

const STATUS_LABEL_MAP = {
  success: '成功',
  failed: '失败',
}

const actionOptions = computed(() =>
  Object.entries(ACTION_LABEL_MAP).map(([value, label]) => ({ value, label }))
)
const drawerVisible = ref(false)
const selectedLog = ref({})

const formattedDetail = computed(() => {
  if (!selectedLog.value?.detail) return '-'
  try {
    return JSON.stringify(selectedLog.value.detail, null, 2)
  } catch {
    return String(selectedLog.value.detail)
  }
})

const formatAction = (value) => {
  if (!value) return '-'
  return ACTION_LABEL_MAP[value] || value
}

const formatStatus = (value) => {
  if (!value) return '-'
  return STATUS_LABEL_MAP[value] || value
}

const formatDate = (value) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', { hour12: false })
}

const loadUsers = async () => {
  try {
    const res = await fetchAllUsers()
    users.value = res.data || []
  } catch (err) {
    const msg = err?.response?.data?.detail || '加载用户失败'
    ElMessage.error(msg)
  }
}

const buildParams = () => {
  const params = {
    page: page.value,
    page_size: pageSize.value,
  }
  if (filters.value.userId) params.user_id = filters.value.userId
  if (filters.value.action) params.action = filters.value.action
  if (filters.value.status) params.status = filters.value.status
  if (filters.value.keyword) params.keyword = filters.value.keyword.trim()
  if (filters.value.dateRange?.length === 2) {
    params.date_from = filters.value.dateRange[0]
    params.date_to = filters.value.dateRange[1]
  }
  return params
}

const loadLogs = async () => {
  loading.value = true
  try {
    const res = await fetchAuditLogs(buildParams())
    logs.value = res.data?.items || []
    total.value = res.data?.total || 0
  } catch (err) {
    const msg = err?.response?.data?.detail || '加载日志失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

const applyFilters = () => {
  page.value = 1
  loadLogs()
}

const resetFilters = () => {
  filters.value = {
    userId: null,
    action: '',
    status: '',
    dateRange: null,
    keyword: '',
  }
  page.value = 1
  loadLogs()
}

const handleSizeChange = () => {
  page.value = 1
  loadLogs()
}

const openDetail = (row) => {
  selectedLog.value = row || {}
  drawerVisible.value = true
}

onMounted(async () => {
  await loadUsers()
  await loadLogs()
})
</script>

<style scoped>
.admin-page {
  --admin-ink: #183642;
  --admin-subtle: #6c7f86;
  --admin-line: rgba(24, 54, 66, 0.1);
  --admin-card: rgba(255, 252, 247, 0.94);
  padding: 8px 0 0;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 18px;
  padding: 0 4px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  color: var(--admin-ink);
}

.page-header p {
  margin: 8px 0 0;
  color: var(--admin-subtle);
}

.header-actions {
  display: flex;
  gap: 12px;
}

.toolbar {
  margin-bottom: 18px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  padding: 18px;
  border-radius: 22px;
  border: 1px solid var(--admin-line);
  background:
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.72), transparent 42%),
    rgba(242, 238, 230, 0.7);
}

.pager {
  margin-top: 18px;
  display: flex;
  justify-content: flex-end;
}

.resource-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.resource-type {
  font-size: 12px;
  color: #64748b;
}

.resource-name {
  color: #111827;
}

.detail-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
  font-size: 13px;
  padding: 18px;
  border-radius: 20px;
  border: 1px solid rgba(24, 54, 66, 0.08);
  background: rgba(255, 255, 255, 0.78);
}

.detail-json {
  background: linear-gradient(180deg, rgba(250, 248, 243, 0.96), rgba(243, 238, 229, 0.88));
  border-radius: 22px;
  padding: 16px 18px;
  border: 1px solid rgba(24, 54, 66, 0.08);
}

.detail-title {
  font-weight: 600;
  margin-bottom: 8px;
}

.detail-json pre {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}

:deep(.el-card) {
  border-radius: 28px;
  border: 1px solid var(--admin-line);
  background: var(--admin-card);
  box-shadow: 0 18px 40px rgba(24, 54, 66, 0.08);
}

:deep(.el-card__body) {
  padding: 22px;
}

:deep(.el-table) {
  border-radius: 22px;
  overflow: hidden;
  border: 1px solid rgba(24, 54, 66, 0.08);
  --el-table-border-color: rgba(24, 54, 66, 0.08);
  --el-table-row-hover-bg-color: rgba(24, 119, 104, 0.06);
  --el-table-header-bg-color: rgba(245, 240, 232, 0.9);
  --el-table-bg-color: rgba(255, 255, 255, 0.75);
  --el-fill-color-blank: transparent;
}

:deep(.el-table::before) {
  display: none;
}

:deep(.el-table th.el-table__cell) {
  padding: 15px 0;
  color: var(--admin-ink);
  font-weight: 600;
  background: rgba(245, 240, 232, 0.9);
}

:deep(.el-table td.el-table__cell) {
  padding: 15px 0;
}

:deep(.el-button) {
  border-radius: 15px;
  min-height: 40px;
  padding: 0 16px;
  border-color: rgba(24, 54, 66, 0.12);
  box-shadow: none;
}

:deep(.el-button--default) {
  background: rgba(255, 255, 255, 0.84);
  color: var(--admin-ink);
}

:deep(.el-button--primary) {
  background: linear-gradient(135deg, #1f7a73, #305c72);
  border-color: transparent;
}

:deep(.el-button.is-link) {
  min-height: auto;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(24, 54, 66, 0.06);
}

:deep(.el-input__wrapper),
:deep(.el-select__wrapper) {
  border-radius: 16px;
  min-height: 44px;
  box-shadow: 0 0 0 1px rgba(24, 54, 66, 0.08) inset;
  background: rgba(255, 255, 255, 0.86);
}

:deep(.el-range-editor.el-input__wrapper) {
  padding: 0 14px;
}

:deep(.el-pagination button),
:deep(.el-pagination .number) {
  border-radius: 12px;
}

:deep(.el-drawer) {
  border-top-left-radius: 28px;
  border-bottom-left-radius: 28px;
  overflow: hidden;
  background: rgba(255, 252, 247, 0.98);
}

:deep(.el-drawer__header) {
  margin-bottom: 0;
  padding: 22px 24px 12px;
  color: var(--admin-ink);
}

:deep(.el-drawer__body) {
  padding: 16px 24px 24px;
}
</style>
