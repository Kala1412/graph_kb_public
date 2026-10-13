<template>
  <div class="admin-page">
    <div class="page-header">
      <div>
        <h2>用户管理</h2>
        <p>管理员可查看与编辑全部用户信息</p>
      </div>
      <div class="header-actions">
        <el-button @click="loadUsers" :loading="loading">刷新</el-button>
      </div>
    </div>

    <el-card shadow="never">
      <div class="toolbar">
        <el-input
          v-model="keyword"
          placeholder="按用户名或邮箱搜索"
          clearable
          style="max-width: 320px"
        />
      </div>

      <el-table :data="pagedUsers" v-loading="loading" border>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" min-width="160" />
        <el-table-column prop="email" label="邮箱" min-width="220" />
        <el-table-column label="角色" width="120">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'info'">
              {{ row.role }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'danger'">
              {{ row.status === 'active' ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="启用/禁用" width="150">
          <template #default="{ row }">
            <el-switch
              :model-value="row.status === 'active'"
              :disabled="savingId === row.id || row.id === currentUserId"
              active-text="启用"
              inactive-text="禁用"
              @change="(val) => toggleUserStatus(row, val)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="openEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          :total="filteredUsers.length"
        />
      </div>
    </el-card>

    <el-dialog v-model="editVisible" title="编辑用户" width="520px">
      <el-form :model="editForm" label-width="90px">
        <el-form-item label="用户名">
          <el-input v-model="editForm.username" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="editForm.email" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="editForm.role" style="width: 100%">
            <el-option label="用户" value="user" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="重置密码">
          <el-input
            v-model="editForm.password"
            show-password
            placeholder="留空表示不修改"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveUser">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api, { fetchAllUsers, getMyProfile } from '@/api/index'

const loading = ref(false)
const saving = ref(false)
const savingId = ref(null)
const users = ref([])
const keyword = ref('')
const page = ref(1)
const pageSize = ref(10)
const currentUserId = ref(null)

const editVisible = ref(false)
const editForm = ref({
  id: null,
  username: '',
  email: '',
  role: 'user',
  password: '',
})

const filteredUsers = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return users.value
  return users.value.filter((u) => {
    const username = (u.username || '').toLowerCase()
    const email = (u.email || '').toLowerCase()
    return username.includes(q) || email.includes(q)
  })
})

const pagedUsers = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredUsers.value.slice(start, start + pageSize.value)
})

const loadUsers = async () => {
  loading.value = true
  try {
    const res = await fetchAllUsers()
    users.value = res.data || []
  } catch (err) {
    const msg = err?.response?.data?.detail || '加载用户失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

const loadCurrentUser = async () => {
  try {
    const res = await getMyProfile()
    currentUserId.value = res?.data?.id || null
  } catch {
    currentUserId.value = null
  }
}

const openEdit = (row) => {
  editForm.value = {
    id: row.id,
    username: row.username || '',
    email: row.email || '',
    role: row.role || 'user',
    password: '',
  }
  editVisible.value = true
}

const toggleUserStatus = async (row, enabled) => {
  const nextStatus = enabled ? 'active' : 'disabled'
  if (row.status === nextStatus) return

  if (row.id === currentUserId.value && nextStatus === 'disabled') {
    ElMessage.warning('不能禁用当前登录账号')
    return
  }

  if (nextStatus === 'disabled') {
    try {
      await ElMessageBox.confirm(
        `确认禁用用户「${row.username}」吗？禁用后该用户将无法登录。`,
        '禁用确认',
        {
          confirmButtonText: '禁用',
          cancelButtonText: '取消',
          type: 'warning',
        }
      )
    } catch {
      return
    }
  }

  const previousStatus = row.status
  row.status = nextStatus
  savingId.value = row.id
  try {
    await api.put('/users/', {
      id: row.id,
      status: nextStatus,
    })
    ElMessage.success(nextStatus === 'active' ? '用户已启用' : '用户已禁用')
  } catch (err) {
    row.status = previousStatus
    const msg = err?.response?.data?.detail || '更新状态失败'
    ElMessage.error(msg)
  } finally {
    savingId.value = null
  }
}

const saveUser = async () => {
  if (!editForm.value.id) return
  saving.value = true
  try {
    const payload = {
      id: editForm.value.id,
      username: editForm.value.username?.trim() || null,
      email: editForm.value.email?.trim() || null,
      role: editForm.value.role || 'user',
    }
    if (editForm.value.password?.trim()) {
      payload.password = editForm.value.password.trim()
    }
    await api.put('/users/', payload)
    ElMessage.success('用户信息已更新')
    editVisible.value = false
    await loadUsers()
  } catch (err) {
    const msg = err?.response?.data?.detail || '保存失败'
    ElMessage.error(msg)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadUsers()
  loadCurrentUser()
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

:deep(.el-pagination button),
:deep(.el-pagination .number) {
  border-radius: 12px;
}

:deep(.el-dialog) {
  border-radius: 28px;
  overflow: hidden;
  background: rgba(255, 252, 247, 0.98);
}

:deep(.el-dialog__header) {
  margin-right: 0;
  padding: 22px 24px 12px;
}

:deep(.el-dialog__body) {
  padding: 12px 24px 18px;
}

:deep(.el-dialog__footer) {
  padding: 0 24px 24px;
}
</style>
