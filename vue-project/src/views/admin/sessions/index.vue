<template>
  <div class="admin-page">
    <div class="page-header">
      <div>
        <h2>对话管理</h2>
        <p>按用户查看会话列表，并支持查看会话消息</p>
      </div>
      <div class="header-actions">
        <el-button @click="loadData" :loading="loading">刷新</el-button>
      </div>
    </div>

    <el-card shadow="never">
      <div class="toolbar">
        <el-select
          v-model="selectedUserId"
          clearable
          filterable
          placeholder="筛选用户"
          style="width: 220px"
        >
          <el-option
            v-for="u in users"
            :key="u.id"
            :label="`${u.username} (ID:${u.id})`"
            :value="u.id"
          />
        </el-select>
        <el-input
          v-model="keyword"
          placeholder="按会话标题或会话ID搜索"
          clearable
          style="max-width: 320px"
        />
      </div>

      <el-table :data="filteredSessions" v-loading="loading" border>
        <el-table-column prop="id" label="会话ID" min-width="220" show-overflow-tooltip />
        <el-table-column prop="title" label="标题" min-width="180" />
        <el-table-column label="用户" min-width="160">
          <template #default="{ row }">
            {{ getUsername(row.user_id) }} ({{ row.user_id || '-' }})
          </template>
        </el-table-column>
        <el-table-column prop="kb_id" label="知识库ID" width="110" />
        <el-table-column label="创建时间" min-width="170">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewMessages(row)">查看消息</el-button>
            <el-button type="danger" link @click="deleteSession(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="drawerVisible" size="45%" :title="drawerTitle">
      <div v-loading="messagesLoading" class="message-list">
        <el-empty v-if="!messagesLoading && messages.length === 0" description="暂无消息记录" />
        <div v-for="(msg, idx) in messages" :key="idx" class="msg-item">
          <div class="msg-meta">
            <el-tag :type="msg.role === 'user' ? 'primary' : 'success'" effect="plain">
              {{ msg.role }}
            </el-tag>
            <span class="msg-time">{{ formatDate(msg.created_at) }}</span>
          </div>
          <div class="msg-content">{{ msg.content }}</div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api, { fetchAllUsers, fetchAdminSessions } from '@/api/index'

const loading = ref(false)
const users = ref([])
const sessions = ref([])
const selectedUserId = ref(null)
const keyword = ref('')

const drawerVisible = ref(false)
const drawerTitle = ref('会话消息')
const messagesLoading = ref(false)
const messages = ref([])

const getUsername = (userId) => {
  const user = users.value.find((u) => u.id === userId)
  return user?.username || '未知用户'
}

const filteredSessions = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  return sessions.value.filter((s) => {
    if (selectedUserId.value && s.user_id !== selectedUserId.value) return false
    if (!q) return true
    const title = (s.title || '').toLowerCase()
    const id = (s.id || '').toLowerCase()
    return title.includes(q) || id.includes(q)
  })
})

const formatDate = (value) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', {
    hour12: false,
  })
}

const loadData = async () => {
  loading.value = true
  try {
    const [usersRes, sessionsRes] = await Promise.all([
      fetchAllUsers(),
      fetchAdminSessions(),
    ])
    users.value = usersRes.data || []
    sessions.value = sessionsRes.data || []
  } catch (err) {
    const msg = err?.response?.data?.detail || '加载会话数据失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

const viewMessages = async (session) => {
  drawerTitle.value = `会话消息 - ${session.title || session.id}`
  drawerVisible.value = true
  messagesLoading.value = true
  messages.value = []
  try {
    const res = await api.get(`/agent/sessions/${session.id}/messages`)
    messages.value = res.data || []
  } catch (err) {
    const msg = err?.response?.data?.detail || '加载会话消息失败'
    ElMessage.error(msg)
  } finally {
    messagesLoading.value = false
  }
}

const deleteSession = async (session) => {
  try {
    await ElMessageBox.confirm(
      `确认删除会话「${session.title || session.id}」吗？`,
      '删除确认',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    await api.delete(`/agent/sessions/${session.id}`)
    ElMessage.success('会话已删除')
    await loadData()
  } catch (err) {
    if (err === 'cancel') return
    const msg = err?.response?.data?.detail || '删除会话失败'
    ElMessage.error(msg)
  }
}

onMounted(() => {
  loadData()
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

.message-list {
  height: 100%;
  overflow-y: auto;
  padding-right: 8px;
}

.msg-item {
  border: 1px solid #e2e8f0;
  border-radius: 22px;
  padding: 14px 16px;
  margin-bottom: 12px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.84));
  box-shadow: 0 14px 28px rgba(24, 54, 66, 0.06);
}

.msg-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.msg-time {
  font-size: 12px;
  color: #94a3b8;
}

.msg-content {
  white-space: pre-wrap;
  line-height: 1.6;
  color: #334155;
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

:deep(.el-button.is-link) {
  min-height: auto;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(24, 54, 66, 0.06);
}

:deep(.el-button.is-link + .el-button.is-link) {
  margin-left: 8px;
}

:deep(.el-input__wrapper),
:deep(.el-select__wrapper) {
  border-radius: 16px;
  min-height: 44px;
  box-shadow: 0 0 0 1px rgba(24, 54, 66, 0.08) inset;
  background: rgba(255, 255, 255, 0.86);
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
