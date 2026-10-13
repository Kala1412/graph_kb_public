<template>
  <div class="admin-page">
    <div class="page-header">
      <div>
        <h2>个人病症管理</h2>
        <p>管理员可切换任意用户，统一维护其长期病症记录、来源与更新时间。</p>
      </div>
      <div class="header-actions">
        <el-button @click="reloadCurrentUserRecords" :loading="recordsLoading">刷新</el-button>
        <el-button type="primary" :disabled="!selectedUserId" @click="openCreateDialog">新增病症记录</el-button>
      </div>
    </div>

    <div class="hero-grid">
      <el-card shadow="never" class="hero-card main-hero">
        <div class="hero-copy">
          <span class="eyebrow">Medical Profile Admin</span>
          <h3>{{ selectedUserName }}</h3>
          <p>{{ selectedUserHint }}</p>
          <div class="hero-inline-stats">
            <div class="hero-inline-item">
              <span>当前用户 ID</span>
              <strong>{{ selectedUserId || '--' }}</strong>
            </div>
            <div class="hero-inline-item">
              <span>记录总数</span>
              <strong>{{ totalRecords }}</strong>
            </div>
            <div class="hero-inline-item">
              <span>最近更新</span>
              <strong>{{ latestUpdatedText }}</strong>
            </div>
          </div>
        </div>
        <div class="hero-meta">
          <div class="hero-badge">
            <span>手动录入</span>
            <strong>{{ sourceCountMap.manual || 0 }}</strong>
          </div>
          <div class="hero-badge">
            <span>对话提取</span>
            <strong>{{ sourceCountMap.chat_import || 0 }}</strong>
          </div>
        </div>
      </el-card>

      <el-card shadow="never" class="hero-card stat-card">
        <span class="stat-label">症状记录</span>
        <strong>{{ typeCountMap.symptom || 0 }}</strong>
        <p>适合维护持续症状、主诉和身体不适。</p>
        <div class="stat-foot">
          <span>占比</span>
          <b>{{ getTypePercent('symptom') }}</b>
        </div>
      </el-card>

      <el-card shadow="never" class="hero-card stat-card">
        <span class="stat-label">诊断与病史</span>
        <strong>{{ (typeCountMap.diagnosis || 0) + (typeCountMap.history || 0) }}</strong>
        <p>用于沉淀明确诊断、既往病史和长期背景信息。</p>
        <div class="stat-foot">
          <span>重点沉淀</span>
          <b>{{ diagnosisHistorySummary }}</b>
        </div>
      </el-card>
    </div>

    <el-card shadow="never">
      <div class="toolbar">
        <el-select
          v-model="selectedUserId"
          filterable
          clearable
          placeholder="选择要管理的用户"
          style="width: 260px"
          @change="handleUserChange"
        >
          <el-option
            v-for="user in users"
            :key="user.id"
            :label="`${user.username} (${user.email || '无邮箱'})`"
            :value="user.id"
          />
        </el-select>

        <el-select v-model="filters.recordType" clearable placeholder="病症分类" style="width: 170px">
          <el-option v-for="item in medicalTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>

        <el-select v-model="filters.source" clearable placeholder="记录来源" style="width: 170px">
          <el-option v-for="item in medicalSourceOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>

        <el-input
          v-model="filters.keyword"
          clearable
          placeholder="搜索病症内容"
          style="width: 260px"
        />

        <el-button @click="resetFilters">重置筛选</el-button>
      </div>

      <div class="type-chips">
        <button
          v-for="item in medicalTypeCards"
          :key="item.value"
          type="button"
          class="type-chip"
          :class="{ active: filters.recordType === item.value }"
          @click="toggleTypeFilter(item.value)"
        >
          <span class="chip-dot" :style="{ background: item.color }"></span>
          <span>{{ item.label }}</span>
          <strong>{{ item.count }}</strong>
        </button>
      </div>

      <div v-if="!selectedUserId" class="empty-state">
        <span class="eyebrow">Select User</span>
        <h4>先选择一个用户再管理病症档案</h4>
        <p>当前后端按用户维度提供病症档案管理能力，管理员可在这里快速切换任意用户并维护其记录。</p>
      </div>

      <template v-else>
        <el-table :data="pagedRecords" v-loading="recordsLoading" border>
          <el-table-column prop="id" label="记录ID" width="90" />
          <el-table-column label="所属用户" min-width="180">
            <template #default="{ row }">
              <div class="user-cell">
                <strong>{{ getUserName(row.user_id) }}</strong>
                <span>ID: {{ row.user_id }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="分类" width="140">
            <template #default="{ row }">
              <span class="record-type-pill" :style="getTypePillStyle(row.record_type)">
                {{ getTypeLabel(row.record_type) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="来源" width="130">
            <template #default="{ row }">
              <el-tag effect="plain">{{ getSourceLabel(row.source) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="content" label="病症内容" min-width="320" show-overflow-tooltip />
          <el-table-column label="更新时间" min-width="180">
            <template #default="{ row }">
              {{ formatDate(row.updated_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEditDialog(row)">编辑</el-button>
              <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="!recordsLoading && !filteredRecords.length" class="empty-state compact">
          <span class="eyebrow">No Records</span>
          <h4>该用户还没有病症档案</h4>
          <p>可以手动新增症状、诊断、用药或既往病史，方便后续问答和长期画像维护。</p>
        </div>

        <div class="pager">
          <el-pagination
            v-model:current-page="page"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            :total="filteredRecords.length"
          />
        </div>
      </template>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '新增病症记录' : '编辑病症记录'"
      width="620px"
      @closed="resetDialog"
    >
      <el-form ref="medicalFormRef" :model="medicalForm" :rules="medicalRules" label-position="top">
        <div class="form-grid">
          <el-form-item label="所属用户" prop="user_id">
            <el-select v-model="medicalForm.user_id" filterable placeholder="请选择用户">
              <el-option
                v-for="user in users"
                :key="user.id"
                :label="`${user.username} (${user.email || '无邮箱'})`"
                :value="user.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="病症分类" prop="record_type">
            <el-select v-model="medicalForm.record_type">
              <el-option v-for="item in medicalTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
        </div>

        <div class="form-grid">
          <el-form-item label="来源" prop="source">
            <el-select v-model="medicalForm.source">
              <el-option v-for="item in medicalSourceOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>

          <el-form-item label="用户预览">
            <div class="user-preview">
              <strong>{{ getUserName(medicalForm.user_id) }}</strong>
              <span>{{ getUserEmail(medicalForm.user_id) }}</span>
            </div>
          </el-form-item>
        </div>

        <el-form-item label="病症内容" prop="content">
          <el-input
            v-model="medicalForm.content"
            type="textarea"
            :rows="5"
            maxlength="500"
            show-word-limit
            placeholder="请输入该用户的症状、诊断、用药、过敏史或其它长期医疗信息"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitRecord">
          {{ dialogMode === 'create' ? '保存记录' : '更新记录' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="deleteDialogVisible"
      width="520px"
      destroy-on-close
      class="delete-dialog"
    >
      <div class="delete-dialog-body">
        <div class="delete-icon">!</div>
        <div class="delete-copy">
          <span class="eyebrow danger-eyebrow">Delete Record</span>
          <h4>删除这条病症信息？</h4>
          <p>删除后将无法恢复，这条长期病症档案会从当前用户资料中移除。</p>
          <div
            v-if="deletingRecord"
            class="delete-record-preview"
            :style="{ '--preview-accent': typeMetaMap[deletingRecord.record_type]?.color || '#0f766e' }"
          >
            <div class="delete-record-meta">
              <span class="record-type-pill preview-chip" :style="getTypePillStyle(deletingRecord.record_type)">
                {{ getTypeLabel(deletingRecord.record_type) }}
              </span>
              <span>{{ getSourceLabel(deletingRecord.source) }}</span>
              <span>{{ getUserName(deletingRecord.user_id) }}</span>
            </div>
            <div class="delete-record-text">{{ deletingRecord.content }}</div>
          </div>
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button class="ghost-btn" @click="closeDeleteDialog">取消</el-button>
          <el-button class="danger-btn" :loading="deleting" @click="confirmDelete">删除</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  createMedicalProfileRecord,
  deleteMedicalProfileRecord,
  fetchAllUsers,
  listMedicalProfileRecords,
  updateMedicalProfileRecord,
} from '@/api/index'

const medicalFormRef = ref(null)
const usersLoading = ref(false)
const recordsLoading = ref(false)
const saving = ref(false)
const users = ref([])
const records = ref([])
const selectedUserId = ref(null)
const page = ref(1)
const pageSize = ref(10)
const dialogVisible = ref(false)
const dialogMode = ref('create')
const editingRecordId = ref(null)
const deleteDialogVisible = ref(false)
const deleting = ref(false)
const deletingRecord = ref(null)

const filters = reactive({
  recordType: '',
  source: '',
  keyword: '',
})

const medicalForm = reactive({
  user_id: null,
  record_type: 'symptom',
  source: 'manual',
  content: '',
})

const medicalTypeOptions = [
  { label: '症状', value: 'symptom', color: '#d97706' },
  { label: '诊断', value: 'diagnosis', color: '#0f766e' },
  { label: '用药', value: 'medication', color: '#2563eb' },
  { label: '过敏', value: 'allergy', color: '#dc2626' },
  { label: '病史', value: 'history', color: '#7c3aed' },
  { label: '其他', value: 'other', color: '#64748b' },
]

const medicalSourceOptions = [
  { label: '手动录入', value: 'manual' },
  { label: '对话提取', value: 'chat_import' },
  { label: '历史迁移', value: 'migration' },
]

const typeMetaMap = Object.fromEntries(medicalTypeOptions.map((item) => [item.value, item]))
const sourceLabelMap = Object.fromEntries(medicalSourceOptions.map((item) => [item.value, item.label]))

const medicalRules = {
  user_id: [{ required: true, message: '请选择所属用户', trigger: 'change' }],
  record_type: [{ required: true, message: '请选择病症分类', trigger: 'change' }],
  source: [{ required: true, message: '请选择来源', trigger: 'change' }],
  content: [{ required: true, message: '请输入病症内容', trigger: 'blur' }],
}

const filteredRecords = computed(() => {
  const keyword = filters.keyword.trim().toLowerCase()
  return records.value.filter((record) => {
    if (filters.recordType && record.record_type !== filters.recordType) return false
    if (filters.source && record.source !== filters.source) return false
    if (!keyword) return true
    return (record.content || '').toLowerCase().includes(keyword)
  })
})

const pagedRecords = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredRecords.value.slice(start, start + pageSize.value)
})

const totalRecords = computed(() => records.value.length)

const typeCountMap = computed(() =>
  records.value.reduce((acc, item) => {
    acc[item.record_type] = (acc[item.record_type] || 0) + 1
    return acc
  }, {})
)

const sourceCountMap = computed(() =>
  records.value.reduce((acc, item) => {
    acc[item.source] = (acc[item.source] || 0) + 1
    return acc
  }, {})
)

const medicalTypeCards = computed(() =>
  medicalTypeOptions.map((item) => ({
    ...item,
    count: records.value.filter((record) => record.record_type === item.value).length,
  }))
)

const selectedUser = computed(() =>
  users.value.find((item) => item.id === selectedUserId.value) || null
)

const selectedUserName = computed(() => selectedUser.value?.username || '未选择用户')

const selectedUserHint = computed(() => {
  if (!selectedUser.value) return '请先选择一个用户，再进入该用户病症档案的日常维护。'
  return `当前正在管理 ${selectedUser.value.username} 的长期病症信息，可新增、编辑、删除并按分类查看。`
})

const latestUpdatedText = computed(() => {
  if (!records.value.length) return '暂无记录'
  return formatDate(records.value[0]?.updated_at)
})

const diagnosisHistorySummary = computed(() => {
  const diagnosis = typeCountMap.value.diagnosis || 0
  const history = typeCountMap.value.history || 0
  if (!diagnosis && !history) return '暂无'
  return `诊断 ${diagnosis} / 病史 ${history}`
})

const getUserName = (userId) => users.value.find((item) => item.id === userId)?.username || '未知用户'

const getUserEmail = (userId) => users.value.find((item) => item.id === userId)?.email || '暂无邮箱'

const getTypeLabel = (value) => typeMetaMap[value]?.label || value || '-'

const getSourceLabel = (value) => sourceLabelMap[value] || value || '-'

const getTypePillStyle = (value) => {
  const color = typeMetaMap[value]?.color || '#64748b'
  return {
    '--pill-color': color,
    color,
  }
}

const getTypePercent = (type) => {
  const total = totalRecords.value
  if (!total) return '0%'
  const count = typeCountMap.value[type] || 0
  return `${Math.round((count / total) * 100)}%`
}

const formatDate = (value) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', { hour12: false })
}

const loadUsers = async () => {
  usersLoading.value = true
  try {
    const { data } = await fetchAllUsers()
    users.value = Array.isArray(data) ? data : []
    if (!selectedUserId.value && users.value.length) {
      selectedUserId.value = users.value[0].id
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '加载用户列表失败')
  } finally {
    usersLoading.value = false
  }
}

// 如果管理员暂时没有选中用户，就主动清空当前列表，避免界面显示旧数据。
const loadRecords = async () => {
  if (!selectedUserId.value) {
    records.value = []
    return
  }

  recordsLoading.value = true
  try {
    const { data } = await listMedicalProfileRecords({
      user_id: selectedUserId.value,
      skip: 0,
      limit: 500,
    })
    records.value = Array.isArray(data?.items) ? data.items : []
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '加载病症记录失败')
  } finally {
    recordsLoading.value = false
  }
}

const reloadCurrentUserRecords = async () => {
  await loadRecords()
}

// 切换用户时同步重置筛选条件和分页位置，
// 确保管理员看到的是“新用户的第一页完整数据”，而不是上一位用户遗留的视图状态。
const handleUserChange = async () => {
  page.value = 1
  filters.recordType = ''
  filters.source = ''
  filters.keyword = ''
  await loadRecords()
}

const resetDialog = () => {
  medicalForm.user_id = selectedUserId.value || null
  medicalForm.record_type = 'symptom'
  medicalForm.source = 'manual'
  medicalForm.content = ''
  editingRecordId.value = null
  medicalFormRef.value?.clearValidate?.()
}

const openCreateDialog = async () => {
  dialogMode.value = 'create'
  resetDialog()
  medicalForm.user_id = selectedUserId.value || null
  dialogVisible.value = true
  await nextTick()
}

const openEditDialog = async (record) => {
  dialogMode.value = 'edit'
  editingRecordId.value = record.id
  medicalForm.user_id = record.user_id
  medicalForm.record_type = record.record_type || 'symptom'
  medicalForm.source = record.source || 'manual'
  medicalForm.content = record.content || ''
  dialogVisible.value = true
  await nextTick()
}

// 如果编辑后把记录改挂到另一位用户名下，这里会同步切换 selectedUserId，
// 让页面立刻展示该记录的最新归属位置。
const submitRecord = async () => {
  if (!medicalFormRef.value || saving.value) return

  try {
    await medicalFormRef.value.validate()
  } catch {
    return
  }

  saving.value = true
  try {
    const payload = {
      user_id: medicalForm.user_id,
      record_type: medicalForm.record_type,
      source: medicalForm.source,
      content: medicalForm.content.trim(),
    }

    if (dialogMode.value === 'create') {
      await createMedicalProfileRecord(payload)
      ElMessage.success('病症记录已新增')
    } else {
      await updateMedicalProfileRecord(editingRecordId.value, payload)
      ElMessage.success('病症记录已更新')
    }

    dialogVisible.value = false
    if (selectedUserId.value !== medicalForm.user_id) {
      selectedUserId.value = medicalForm.user_id
    }
    await loadRecords()
    resetDialog()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '提交病症记录失败')
  } finally {
    saving.value = false
  }
}

const handleDelete = (record) => {
  deletingRecord.value = record
  deleteDialogVisible.value = true
}

const closeDeleteDialog = (force = false) => {
  if (deleting.value && !force) return
  deleteDialogVisible.value = false
  deletingRecord.value = null
}

const confirmDelete = async () => {
  if (deleting.value || !deletingRecord.value?.id) return
  deleting.value = true
  try {
    await deleteMedicalProfileRecord(deletingRecord.value.id)
    closeDeleteDialog(true)
    await loadRecords()
    ElMessage.success('病症记录已删除')
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '删除病症记录失败')
  } finally {
    deleting.value = false
  }
}

const resetFilters = () => {
  filters.recordType = ''
  filters.source = ''
  filters.keyword = ''
  page.value = 1
}

const toggleTypeFilter = (value) => {
  filters.recordType = filters.recordType === value ? '' : value
}

watch(
  () => filters.keyword,
  () => {
    page.value = 1
  }
)

watch(
  () => [filters.recordType, filters.source],
  () => {
    page.value = 1
  }
)

watch(pageSize, () => {
  page.value = 1
})

watch(filteredRecords, (list) => {
  const maxPage = Math.max(1, Math.ceil(list.length / pageSize.value))
  if (page.value > maxPage) page.value = maxPage
})

onMounted(async () => {
  await loadUsers()
  await loadRecords()
  resetDialog()
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
  gap: 16px;
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
  flex-wrap: wrap;
}

.hero-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) repeat(2, minmax(220px, 0.92fr));
  gap: 16px;
  margin-bottom: 18px;
}

.hero-card {
  min-height: 118px;
}

.main-hero {
  overflow: hidden;
}

.main-hero :deep(.el-card__body) {
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  gap: 16px;
  min-height: 118px;
  background:
    radial-gradient(circle at top right, rgba(255, 255, 255, 0.16), transparent 28%),
    linear-gradient(135deg, #183642, #355566 58%, #4c7580);
  color: #f8fafc;
}

.hero-copy h3 {
  margin: 8px 0 6px;
  font-size: 28px;
  font-family: Georgia, 'Times New Roman', serif;
}

.hero-copy p {
  margin: 0;
  max-width: 520px;
  color: rgba(248, 250, 252, 0.82);
  line-height: 1.72;
  font-size: 13px;
}

.eyebrow {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  background: rgba(255, 255, 255, 0.14);
  color: inherit;
}

.hero-meta {
  display: grid;
  gap: 10px;
  min-width: 150px;
}

.hero-badge {
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.12);
}

.hero-badge span {
  display: block;
  font-size: 12px;
  color: rgba(248, 250, 252, 0.74);
}

.hero-badge strong {
  display: block;
  margin-top: 4px;
  font-size: 22px;
  color: #fffdf8;
}

.hero-inline-stats {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 14px;
}

.hero-inline-item {
  min-width: 110px;
  padding: 10px 12px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.hero-inline-item span {
  display: block;
  font-size: 11px;
  color: rgba(248, 250, 252, 0.72);
}

.hero-inline-item strong {
  display: block;
  margin-top: 4px;
  font-size: 16px;
  color: #fffdf8;
}

.stat-card {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.stat-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 118px;
}

.stat-label {
  font-size: 13px;
  color: var(--admin-subtle);
}

.stat-card strong {
  margin-top: 8px;
  font-size: 24px;
  color: var(--admin-ink);
}

.stat-card p {
  margin: 8px 0 0;
  line-height: 1.65;
  color: var(--admin-subtle);
  font-size: 13px;
}

.stat-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed rgba(24, 54, 66, 0.1);
  font-size: 12px;
  color: var(--admin-subtle);
}

.stat-foot b {
  color: var(--admin-ink);
  font-size: 13px;
}

.toolbar {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 18px;
  padding: 18px;
  border-radius: 22px;
  border: 1px solid var(--admin-line);
  background:
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.72), transparent 42%),
    rgba(242, 238, 230, 0.7);
}

.type-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 18px;
}

.type-chip {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 44px;
  padding: 0 14px;
  border: 1px solid rgba(24, 54, 66, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
  color: var(--admin-ink);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.type-chip strong {
  color: var(--admin-subtle);
}

.type-chip.active {
  border-color: rgba(15, 118, 110, 0.2);
  box-shadow: 0 12px 24px rgba(24, 54, 66, 0.08);
  transform: translateY(-1px);
}

.chip-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
}

.user-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.user-cell strong {
  color: var(--admin-ink);
}

.user-cell span {
  font-size: 12px;
  color: var(--admin-subtle);
}

.record-type-pill {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--pill-color) 12%, white);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--pill-color) 18%, white);
}

.empty-state {
  display: grid;
  gap: 10px;
  place-items: start;
  padding: 28px;
  border-radius: 24px;
  border: 1px dashed rgba(24, 54, 66, 0.14);
  background: rgba(250, 248, 243, 0.86);
}

.empty-state.compact {
  margin-top: 16px;
}

.empty-state h4 {
  margin: 0;
  font-size: 24px;
  color: var(--admin-ink);
  font-family: Georgia, 'Times New Roman', serif;
}

.empty-state p {
  margin: 0;
  max-width: 620px;
  line-height: 1.75;
  color: var(--admin-subtle);
}

.pager {
  margin-top: 18px;
  display: flex;
  justify-content: flex-end;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.user-preview {
  display: grid;
  gap: 4px;
  min-height: 44px;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(250, 248, 243, 0.86);
  border: 1px solid rgba(24, 54, 66, 0.08);
}

.user-preview strong {
  color: var(--admin-ink);
}

.user-preview span {
  color: var(--admin-subtle);
  font-size: 12px;
}

.delete-dialog-body {
  display: flex;
  align-items: flex-start;
  gap: 18px;
  padding: 8px 4px 4px;
}

.delete-icon {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  border-radius: 18px;
  font-size: 24px;
  font-weight: 700;
  color: #b91c1c;
  background: linear-gradient(135deg, rgba(248, 113, 113, 0.18), rgba(251, 191, 36, 0.18));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
}

.delete-copy {
  flex: 1;
}

.danger-eyebrow {
  background: rgba(185, 28, 28, 0.08);
  color: #b91c1c;
}

.delete-copy h4 {
  margin: 2px 0 10px;
  font-size: 28px;
  color: var(--admin-ink);
  font-family: Georgia, 'Times New Roman', serif;
}

.delete-copy p {
  margin: 0;
  color: var(--admin-subtle);
  line-height: 1.8;
  word-break: break-word;
}

.delete-record-preview {
  margin-top: 16px;
  padding: 16px;
  border-radius: 20px;
  border: 1px solid color-mix(in srgb, var(--preview-accent) 18%, white);
  background: linear-gradient(180deg, color-mix(in srgb, var(--preview-accent) 8%, white), rgba(255, 255, 255, 0.92));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.78);
}

.delete-record-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  color: var(--admin-subtle);
  font-size: 12px;
}

.preview-chip {
  color: var(--preview-accent);
}

.delete-record-text {
  margin-top: 12px;
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.82);
  line-height: 1.8;
  word-break: break-word;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
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
:deep(.el-select__wrapper),
:deep(.el-textarea__inner) {
  border-radius: 16px;
  box-shadow: 0 0 0 1px rgba(24, 54, 66, 0.08) inset;
  background: rgba(255, 255, 255, 0.86);
}

:deep(.el-input__wrapper),
:deep(.el-select__wrapper) {
  min-height: 44px;
}

:deep(.el-textarea__inner) {
  padding: 12px 14px;
}

:deep(.el-tag) {
  border-radius: 999px;
  padding-inline: 10px;
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
  padding: 14px 24px 18px;
}

:deep(.el-dialog__footer) {
  padding: 0 24px 24px;
}

:deep(.delete-dialog .el-overlay-dialog) {
  animation: dialog-fade-in 0.28s cubic-bezier(0.2, 0.8, 0.2, 1);
}

:deep(.delete-dialog .el-dialog) {
  border-radius: 28px;
  overflow: hidden;
  background: linear-gradient(180deg, rgba(255, 252, 247, 0.98), rgba(255, 248, 240, 0.98));
  box-shadow: 0 28px 80px rgba(31, 49, 58, 0.2);
  transform-origin: center;
  animation: dialog-pop-in 0.3s cubic-bezier(0.2, 0.8, 0.2, 1);
}

:deep(.delete-dialog .el-dialog__header) {
  display: none;
}

:deep(.delete-dialog .el-dialog__body) {
  padding: 28px 28px 8px;
}

:deep(.delete-dialog .el-dialog__footer) {
  padding: 0 28px 26px;
}

:deep(.ghost-btn.el-button) {
  background: rgba(255, 255, 255, 0.76);
  color: var(--admin-ink);
}

:deep(.danger-btn.el-button) {
  background: linear-gradient(135deg, #b91c1c, #dc2626);
  border-color: transparent;
  color: #fff;
}

@keyframes dialog-fade-in {
  from {
    opacity: 0;
  }

  to {
    opacity: 1;
  }
}

@keyframes dialog-pop-in {
  from {
    opacity: 0;
    transform: translateY(18px) scale(0.96);
    filter: blur(4px);
  }

  to {
    opacity: 1;
    transform: translateY(0) scale(1);
    filter: blur(0);
  }
}

@media (max-width: 1200px) {
  .hero-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .main-hero :deep(.el-card__body) {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
