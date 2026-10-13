<template>
  <div class="kb-admin-detail">
    <div class="page-header">
      <div class="title-wrap">
        <el-button text @click="goBack">← 返回知识库列表</el-button>
        <h2>知识库详情管理</h2>
      </div>
      <el-button :loading="refreshing" @click="refreshAll">刷新</el-button>
    </div>

    <el-row :gutter="12" class="info-cards">
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never" class="mini-card">
          <div class="mini-label">知识库 ID</div>
          <div class="mini-value">{{ kbInfo.id || '-' }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never" class="mini-card">
          <div class="mini-label">文件数量</div>
          <div class="mini-value">{{ kbInfo.file_count || 0 }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never" class="mini-card">
          <div class="mini-label">创建者</div>
          <div class="mini-value">{{ creatorName }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never" class="mini-card">
          <div class="mini-label">创建时间</div>
          <div class="mini-value small">{{ formatDate(kbInfo.created_at) }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="card-header">
          <span>基本信息</span>
        </div>
      </template>
      <el-form :model="form" label-width="90px" class="base-form">
        <el-form-item label="知识库名称">
          <el-input v-model="form.name" placeholder="请输入知识库名称" />
        </el-form-item>
        <el-form-item label="知识库描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="请输入知识库描述"
          />
        </el-form-item>
      </el-form>
      <div class="actions">
        <el-button type="primary" :loading="savingInfo" @click="saveBaseInfo">保存基本信息</el-button>
      </div>
    </el-card>

    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <span>文件列表</span>
            <div class="file-summary">
              <el-tag size="small" effect="plain">总数 {{ fileStats.total }}</el-tag>
              <el-tag size="small" type="success" effect="plain">可用 {{ fileStats.indexed }}</el-tag>
              <el-tag size="small" type="warning" effect="plain">处理中 {{ fileStats.processing }}</el-tag>
              <el-tag size="small" type="danger" effect="plain">异常 {{ fileStats.error }}</el-tag>
            </div>
          </div>
          <div class="header-actions">
            <el-tag type="info" effect="plain">已选 {{ selectedCount }} 项</el-tag>
            <el-button
              type="warning"
              plain
              :disabled="selectedCount === 0"
              :loading="batchRetrying"
              @click="retrySelectedFiles"
            >
              批量重试
            </el-button>
            <el-button
              type="danger"
              plain
              :disabled="selectedCount === 0"
              :loading="batchDeleting"
              @click="deleteSelectedFiles"
            >
              批量删除
            </el-button>
            <el-input
              v-model="keyword"
              placeholder="搜索文件名"
              clearable
              style="width: 220px"
            />
            <el-button type="primary" @click="openUploadDialog()">上传文件</el-button>
          </div>
        </div>
      </template>

      <el-table
        ref="fileTableRef"
        :data="pagedFiles"
        :row-key="row => row.id"
        v-loading="filesLoading"
        border
        @select="handleRowSelect"
        @select-all="handleSelectAll"
      >
        <el-table-column type="selection" width="48" :reserve-selection="true" />
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="filename" label="文件名" min-width="240" show-overflow-tooltip />
        <el-table-column label="大小" width="120">
          <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="170">
          <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="错误信息" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ row.error_message || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="previewMarkdown(row)">预览</el-button>
            <el-button link type="primary" @click="openUploadDialog(row)">覆盖上传</el-button>
            <el-button link type="warning" @click="retryFile(row)">重试</el-button>
            <el-button link type="danger" @click="deleteFile(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="table-pagination">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="filteredFiles.length"
        />
      </div>
    </el-card>

    <el-dialog v-model="uploadVisible" :title="uploadDialogTitle" width="520px" @closed="resetUploadDialog">
      <el-form label-width="100px">
        <el-form-item label="文件">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :file-list="uploadFileList"
            :limit="1"
            :on-change="onFileChange"
            :on-remove="onFileRemove"
          >
            <el-button type="primary">选择文件</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item label="OCR 模式">
          <el-select v-model="ocrMode" style="width: 100%">
            <el-option label="关闭 OCR" value="disable" />
            <el-option label="DeepSeek OCR" value="deepseek_ocr" />
            <el-option label="MinerU OCR" value="mineru" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="uploadFile">上传</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="markdownVisible" width="80%" top="5vh" class="markdown-dialog">
      <template #header>
        <div class="markdown-header">
          <div class="markdown-title">{{ markdownTitle || '文档预览' }}</div>
          <div class="markdown-subtitle" v-if="markdownStatusText">{{ markdownStatusText }}</div>
        </div>
      </template>

      <el-scrollbar height="70vh" class="markdown-scroll">
        <div v-if="markdownLoading" class="markdown-loading">
          <el-skeleton :rows="8" animated />
        </div>
        <div v-else-if="markdownError" class="markdown-error">
          <el-empty :description="markdownError" />
        </div>
        <div v-else-if="markdownContent" class="markdown-body" v-html="markdownHtml"></div>
        <div v-else class="markdown-empty">
          <el-empty description="暂无可预览内容" />
        </div>
      </el-scrollbar>
      <template #footer>
        <el-button @click="markdownVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api/index'
import MarkdownIt from 'markdown-it'
import mk from 'markdown-it-katex'
import 'katex/dist/katex.min.css'

const router = useRouter()
const route = useRoute()
const kbId = computed(() => Number(route.params.kbId || 0))

const refreshing = ref(false)
const filesLoading = ref(false)
const savingInfo = ref(false)
const uploading = ref(false)
const batchRetrying = ref(false)
const batchDeleting = ref(false)

const kbInfo = ref({
  id: null,
  name: '',
  description: '',
  file_count: 0,
  created_at: null,
  creator: null,
})

const form = ref({
  name: '',
  description: '',
})

const files = ref([])
const keyword = ref('')
const page = ref(1)
const pageSize = ref(10)
const selectedFileIds = ref([])
const fileTableRef = ref(null)

const uploadVisible = ref(false)
const uploadFileList = ref([])
const ocrMode = ref('disable')
const uploadRef = ref(null)
const replaceTargetFileId = ref(null)

const markdownVisible = ref(false)
const markdownLoading = ref(false)
const markdownError = ref('')
const markdownContent = ref('')
const markdownTitle = ref('')
const markdownStatusText = ref('')
const markdownBlobUrls = ref([])
const mdParser = new MarkdownIt({
  html: true,
  linkify: true,
  breaks: true,
}).use(mk)
const markdownHtml = computed(() =>
  markdownContent.value ? mdParser.render(markdownContent.value) : ''
)

let pollTimer = null
let pollingBusy = false

const creatorName = computed(() => {
  return kbInfo.value?.creator?.username || kbInfo.value?.owner_name || '-'
})

const filteredFiles = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return files.value
  return files.value.filter((item) => (item.filename || '').toLowerCase().includes(q))
})

const pagedFiles = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredFiles.value.slice(start, start + pageSize.value)
})

const selectedCount = computed(() => selectedFileIds.value.length)

const uploadDialogTitle = computed(() =>
  replaceTargetFileId.value ? `覆盖上传（文件ID: ${replaceTargetFileId.value}）` : '上传文件'
)

const fileStats = computed(() => {
  const total = files.value.length
  let indexed = 0
  let processing = 0
  let error = 0

  files.value.forEach((item) => {
    if (item.status === 'indexed') indexed += 1
    else if (inProgressStates.has(item.status)) processing += 1
    else if ((item.status || '').startsWith('error')) error += 1
  })

  return { total, indexed, processing, error }
})

const formatDate = (value) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', { hour12: false })
}

const formatSize = (size) => {
  if (!size || size <= 0) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(2)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(2)} MB`
  return `${(size / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

const statusText = (status) => {
  const map = {
    uploaded: '已上传',
    parsing: '解析中',
    parsed: '已解析',
    indexing: '索引中',
    indexed: '可用',
    error_parsing: '解析失败',
    error_indexing: '索引失败',
  }
  return map[status] || status || '-'
}

const statusType = (status) => {
  const map = {
    uploaded: 'info',
    parsing: 'warning',
    parsed: 'warning',
    indexing: 'warning',
    indexed: 'success',
    error_parsing: 'danger',
    error_indexing: 'danger',
  }
  return map[status] || 'info'
}

const inProgressStates = new Set(['uploaded', 'parsing', 'parsed', 'indexing'])
const markdownReadyStates = new Set(['parsed', 'indexing', 'indexed'])
const retryableStates = new Set(['error_parsing', 'error_indexing'])

const canPreviewMarkdown = (status) => markdownReadyStates.has(String(status || '').toLowerCase())

const syncPolling = () => {
  const hasInProgress = files.value.some((item) => inProgressStates.has(item.status))
  if (hasInProgress && !pollTimer) {
    pollTimer = setInterval(async () => {
      if (pollingBusy) return
      pollingBusy = true
      try {
        await loadFiles(false)
      } finally {
        pollingBusy = false
      }
    }, 5000)
  }
  if (!hasInProgress && pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const clearPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const loadKbInfo = async () => {
  const { data } = await api.get(`/knowledge/${kbId.value}`)
  kbInfo.value = data || kbInfo.value
  form.value = {
    name: data?.name || '',
    description: data?.description || '',
  }
}

const loadFiles = async (showLoading = true) => {
  if (showLoading) filesLoading.value = true
  try {
    const { data } = await api.get(`/knowledge/${kbId.value}/files`)
    files.value = data || []
    const validIds = new Set(files.value.map((item) => item.id))
    selectedFileIds.value = selectedFileIds.value.filter((id) => validIds.has(id))
    syncPolling()
  } finally {
    if (showLoading) filesLoading.value = false
  }
}

const refreshAll = async () => {
  refreshing.value = true
  try {
    await Promise.all([loadKbInfo(), loadFiles()])
  } catch (err) {
    console.error(err)
    ElMessage.error(err?.response?.data?.detail || '加载详情失败')
  } finally {
    refreshing.value = false
  }
}

const saveBaseInfo = async () => {
  const name = form.value.name?.trim()
  if (!name) {
    ElMessage.warning('知识库名称不能为空')
    return
  }
  savingInfo.value = true
  try {
    await api.put(`/knowledge/update/${kbId.value}`, {
      name,
      description: form.value.description || '',
    })
    ElMessage.success('知识库基本信息已更新')
    await loadKbInfo()
  } catch (err) {
    console.error(err)
    ElMessage.error(err?.response?.data?.detail || '更新失败')
  } finally {
    savingInfo.value = false
  }
}

const openUploadDialog = (file = null) => {
  replaceTargetFileId.value = file?.id || null
  uploadVisible.value = true
}

const resetUploadDialog = () => {
  uploadFileList.value = []
  ocrMode.value = 'disable'
  replaceTargetFileId.value = null
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
}

const onFileChange = (_file, fileList) => {
  uploadFileList.value = fileList
}

const onFileRemove = (_file, fileList) => {
  uploadFileList.value = fileList
}

const uploadFile = async () => {
  if (!uploadFileList.value.length) {
    ElMessage.warning('请先选择文件')
    return
  }
  const raw = uploadFileList.value[0].raw || uploadFileList.value[0]
  const formData = new FormData()
  formData.append('kb_id', String(kbId.value))
  formData.append('file', raw)
  formData.append('enable_ocr', ocrMode.value)
  if (replaceTargetFileId.value) {
    formData.append('file_id', String(replaceTargetFileId.value))
  }

  uploading.value = true
  try {
    await api.post('/knowledge/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    ElMessage.success('上传成功，后台正在处理')
    uploadVisible.value = false
    await refreshAll()
  } catch (err) {
    console.error(err)
    ElMessage.error(err?.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

const deleteFile = async (file) => {
  try {
    await ElMessageBox.confirm(`确认删除文件「${file.filename}」吗？`, '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await api.delete(`/knowledge/files/${file.id}`)
    ElMessage.success('文件已删除')
    await refreshAll()
  } catch (err) {
    if (err === 'cancel') return
    console.error(err)
    ElMessage.error(err?.response?.data?.detail || '删除文件失败')
  }
}

const retryFile = async (file) => {
  try {
    await api.post(`/knowledge/files/${file.id}/retry`)
    ElMessage.success('已触发重试任务')
    await loadFiles()
  } catch (err) {
    console.error(err)
    ElMessage.error(err?.response?.data?.detail || '重试失败')
  }
}

const addSelectedId = (id) => {
  if (!selectedFileIds.value.includes(id)) {
    selectedFileIds.value = [...selectedFileIds.value, id]
  }
}

const removeSelectedId = (id) => {
  selectedFileIds.value = selectedFileIds.value.filter((item) => item !== id)
}

const handleRowSelect = (selection, row) => {
  const selectedSet = new Set(selection.map((item) => item.id))
  if (selectedSet.has(row.id)) addSelectedId(row.id)
  else removeSelectedId(row.id)
}

const handleSelectAll = (selection) => {
  const selectedSet = new Set(selection.map((item) => item.id))
  pagedFiles.value.forEach((row) => {
    if (selectedSet.has(row.id)) addSelectedId(row.id)
    else removeSelectedId(row.id)
  })
}

const retrySelectedFiles = async () => {
  if (selectedCount.value === 0) return
  const selectedRows = files.value.filter((item) => selectedFileIds.value.includes(item.id))
  const candidates = selectedRows.filter((item) => retryableStates.has(String(item.status || '')))
  if (candidates.length === 0) {
    ElMessage.warning('请选择状态为“解析失败/索引失败”的文件进行批量重试')
    return
  }

  batchRetrying.value = true
  try {
    const results = await Promise.allSettled(
      candidates.map((item) => api.post(`/knowledge/files/${item.id}/retry`))
    )
    const success = results.filter((item) => item.status === 'fulfilled').length
    const failed = results.length - success

    if (success > 0) {
      ElMessage.success(`批量重试已触发：成功 ${success}，失败 ${failed}`)
    } else {
      ElMessage.error('批量重试失败，请稍后再试')
    }
    await loadFiles()
  } finally {
    batchRetrying.value = false
  }
}

const deleteSelectedFiles = async () => {
  if (selectedCount.value === 0) return
  const ids = [...selectedFileIds.value]
  try {
    await ElMessageBox.confirm(`确认批量删除已选中的 ${ids.length} 个文件吗？`, '批量删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }

  batchDeleting.value = true
  try {
    const results = await Promise.allSettled(
      ids.map((id) => api.delete(`/knowledge/files/${id}`))
    )
    const success = results.filter((item) => item.status === 'fulfilled').length
    const failed = results.length - success

    selectedFileIds.value = []
    if (fileTableRef.value) {
      fileTableRef.value.clearSelection()
    }

    if (success > 0) {
      ElMessage.success(`批量删除完成：成功 ${success}，失败 ${failed}`)
    } else {
      ElMessage.error('批量删除失败，请稍后再试')
    }
    await refreshAll()
  } finally {
    batchDeleting.value = false
  }
}

const previewMarkdown = async (file) => {
  if (!canPreviewMarkdown(file.status)) {
    ElMessage.warning('该文件尚未生成 Markdown，请稍后再试')
    return
  }

  markdownVisible.value = true
  markdownLoading.value = true
  markdownError.value = ''
  markdownContent.value = ''
  markdownTitle.value = file.filename
  markdownStatusText.value = '正在加载文档内容...'

  try {
    const statusRes = await api.get(`/knowledge/files/${file.id}/status`)
    const markdownUrl = statusRes?.data?.markdown_url
    if (!markdownUrl) {
      markdownError.value = '该文件尚未生成 Markdown，请稍后再试'
      markdownStatusText.value = '暂无 Markdown'
      return
    }

    const { data } = await api.get(`/knowledge/files/${file.id}/markdown`, {
      responseType: 'text',
    })
    const rawText = typeof data === 'string' ? data : ''
    markdownContent.value = await hydrateMarkdownAssets(rawText)
    markdownStatusText.value = '加载完成'
  } catch (err) {
    console.error(err)
    markdownError.value = err?.response?.data?.detail || err?.message || 'Markdown 预览失败'
    markdownStatusText.value = '加载失败'
  } finally {
    markdownLoading.value = false
  }
}

const releaseMarkdownBlobs = () => {
  markdownBlobUrls.value.forEach((url) => {
    try {
      URL.revokeObjectURL(url)
    } catch (err) {
      console.warn('释放 Blob URL 失败:', err)
    }
  })
  markdownBlobUrls.value = []
}

const hydrateMarkdownAssets = async (rawText) => {
  releaseMarkdownBlobs()
  const assetUrlPattern =
    /((?:https?:\/\/[^\s)'"]+)?\/(?:api\/)?knowledge\/files\/\d+\/assets\/[^)\s'"]+)/g
  const matches = rawText.match(assetUrlPattern)
  if (!matches || matches.length === 0) {
    return rawText
  }

  const uniqueUrls = Array.from(new Set(matches))
  let processed = rawText

  const normalizeAssetRequestUrl = (url) => {
    if (url.startsWith('/knowledge/')) return `/api${url}`
    return url
  }

  const tasks = uniqueUrls.map(async (url) => {
    try {
      const requestUrl = normalizeAssetRequestUrl(url)
      const res = await api.get(requestUrl, { responseType: 'blob' })
      const blobUrl = URL.createObjectURL(res.data)
      markdownBlobUrls.value.push(blobUrl)
      return { url, blobUrl }
    } catch (err) {
      console.warn('加载图片资源失败:', url, err)
      return null
    }
  })

  const results = await Promise.all(tasks)
  results.forEach((item) => {
    if (item?.url && item?.blobUrl) {
      processed = processed.split(item.url).join(item.blobUrl)
    }
  })

  return processed
}

watch(markdownVisible, (visible) => {
  if (!visible) {
    releaseMarkdownBlobs()
  }
})

watch(keyword, () => {
  page.value = 1
})

watch(pageSize, () => {
  page.value = 1
})

watch(filteredFiles, (list) => {
  const maxPage = Math.max(1, Math.ceil(list.length / pageSize.value))
  if (page.value > maxPage) page.value = maxPage
})

watch(
  pagedFiles,
  async (rows) => {
    await nextTick()
    if (!fileTableRef.value) return
    fileTableRef.value.clearSelection()
    rows.forEach((row) => {
      if (selectedFileIds.value.includes(row.id)) {
        fileTableRef.value.toggleRowSelection(row, true)
      }
    })
  },
  { deep: true }
)

const goBack = () => {
  router.push('/admin/knowledge')
}

onMounted(async () => {
  if (!kbId.value) {
    ElMessage.error('无效的知识库ID')
    goBack()
    return
  }
  await refreshAll()
})

watch(
  () => route.params.kbId,
  async () => {
    clearPolling()
    selectedFileIds.value = []
    page.value = 1
    await refreshAll()
  }
)

onBeforeUnmount(() => {
  clearPolling()
  releaseMarkdownBlobs()
})
</script>

<style scoped>
.kb-admin-detail {
  --admin-ink: #183642;
  --admin-subtle: #6c7f86;
  --admin-line: rgba(24, 54, 66, 0.1);
  --admin-card: rgba(255, 252, 247, 0.94);
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding-top: 8px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 4px;
}

.title-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.title-wrap h2 {
  margin: 0;
  font-size: 24px;
  color: var(--admin-ink);
}

.info-cards {
  margin-bottom: 0;
}

.mini-card {
  border-radius: 24px;
}

.mini-label {
  color: var(--admin-subtle);
  font-size: 13px;
}

.mini-value {
  margin-top: 8px;
  color: #0f172a;
  font-size: 24px;
  font-weight: 700;
  line-height: 1.1;
}

.mini-value.small {
  font-size: 24px;
  font-weight: 500;
}

.section-card {
  border-radius: 28px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.file-summary {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 14px;
  border-radius: 22px;
  border: 1px solid var(--admin-line);
  background:
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.72), transparent 42%),
    rgba(242, 238, 230, 0.7);
}

.base-form {
  max-width: 760px;
}

.actions {
  margin-top: 12px;
}

.table-pagination {
  margin-top: 18px;
  display: flex;
  justify-content: flex-end;
}

.markdown-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.markdown-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--admin-ink);
}

.markdown-subtitle {
  font-size: 12px;
  color: var(--admin-subtle);
}

.markdown-scroll {
  padding-right: 8px;
}

.markdown-body {
  font-size: 14px;
  line-height: 1.75;
  color: #0f172a;
  padding-right: 10px;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  font-weight: 600;
  color: #0f172a;
  margin: 18px 0 10px;
}

.markdown-body :deep(h1) {
  font-size: 22px;
}

.markdown-body :deep(h2) {
  font-size: 18px;
}

.markdown-body :deep(h3) {
  font-size: 16px;
}

.markdown-body :deep(p) {
  margin: 8px 0;
}

.markdown-body :deep(a) {
  color: #0f766e;
  text-decoration: none;
}

.markdown-body :deep(a:hover) {
  text-decoration: underline;
}

.markdown-body :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 8px;
  font-size: 12px;
}

.markdown-body :deep(pre) {
  background: #0b1020;
  color: #e2e8f0;
  padding: 12px 14px;
  border-radius: 18px;
  overflow: auto;
  margin: 12px 0;
}

.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
}

.markdown-body :deep(blockquote) {
  margin: 12px 0;
  padding: 12px 14px;
  border-left: 4px solid #8db9b3;
  background: #f8fafc;
  border-radius: 16px;
  color: #475569;
}

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: 13px;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #e2e8f0;
  padding: 10px 12px;
  text-align: left;
}

.markdown-body :deep(img) {
  max-width: 100%;
  border-radius: 16px;
}

:deep(.el-card) {
  border-radius: 28px;
  border: 1px solid var(--admin-line);
  background: var(--admin-card);
  box-shadow: 0 18px 40px rgba(24, 54, 66, 0.08);
}

:deep(.el-card__header) {
  padding: 18px 22px;
  border-bottom: 1px solid var(--admin-line);
  background: rgba(255, 255, 255, 0.56);
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

:deep(.el-button--warning.is-plain) {
  background: rgba(245, 158, 11, 0.12);
  border-color: rgba(245, 158, 11, 0.18);
  color: #b45309;
}

:deep(.el-button--danger.is-plain) {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.16);
  color: #b91c1c;
}

:deep(.el-button.is-text),
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

:deep(.el-upload) {
  width: 100%;
}

:deep(.el-upload-list__item) {
  border-radius: 16px;
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

:deep(.markdown-dialog .el-dialog) {
  border-radius: 32px;
}

:deep(.el-tag) {
  border-radius: 999px;
  padding-inline: 10px;
}

@media (max-width: 768px) {
  .page-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .card-header {
    align-items: flex-start;
  }

  .header-actions {
    width: 100%;
  }
}
</style>
