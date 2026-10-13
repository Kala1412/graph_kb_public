<template>
  <div class="kb-detail">
    <div class="detail-breadcrumb">
      <el-button text @click="goBack" :icon="ArrowLeft">返回</el-button>
      <span class="breadcrumb-separator">/</span>
      <span class="breadcrumb-text">{{ kbInfo.name }}</span>
      <span v-if="kbInfo.id" class="kb-id">ID: {{ kbInfo.id }}</span>
    </div>
    <el-row :gutter="20" class="detail-content">
      <el-col :xs="24" :md="12">
        <el-card class="file-list-card">
          <template #header>
            <div class="card-header">
              <span class="title">📄 文件列表</span>
              <el-button type="primary" size="small" @click="showUploadDialog"
                >+ 添加文件</el-button
              >
            </div>
          </template>

          <el-table
            :data="files"
            stripe
            style="width: 100%"
            :default-sort="{ prop: 'created_at', order: 'descending' }"
            v-loading="filesLoading"
            element-loading-text="加载中..."
          >
            <el-table-column prop="filename" label="文件名" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">
                <el-tooltip
                  v-if="canPreviewMarkdown(row.status)"
                  content="点击查看 Markdown 内容"
                  placement="top"
                >
                  <el-link type="primary" :underline="false" @click="openMarkdownPreview(row)">
                    {{ row.filename }}
                  </el-link>
                </el-tooltip>
                <span v-else class="file-name-disabled">{{ row.filename }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="file_size" label="大小" width="80">
              <template #default="{ row }">
                {{ formatBytes(row.file_size) }}
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" effect="light">
                  {{ formatStatus(row.status) }}
                </el-tag>
              </template>
            </el-table-column>

            <el-table-column label="处理状态" min-width="360">
              <template #default="{ row }">
                <FileStatusTracker :status="row.status" :error-message="row.error_message" />
              </template>
            </el-table-column>

            <el-table-column prop="created_at" label="上传时间" width="160">
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="row.status === 'ERROR_PARSING' || row.status === 'ERROR_INDEXING'"
                  text
                  type="primary"
                  size="small"
                  @click="retryFile(row)"
                >
                  重试
                </el-button>
                <el-button text type="danger" size="small" @click="deleteFile(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-empty
            v-if="files.length === 0 && !filesLoading"
            description="暂无文件，请上传"
          ></el-empty>
        </el-card>
        <el-card class="info-card m-t-20" shadow="hover">
          <template #header>
            <span class="title">📚 知识库信息</span>
            <el-button type="primary" link :icon="Edit" @click="showEditKbDialog">编辑</el-button>
          </template>
          <div class="info-item">
            <span class="label">名称:</span>
            <span class="value">{{ kbInfo.name }}</span>
          </div>
          <div class="info-item" v-if="kbInfo.description">
            <span class="label">描述:</span>
            <span class="value">{{ kbInfo.description }}</span>
          </div>
          <div class="info-item">
            <span class="label">文件数:</span>
            <span class="value">{{ files.length }}</span>
          </div>
          <div class="info-item">
            <span class="label">创建时间:</span>
            <span class="value">{{ formatDate(kbInfo.created_at) }}</span>
          </div>
        </el-card>

        <el-card class="search-card m-t-20" shadow="hover">
          <template #header>
            <span class="title">🔍 快速搜索</span>
          </template>

          <div class="search-input-section">
            <el-input
              v-model="searchQuery"
              placeholder="输入关键词搜索知识库内容..."
              clearable
              type="textarea"
              :rows="2"
              @keyup.enter="performSearch"
              :disabled="isSearching"
            />
            <div class="search-actions">
              <el-button-group>
                <el-button
                  type="primary"
                  @click="performSearch"
                  :icon="Search"
                  :loading="isSearching"
                  :disabled="!searchQuery.trim()"
                >
                  {{ isSearching ? '搜索中...' : '搜索' }}
                </el-button>
                <el-button v-if="isSearching" @click="cancelSearch" type="danger">取消</el-button>
              </el-button-group>
            </div>

            <div class="search-options">
              <div class="option-group">
                <span class="option-label">检索模式</span>
                <el-radio-group v-model="searchMode" size="small" :disabled="isSearching">
                  
                  <el-radio-button value="hybrid">
                    <el-tooltip content="结合局部和全局图谱推理" placement="top">
                      <span>🔄 混合推理</span>
                    </el-tooltip>
                  </el-radio-button>
                  <el-radio-button value="naive">
                    <el-tooltip content="仅使用 Milvus 向量相似度搜索" placement="top">
                      <span>📐 向量检索</span>
                    </el-tooltip>
                  </el-radio-button>
                  <el-radio-button value="local">
                    <el-tooltip content="基于实体的局部图谱推理" placement="top">
                      <span>📍 局部图谱</span>
                    </el-tooltip>
                  </el-radio-button>
                  <el-radio-button value="global">
                    <el-tooltip content="基于全局知识的图谱推理" placement="top">
                      <span>🌐 全局图谱</span>
                    </el-tooltip>
                  </el-radio-button>
                </el-radio-group>
              </div>

              <div class="option-group">
                <span class="option-label">结果数量</span>
                <el-radio-group v-model="searchTopK" size="small" :disabled="isSearching">
                  <el-radio-button :label="3">
                    <el-tooltip content="返回最相关的 3 条结果，精准快速" placement="top">
                      <span>精准 (3)</span>
                    </el-tooltip>
                  </el-radio-button>
                  <el-radio-button :label="5">
                    <el-tooltip content="返回 5 条结果，平衡精准与覆盖" placement="top">
                      <span>标准 (5)</span>
                    </el-tooltip>
                  </el-radio-button>
                  <el-radio-button :label="10">
                    <el-tooltip content="返回 10 条结果，覆盖更全面" placement="top">
                      <span>广泛 (10)</span>
                    </el-tooltip>
                  </el-radio-button>
                </el-radio-group>
              </div>

              <div class="option-group">
                <span class="option-label">重排</span>
                <el-switch
                  v-model="searchRerankEnabled"
                  :disabled="isSearching || !isSearchRerankEligible"
                />
                <span class="option-hint">仅 naive/local/hybrid</span>
              </div>
            </div>
            <div class="option-group">
              <span class="option-label">仅上下文</span>
              <el-switch
                v-model="searchOnlyContext"
                active-text="仅上下文"
                inactive-text="生成回答"
              />
              <el-tooltip
                content="开启后仅返回检索到的上下文，不调用 LLM；关闭后由 LLM 生成回答"
                placement="top"
              >
                <el-icon class="m-l-4"><QuestionFilled /></el-icon>
              </el-tooltip>
            </div>

            <div v-if="searchPerformed" class="search-panel">
              <div v-if="!searchOnlyContext && searchAnswer" class="answer-section">
                <div class="section-title">🤖 AI 助手回答：</div>
                <div class="answer-content">{{ searchAnswer }}</div>
              </div>

              <el-tabs v-else-if="searchOnlyContext" v-model="activeResultTab" class="context-tabs">
                <el-tab-pane
                  :label="'文本切片 (' + searchResults.chunks.length + ')'"
                  name="chunks"
                >
                  <div class="chunks-container">
                    <el-card
                      v-for="(item, idx) in searchResults.chunks"
                      :key="idx"
                      class="chunk-card"
                    >
                      <div class="chunk-index">#{{ idx + 1 }}</div>
                      <div class="chunk-text">{{ item.content }}</div>
                    </el-card>
                  </div>
                </el-tab-pane>

                <el-tab-pane
                  :label="'关联实体 (' + searchResults.entities.length + ')'"
                  name="entities"
                >
                  <el-table :data="searchResults.entities" border stripe size="small">
                    <el-table-column prop="entity" label="实体" width="150" />
                    <el-table-column prop="type" label="类型" width="120" />
                    <el-table-column prop="description" label="描述" />
                  </el-table>
                </el-tab-pane>

                <el-tab-pane
                  :label="'关联关系 (' + searchResults.relations.length + ')'"
                  name="relations"
                >
                  <el-table :data="searchResults.relations" border stripe size="small">
                    <el-table-column prop="entity1" label="主体" width="120" />
                    <el-table-column prop="entity2" label="客体" width="120" />
                    <el-table-column prop="description" label="关系关系" />
                  </el-table>
                </el-tab-pane>
              </el-tabs>
            </div>
          </div>

          <div v-if="isSearching || searchResultCount > 0" class="search-panel">
            <div v-if="isSearching" class="search-progress">
              <div class="progress-header">
                <span class="progress-message">{{ searchStatusText }}</span>
                <span class="progress-percent">{{ Math.floor(searchProgress) }}%</span>
              </div>
              <el-progress
                :percentage="searchProgress"
                :color="getProgressColor(searchProgress)"
                :show-text="false"
              />
            </div>

            <div v-if="!isSearching && searchPerformed" class="search-summary">
              <span v-if="showResultSummary" class="summary-success">
                ✅ 找到 {{ searchResultCount }} 条相关结果
              </span>
              <span v-else-if="showEmptyState" class="summary-empty"> 未找到相关结果 </span>
            </div>

            <div v-if="searchListResults.length > 0" class="search-results-stream">
              <div
                class="result-item"
                v-for="(item, idx) in searchListResults"
                :key="idx"
                :class="{ 'fade-in': true }"
              >
                <div class="result-header">
                  <div class="result-index">{{ idx + 1 }}</div>
                  <div class="result-title-section">
                    <div class="result-title">{{ item.title }}</div>
                    <div class="result-source-tag">
                      📄 {{ item.source ? item.source.substring(0, 30) : '无源文件' }}
                    </div>
                  </div>
                  <el-tag
                    v-if="item.score"
                    :type="getScoreType(item.score)"
                    size="small"
                    class="result-score"
                  >
                    {{ item.score }}%
                  </el-tag>
                </div>

                <div class="result-content">
                  {{
                    item.content.length > 200
                      ? item.content.substring(0, 200) + '...'
                      : item.content
                  }}
                </div>

                <div class="result-footer">
                  <el-button
                    text
                    type="primary"
                    size="small"
                    @click="copyToClipboard(item.content)"
                  >
                    复制
                  </el-button>
                  <el-button v-if="item.chunk_id" text type="primary" size="small">
                    ID: {{ item.chunk_id }}
                  </el-button>
                </div>
              </div>
            </div>

            <el-empty v-if="showEmptyState" description="搜索无结果，请尝试其他关键词" />
          </div>

          <div v-if="searchResultCount === 0 && !searchPerformed" class="search-tips">
            <el-alert title="💡 搜索提示" type="info" :closable="false" class="search-tip-item">
              <ul>
                <li>支持多模式检索：向量检索快速精准，图谱检索深度推理</li>
                <li>查询超时时间：30秒内必返回结果</li>
                <li>⏱️ 首次大规模检索可能需要10-30秒，请耐心等待</li>
              </ul>
            </el-alert>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="12">
        <el-card class="graph-card">
        <template #header>
          <div class="card-header">
            <span>实体关系知识图谱</span>
            <el-button link type="primary" @click="loadGraph">刷新图谱</el-button>
          </div>
        </template>
        <div class="graph-viewport">
          <GraphCanvas :data="graphData" v-show="graphData.nodes.length > 0" />
          <el-empty v-if="graphData.nodes.length === 0" description="暂无图谱数据，请先上传并索引文档" />
        </div>
      </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="uploadDialogVisible" title="上传文件" width="500px" center>
      <el-form @submit.prevent="uploadFile">
        <el-form-item label="选择文件">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :file-list="uploadFileList"
            @change="handleFileSelect"
            accept=".pdf,.txt,.docx,.doc,.xlsx,.xls,.pptx,.ppt"
          >
            <el-button type="primary">选择文件</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item label="启用OCR（PDF）">
          <el-select v-model="enableOCR" placeholder="请选择解析模式" style="width: 100%">
            <el-option label="标准解析 (Docling)" value="disable" />
            <el-option label="DeepSeek OCR (适合医疗扫描件)" value="deepseek_ocr" />
            <el-option label="MinerU (适合复杂公式表格)" value="mineru" />
          </el-select>
          <span class="tips">PDF 图片识别需要额外时间</span>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="uploadFile" :loading="uploadLoading">上传</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editKbDialogVisible" title="修改知识库信息" width="500px">
      <el-form :model="editKbForm" label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="editKbForm.name" placeholder="请输入知识库名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="editKbForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入描述信息"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editKbDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleUpdateKb" :loading="updateKbLoading"
          >保存修改</el-button
        >
      </template>
    </el-dialog>

    <el-dialog v-model="markdownDialogVisible" width="80%" top="5vh" class="markdown-dialog">
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
        <el-button @click="markdownDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Search, Share, DataAnalysis, Edit } from '@element-plus/icons-vue'
import api, { getKnowledgeGraph } from '@/api/index'
import FileStatusTracker from '@/components/FileStatusTracker.vue'
import GraphCanvas from '@/components/GraphCanvas.vue' // 引入组件
import MarkdownIt from 'markdown-it'
import mk from 'markdown-it-katex'
import 'katex/dist/katex.min.css'

const router = useRouter()
const route = useRoute()
const kbId = parseInt(route.params.kbId)

const kbInfo = ref({ id: kbId, name: '', description: '' })
const files = ref([])
const filesLoading = ref(false)
const uploadDialogVisible = ref(false)
const uploadLoading = ref(false)
const uploadFileList = ref([])
const enableOCR = ref('disable')
const searchQuery = ref('')
const searchMode = ref('hybrid')
const searchTopK = ref(5) // 新增 top_k 参数，默认 5
const searchRerankEnabled = ref(true)
const isSearchRerankEligible = computed(() => ['naive', 'local', 'hybrid'].includes(searchMode.value))
const effectiveSearchRerank = computed(() =>
  isSearchRerankEligible.value ? searchRerankEnabled.value : false
)
const searchOnlyContext = ref(false)
const searchAnswer = ref('') // 存储 AI 回答
const searchResults = ref({ entities: [], relations: [], chunks: [] })
const ENTITY_TYPE_LABELS = {
  Disease: '??',
  Symptom: '??',
  Drug: '??',
  Ingredient: '??',
  Indication: '???',
  Contraindication: '???',
  Interaction: '????',
  Dosage: '??',
  SideEffect: '????',
  Test: '??',
  Treatment: '??',
  Procedure: '??/??',
  Department: '??',
  Population: '??',
  Pathogen: '???',
  Biomarker: '??',
  Guideline: '??',
  Device: '??',
  Document: '??',
  Organization: '??',
  Person: '??',
  Location: '??',
  Time: '??',
  Data: '??',
  Other: '??',
}

const RELATION_LABELS = {
  TREATS: '??',
  HAS_SYMPTOM: '??',
  HAS_SIDE_EFFECT: '????',
  HAS_INGREDIENT: '????',
  INDICATED_FOR: '???',
  CONTRAINDICATED_FOR: '??',
  INTERACTS_WITH: '????',
  REQUIRES_TEST: '????',
  HAS_DOSAGE: '??',
  RELATED_TO: '??',
  PART_OF: '??',
  CAUSES: '??',
}

const getEntityTypeLabel = (value) => ENTITY_TYPE_LABELS[value] || value || ''
const getRelationLabel = (value) => RELATION_LABELS[value] || value || ''
const searchListResults = computed(() =>
  Array.isArray(searchResults.value) ? searchResults.value : []
)
const searchResultCount = computed(() => {
  if (Array.isArray(searchResults.value)) return searchResults.value.length
  const chunks = searchResults.value?.chunks?.length || 0
  const entities = searchResults.value?.entities?.length || 0
  const relations = searchResults.value?.relations?.length || 0
  return chunks + entities + relations
})
const showEmptyState = computed(
  () =>
    !isSearching.value &&
    searchPerformed.value &&
    searchResultCount.value === 0 &&
    (searchOnlyContext.value || !searchAnswer.value)
)
const showResultSummary = computed(
  () =>
    !isSearching.value &&
    searchPerformed.value &&
    searchResultCount.value > 0 &&
    (searchOnlyContext.value || searchListResults.value.length > 0)
)
const markdownDialogVisible = ref(false)
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
const activeResultTab = ref('chunks')
const searchPerformed = ref(false)

const graphData = ref({ nodes: [], edges: [] })

const isSearching = ref(false)
const searchProgress = ref(0)
const searchStatusText = ref('')

const editKbDialogVisible = ref(false)
const updateKbLoading = ref(false)
const editKbForm = ref({
  name: '',
  description: '',
})

let pollTimer = null // 轮询定时器
const POLL_INTERVAL = 3000 // 每 3 秒查一次

const startPollingIfNeeded = () => {
  stopPolling()

  // 如果有文件处于 uploaded / parsing / parsed / indexing 状态，就启动轮询
  const hasProcessing = files.value.some((f) =>
    ['uploaded', 'parsing', 'parsed', 'indexing'].includes(f.status)
  )

  if (hasProcessing) {
    console.log('🔄 检测到处理中的文件，启动状态轮询...')
    pollTimer = setInterval(async () => {
      await pollFileStatuses()
    }, POLL_INTERVAL)
  }
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const pollFileStatuses = async () => {
  const processingFiles = files.value.filter((f) =>
    ['uploaded', 'parsing', 'parsed', 'indexing'].includes(f.status)
  )

  if (processingFiles.length === 0) {
    console.log('✅ 所有文件处理完毕，停止轮询')
    stopPolling()
    return
  }

  for (const file of processingFiles) {
    try {
      const res = await api.get(`/knowledge/files/${file.id}/status`)
      if (res && res.data) {
        const oldStatus = file.status
        const newStatus = res.data.status

        file.status = newStatus
        file.error_message = res.data.error_message

        if (oldStatus !== newStatus) {
          console.log(`📊 文件 "${file.filename}" 状态变更: ${oldStatus} → ${newStatus}`)

          if (newStatus === 'indexed') {
            ElMessage.success(`"${file.filename}" 处理完成`)
          } else if (newStatus === 'error_parsing' || newStatus === 'error_indexing') {
            ElMessage.error(`"${file.filename}" 处理失败: ${res.data.error_message || '未知错误'}`)
          }
        }
      }
    } catch (err) {
      console.warn(`轮询文件 ${file.id} 状态失败:`, err.message)
    }
  }

  const stillProcessing = files.value.some((f) =>
    ['uploaded', 'parsing', 'parsed', 'indexing'].includes(f.status)
  )
  if (!stillProcessing) {
    console.log('✅ 所有文件处理完毕，停止轮询')
    stopPolling()
  }
}

const loadKbInfo = async () => {
  try {
    const res = await api.get(`/knowledge/${kbId}`).catch(() => null)
    if (res && res.data) {
      kbInfo.value = res.data
    } else {
      kbInfo.value = {
        id: kbId,
        name: '测试知识库',
        description: '这是一个测试知识库',
        created_at: new Date().toISOString(),
        creator: { id: 1, username: 'admin' },
      }
    }
  } catch (err) {
    console.error('加载知识库信息失败', err)
  }
}

const loadFiles = async () => {
  filesLoading.value = true
  try {
    const res = await api.get(`/knowledge/${kbId}/files`).catch(() => null)
    if (res && res.data) {
      files.value = res.data
    }
  } catch (err) {
    console.error('加载文件列表失败', err)
    ElMessage.error('加载文件列表失败')
  } finally {
    filesLoading.value = false
    startPollingIfNeeded()
  }
}

const loadGraph = async () => {
  try {
    console.log('📊 加载知识图谱...', kbId)
    const res = await getKnowledgeGraph(kbId, 100)
    
    if (res.status === 'success' && res.data) {
      graphData.value = {
        nodes: res.data.nodes || [],
        edges: res.data.edges || []
      }
      console.log('✅ 图谱加载成功:', {
        nodeCount: graphData.value.nodes.length,
        edgeCount: graphData.value.edges.length
      })
      
      if (graphData.value.nodes.length === 0) {
        ElMessage.warning('暂无图谱数据，请先上传并索引文档')
      }
    } else {
      ElMessage.warning('获取图谱失败或数据为空')
    }
  } catch (error) {
    console.error('加载图谱出错:', error)
    ElMessage.error(`加载图谱失败: ${error.message}`)
  }
}

const formatBytes = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}

const formatDate = (date) => {
  if (!date) return '-'
  const d = new Date(date)
  return d.toLocaleDateString('zh-CN') + ' ' + d.toLocaleTimeString('zh-CN')
}

const formatStatus = (status) => {
  const statusMap = {
    UPLOADED: '已上传',
    PARSING: '解析中',
    PARSED: '已解析',
    INDEXING: '索引中',
    INDEXED: '已索引',
    ERROR_PARSING: '解析失败',
    ERROR_INDEXING: '索引失败',
  }
  return statusMap[status] || status
}

const getStatusType = (status) => {
  const typeMap = {
    UPLOADED: 'info',
    PARSING: 'warning',
    PARSED: 'info',
    INDEXING: 'warning',
    INDEXED: 'success',
    ERROR_PARSING: 'danger',
    ERROR_INDEXING: 'danger',
  }
  return typeMap[status] || 'info'
}

const canPreviewMarkdown = (status) => {
  const normalized = String(status || '').toUpperCase()
  return ['PARSED', 'INDEXING', 'INDEXED'].includes(normalized)
}

const openMarkdownPreview = async (file) => {
  if (!canPreviewMarkdown(file.status)) {
    ElMessage.warning('该文件尚未生成 Markdown，请稍后再试')
    return
  }

  markdownDialogVisible.value = true
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

    const res = await api.get(`/knowledge/files/${file.id}/markdown`, {
      responseType: 'text',
    })
    const rawText = res?.data || ''
    markdownContent.value = await hydrateMarkdownAssets(rawText)
    markdownStatusText.value = '加载完成'
  } catch (err) {
    console.error('加载 Markdown 失败:', err)
    markdownError.value =
      err?.response?.data?.detail || err?.message || '加载 Markdown 失败，请稍后重试'
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
    if (url.startsWith('/knowledge/')) {
      return `/api${url}`
    }
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

watch(markdownDialogVisible, (visible) => {
  if (!visible) {
    releaseMarkdownBlobs()
  }
})

const showUploadDialog = () => {
  uploadDialogVisible.value = true
  uploadFileList.value = []
  enableOCR.value = 'disable' // 重置为默认选项
}

const handleFileSelect = (file, fileList) => {
  uploadFileList.value = fileList
}

const uploadFile = async () => {
  if (uploadFileList.value.length === 0) {
    return ElMessage.warning('请先选择文件')
  }

  uploadLoading.value = true
  try {
    const file = uploadFileList.value[0].raw || uploadFileList.value[0]
    const formData = new FormData()
    formData.append('kb_id', kbId)
    formData.append('file', file)
    formData.append('enable_ocr', enableOCR.value) // 将OCR选项发送给后端

    const res = await api.post('/knowledge/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })

    if (res && res.data && res.data.status === 'success') {
      ElMessage.success('文件上传成功，正在处理中...')
      uploadDialogVisible.value = false
      uploadFileList.value = []
      await loadFiles()
    } else {
      ElMessage.error(res?.data?.message || '上传失败')
    }
  } catch (err) {
    console.error('上传失败', err)
    const msg = err?.response?.data?.detail || err.message || '上传失败'
    ElMessage.error(msg)
  } finally {
    uploadLoading.value = false
  }
}

onUnmounted(() => {
  stopPolling()
})

const deleteFile = async (file) => {
  try {
    await ElMessageBox.confirm(`确定要删除 "${file.filename}" 吗？`, '警告', {
      confirmButtonText: '是',
      cancelButtonText: '否',
      type: 'warning',
    })

    await api.delete(`/knowledge/files/${file.id}`)
    ElMessage.success('删除成功')
    loadFiles()
  } catch (err) {
    // 如果是用户点击取消或关闭弹窗，ElMessageBox 会抛出 'cancel' 或 'close'
    if (err === 'cancel' || err === 'close') {
      return // 直接退出，不执行删除动作
    }

    console.error('删除失败', err)
    const msg = err?.response?.data?.detail || '删除失败'
    ElMessage.error(msg)
  }
}

const retryFile = async (file) => {
  try {
    await api.post(`/knowledge/files/${file.id}/retry`)
    ElMessage.success('重试任务已提交')
    loadFiles()
  } catch (err) {
    console.error('重试失败', err)
    const msg = err?.response?.data?.detail || '重试失败'
    ElMessage.error(msg)
  }
}

const goBack = () => {
  router.back()
}
const showEditKbDialog = () => {
  editKbForm.value = {
    name: kbInfo.value.name,
    description: kbInfo.value.description,
  }
  editKbDialogVisible.value = true
}

const handleUpdateKb = async () => {
  if (!editKbForm.value.name.trim()) {
    return ElMessage.warning('知识库名称不能为空')
  }

  updateKbLoading.value = true
  try {
    const res = await api.put(`/knowledge/update/${kbId}`, {
      name: editKbForm.value.name,
      description: editKbForm.value.description,
    })

    if (res && res.data) {
      ElMessage.success('修改成功')
      kbInfo.value.name = editKbForm.value.name
      kbInfo.value.description = editKbForm.value.description
      editKbDialogVisible.value = false
    }
  } catch (err) {
    console.error('修改失败', err)
    ElMessage.error(err.response?.data?.detail || '修改失败')
  } finally {
    updateKbLoading.value = false
  }
}
onMounted(() => {
  loadKbInfo()
  loadFiles()
  loadGraph()
})

const performSearch = async () => {
  if (!searchQuery.value.trim()) {
    return ElMessage.warning('请输入搜索关键词')
  }

  if (isSearching.value) {
    return ElMessage.warning('搜索已在进行中，请稍候')
  }

  searchPerformed.value = true
  isSearching.value = true
  searchProgress.value = 0
  searchStatusText.value = '⏳ 正在初始化查询任务...'

  searchAnswer.value = ''
  searchResults.value = { entities: [], relations: [], chunks: [] }

  let progressValue = 0
  const progressInterval = setInterval(() => {
    if (progressValue < 90) {
      progressValue += Math.random() * 15
      searchProgress.value = Math.min(progressValue, 90)

      if (searchProgress.value < 30) searchStatusText.value = '🔍 正在扫描向量数据库...'
      else if (searchProgress.value < 60) searchStatusText.value = '📊 正在分析知识图谱关联...'
      else searchStatusText.value = '🧠 正在组织背景知识...'
    }
  }, 400)

  try {
    const res = await api.post('/knowledge/query', {
      kb_id: kbId,
      query: searchQuery.value.trim(),
      mode: searchMode.value,
      top_k: searchTopK.value,
      only_context: searchOnlyContext.value, // 将开关状态发送给后端
      enable_rerank: effectiveSearchRerank.value,
    })

    clearInterval(progressInterval)
    searchProgress.value = 100
    searchStatusText.value = '✅ 查询完成'

    if (res && res.data && res.data.status === 'success') {
      const data = res.data.results

      if (searchOnlyContext.value) {
        const rawEntities = Array.isArray(data.entities) ? data.entities : []
        const rawRelations = Array.isArray(data.relationships)
          ? data.relationships
          : Array.isArray(data.relations)
            ? data.relations
            : []

        const entityTypeMap = {
          Disease: '疾病',
          Symptom: '症状',
          Drug: '药物',
          Ingredient: '成分',
          Indication: '适应症',
          Contraindication: '禁忌症',
          Interaction: '相互作用',
          Dosage: '用法用量',
          SideEffect: '不良反应',
          Test: '检查',
          Treatment: '治疗',
          Procedure: '手术/操作',
          Department: '科室',
          Population: '人群',
          Pathogen: '病原体',
          Biomarker: '医学指标',
          Guideline: '诊疗指南',
          Device: '器械',
          Document: '文献',
          Organization: '机构',
          Person: '人物',
          Location: '地点',
          Time: '时间',
          Data: '数据',
          Other: '其他',
        }


        const relationTypeMap = {
          TREATS: '治疗',
          HAS_SYMPTOM: '具有症状',
          HAS_SIDE_EFFECT: '不良反应',
          HAS_INGREDIENT: '包含成分',
          INDICATED_FOR: '适应症',
          CONTRAINDICATED_FOR: '禁忌',
          INTERACTS_WITH: '相互作用',
          REQUIRES_TEST: '需要检查',
          HAS_DOSAGE: '用法用量',
          RELATED_TO: '相关',
          PART_OF: '属于',
          CAUSES: '导致',

          ASSOCIATED_WITH: '相关',
          LOCATED_IN: '位于',
          PRODUCED_BY: '由其产生',
          USED_FOR: '用于',
          TREATMENT_OF: '治疗',
          DIAGNOSES: '诊断',
          PREVENTS: '预防',
          HAS_PROPERTY: '属性',
          CONTRAINDICATED_WITH: '禁忌',
        }

        const formatEntityType = (value) => entityTypeMap[value] || value || ''
        const formatRelationType = (value) => relationTypeMap[value] || value || ''

        const mappedEntities = rawEntities.map((item) => ({
          entity: item.entity_name ?? item.entity ?? item.name ?? '',
          type: formatEntityType(item.entity_type ?? item.type ?? ''),
          description: item.description ?? item.desc ?? '',
        }))

        const mappedRelations = rawRelations.map((rel) => ({
          entity1: rel.head ?? rel.entity1 ?? rel.source ?? '',
          entity2: rel.tail ?? rel.entity2 ?? rel.target ?? '',
          description: formatRelationType(rel.relation ?? rel.description ?? rel.type ?? ''),
        }))

        searchResults.value = {
          entities: mappedEntities,
          relations: mappedRelations, // ?? <el-table :data="searchResults.relations">
          chunks: data.chunks || [],
        }

        console.log('?????????:', searchResults.value)
      } else {
        searchAnswer.value = data?.answer || ""
      }
    } else {
      throw new Error(res?.data?.detail || '返回数据格式异常')
    }
  } catch (err) {
    clearInterval(progressInterval)
    console.error('搜索出错:', err)

    const errorMsg = err.response?.data?.detail || err.message
    if (errorMsg.includes('timeout') || err.code === 'ECONNABORTED') {
      ElMessage.error('⏱️ 查询超时：当前选择的模式可能运算量过大，请尝试切换至“向量检索”')
    } else {
      ElMessage.error(`搜索失败: ${errorMsg}`)
    }
  } finally {
    setTimeout(() => {
      isSearching.value = false
    }, 1000)
  }
}

const cancelSearch = () => {
  // 普通请求无法中途取消，只能重置 UI 状态
  isSearching.value = false
  searchProgress.value = 0
  searchStatusText.value = ''
  ElMessage.info('已停止显示搜索进度（后端查询可能仍在继续）')
}

const getProgressColor = (progress) => {
  if (progress < 33) return '#0f766e'
  if (progress < 66) return '#e6a23c'
  return '#67c23a'
}

const getScoreType = (score) => {
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'info'
}

const copyToClipboard = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
  } catch (err) {
    ElMessage.error('复制失败')
  }
}
</script>

<style scoped>
.kb-detail {
  --detail-ink: #15313b;
  --detail-subtle: #6b7f86;
  --detail-line: rgba(21, 49, 59, 0.1);
  --detail-card: rgba(255, 252, 247, 0.94);
  --detail-accent: #0f766e;
  padding: 4px 0 24px;
  color: var(--detail-ink);
}

.detail-breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 18px;
  padding: 18px 20px;
  border-radius: 24px;
  border: 1px solid var(--detail-line);
  background:
    radial-gradient(circle at top right, rgba(15, 118, 110, 0.12), transparent 24%),
    linear-gradient(135deg, #fffaf2 0%, #f4eee4 56%, #eef7f5 100%);
  box-shadow: 0 18px 40px rgba(31, 49, 58, 0.06);
  font-size: 14px;
}

.breadcrumb-separator {
  color: #c0c9cf;
}

.breadcrumb-text {
  font-weight: 700;
  color: var(--detail-ink);
  font-family: Georgia, 'Times New Roman', serif;
}

.kb-id {
  margin-left: auto;
  min-height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.76);
  font-size: 12px;
  color: var(--detail-subtle);
}

.detail-content {
  margin-top: 12px;
}

.file-list-card,
.info-card,
.search-card,
.graph-card {
  border-radius: 24px;
  border: 1px solid var(--detail-line);
  background: var(--detail-card);
  box-shadow: 0 18px 40px rgba(31, 49, 58, 0.06);
}

.file-list-card {
  overflow: hidden;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.title {
  font-weight: 700;
  color: var(--detail-ink);
  font-size: 16px;
}

.m-t-20 {
  margin-top: 20px;
}

.graph-card {
  height: 100%;
  min-height: 820px;
  display: flex;
  flex-direction: column;
}

:deep(.graph-card .el-card__body) {
  flex: 1;
  padding: 0;
  position: relative;
}

.graph-viewport {
  width: 100%;
  height: 720px;
  background:
    radial-gradient(circle at 20% 20%, rgba(15, 118, 110, 0.06), transparent 24%),
    radial-gradient(#d6dde0 1px, transparent 1px);
  background-size: auto, 20px 20px;
}

.kg-container {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.info-card,
.search-card {
  margin-bottom: 16px;
}

.search-actions {
  margin-top: 10px;
  display: flex;
  gap: 8px;
}

.search-actions :deep(.el-button-group) {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.search-actions :deep(.el-button-group > .el-button) {
  margin-left: 0 !important;
  border-radius: 18px !important;
}

.search-progress {
  margin-top: 12px;
  margin-bottom: 16px;
  padding: 14px;
  background: rgba(15, 118, 110, 0.06);
  border-radius: 18px;
  border: 1px solid rgba(15, 118, 110, 0.12);
}

.search-tips {
  margin-top: 12px;
}

.search-tip-item :deep(.el-alert__content) {
  padding: 0;
}

.search-tip-item :deep(ul) {
  margin: 0;
  padding-left: 20px;
}

.search-tip-item :deep(li) {
  font-size: 12px;
  color: #606266;
  line-height: 1.6;
  margin: 4px 0;
}

.search-results-stream::-webkit-scrollbar {
  width: 6px;
}

.search-results-stream::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 3px;
}

.search-options {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.option-group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.option-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--detail-subtle);
  min-width: 72px;
}

.option-hint {
  font-size: 11px;
  color: #909399;
}

.option-group :deep(.el-radio-group) {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.option-group :deep(.el-radio-button__inner) {
  min-height: 40px;
  padding: 0 18px !important;
  border-radius: 999px !important;
  border: 1px solid rgba(21, 49, 59, 0.08);
  background: rgba(255, 255, 255, 0.72);
  color: var(--detail-ink);
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  line-height: 1 !important;
  box-shadow: none !important;
  font-size: 12px;
}

.option-group :deep(.el-radio-button__inner > span),
.option-group :deep(.el-radio-button__inner .el-tooltip__trigger) {
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  line-height: 1 !important;
}

.progress-text {
  font-size: 13px;
  color: #0f172a;
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px dashed rgba(21, 49, 59, 0.12);
}

.info-item:last-child {
  border-bottom: none;
}

.label {
  font-weight: 700;
  color: var(--detail-subtle);
  min-width: 72px;
}

.value {
  color: var(--detail-ink);
  word-break: break-all;
}

.search-panel {
  margin-top: 16px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.72);
  border-radius: 20px;
  border: 1px solid rgba(21, 49, 59, 0.08);
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
}

.progress-message {
  color: #606266;
  font-weight: 500;
}

.progress-percent {
  color: var(--detail-accent);
  font-weight: 700;
}

.search-summary {
  padding: 8px 0;
  text-align: center;
  font-size: 13px;
  margin-bottom: 12px;
}

.summary-success {
  color: #16a34a;
  font-weight: 700;
}

.summary-empty {
  color: #dc2626;
  font-weight: 700;
}

.search-results-stream {
  max-height: 500px;
  overflow-y: auto;
  padding: 4px 0;
}

.result-item {
  padding: 14px;
  border: 1px solid rgba(21, 49, 59, 0.08);
  border-radius: 18px;
  margin-bottom: 12px;
  background: rgba(255, 255, 255, 0.78);
  transition: transform 0.2s ease, border-color 0.2s ease;
}

.result-item:hover {
  transform: translateY(-2px);
  border-color: rgba(15, 118, 110, 0.18);
}

.result-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 8px;
}

.result-index {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  background: linear-gradient(135deg, #0f766e, #146c94);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
}

.result-title-section {
  flex: 1;
}

.result-title {
  font-weight: 700;
  color: var(--detail-accent);
  font-size: 13px;
  word-break: break-word;
}

.result-source-tag,
.tips {
  font-size: 11px;
  color: #9aa4b2;
  margin-top: 4px;
}

.file-name-disabled {
  color: #9aa4b2;
  cursor: not-allowed;
}

.markdown-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.markdown-title {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

.markdown-subtitle {
  font-size: 12px;
  color: #6b7280;
}

.markdown-scroll {
  padding-right: 8px;
}

.markdown-body {
  font-size: 14px;
  line-height: 1.75;
  color: #0f172a;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  font-weight: 700;
  color: #0f172a;
  margin: 18px 0 10px;
}

.markdown-body :deep(code) {
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}

.markdown-body :deep(pre) {
  background: #112128;
  color: #e7f3ef;
  padding: 12px 14px;
  border-radius: 10px;
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
  padding: 8px 12px;
  border-left: 3px solid #cbd5f5;
  background: #f8fafc;
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
  padding: 6px 8px;
  text-align: left;
}

.markdown-body :deep(img) {
  max-width: 100%;
  border-radius: 6px;
}

:deep(.el-table) {
  font-size: 13px;
}

:deep(.el-card__header) {
  padding: 16px 20px;
  border-bottom: 1px solid rgba(21, 49, 59, 0.08);
}

:deep(.el-card__body) {
  padding: 16px 20px;
}

:deep(.el-input__wrapper),
:deep(.el-select__wrapper),
:deep(.el-textarea__inner) {
  border-radius: 20px;
  box-shadow: 0 0 0 1px rgba(21, 49, 59, 0.08) inset !important;
}

:deep(.el-button--primary) {
  --el-button-bg-color: #0f766e;
  --el-button-border-color: #0f766e;
  --el-button-hover-bg-color: #0d655e;
  --el-button-hover-border-color: #0d655e;
}

:deep(.el-button--primary.is-disabled),
:deep(.el-button--primary.is-disabled:hover),
:deep(.el-button--primary.is-disabled:focus) {
  background: rgba(15, 118, 110, 0.26) !important;
  border-color: rgba(15, 118, 110, 0.16) !important;
  color: rgba(255, 255, 255, 0.92) !important;
  box-shadow: none !important;
}

.info-card :deep(.el-button.is-link),
.search-card :deep(.el-button.is-link),
.graph-card :deep(.el-button.is-link) {
  border-radius: 14px !important;
  background: rgba(15, 118, 110, 0.1) !important;
  border: 1px solid rgba(15, 118, 110, 0.12) !important;
  box-shadow: none !important;
}

:deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background: #0f766e !important;
  border-color: #0f766e !important;
  color: #fff !important;
  box-shadow: none !important;
}

:deep(.el-switch__label.is-active) {
  color: #0f766e !important;
}

.option-group :deep(.el-switch.is-checked .el-switch__core) {
  background: #0f766e !important;
  border-color: #0f766e !important;
}

@media (max-width: 768px) {
  .detail-breadcrumb,
  .card-header,
  .option-group {
    flex-direction: column;
    align-items: flex-start;
  }

  .kb-id {
    margin-left: 0;
  }

  .graph-card {
    min-height: 640px;
  }

  .graph-viewport {
    height: 540px;
  }
}
</style>
