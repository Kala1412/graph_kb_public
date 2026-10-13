<template>
  <div class="admin-page">
    <div class="page-header">
      <div>
        <h2>知识库管理</h2>
        <p>管理员可查看所有知识库并按创建者筛选</p>
      </div>
      <div class="header-actions">
        <el-button @click="loadKbs" :loading="loading">刷新</el-button>
      </div>
    </div>

    <el-card shadow="never">
      <div class="toolbar">
        <el-input
          v-model="keyword"
          placeholder="按知识库名称或创建者搜索"
          clearable
          style="max-width: 360px"
        />
      </div>

      <el-table :data="filteredKbs" v-loading="loading" border>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="名称" min-width="180" />
        <el-table-column prop="description" label="描述" min-width="260" show-overflow-tooltip />
        <el-table-column prop="file_count" label="文件数" width="100" />
        <el-table-column label="创建者" min-width="140">
          <template #default="{ row }">
            {{ getCreatorName(row) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="openDetail(row)">详情</el-button>
            <el-button type="danger" link @click="deleteKb(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api, { fetchKnowledgeList } from '@/api/index'

const router = useRouter()
const loading = ref(false)
const kbs = ref([])
const keyword = ref('')

const getCreatorName = (kb) => kb?.creator?.username || kb?.owner_name || '-'

const filteredKbs = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return kbs.value
  return kbs.value.filter((kb) => {
    const name = (kb.name || '').toLowerCase()
    const owner = getCreatorName(kb).toLowerCase()
    return name.includes(q) || owner.includes(q)
  })
})

const loadKbs = async () => {
  loading.value = true
  try {
    const res = await fetchKnowledgeList()
    kbs.value = res.data || []
  } catch (err) {
    const msg = err?.response?.data?.detail || '加载知识库失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

const openDetail = (kb) => {
  router.push(`/admin/knowledge/${kb.id}`)
}

const deleteKb = async (kb) => {
  try {
    await ElMessageBox.confirm(
      `确认删除知识库「${kb.name}」吗？该操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    await api.delete(`/knowledge/delete/${kb.id}`)
    ElMessage.success('知识库已删除')
    await loadKbs()
  } catch (err) {
    if (err === 'cancel') return
    const msg = err?.response?.data?.detail || '删除失败'
    ElMessage.error(msg)
  }
}

onMounted(() => {
  loadKbs()
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

:deep(.el-input__wrapper) {
  border-radius: 16px;
  min-height: 44px;
  box-shadow: 0 0 0 1px rgba(24, 54, 66, 0.08) inset;
  background: rgba(255, 255, 255, 0.86);
}
</style>
