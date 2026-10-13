<template>
  <div class="chat-view-root">
    <div class="chat-page-wrapper">
    <div :class="['chat-sidebar', { collapsed: chatStore.sidebarCollapsed }]">
      <div class="sidebar-header">
        <el-button
          type="primary"
          placeholder="创建新对话"
          @click="handleNewSession"
          style="width: 100%"
        >
          <span style="margin-right: 6px">+</span> 新对话
        </el-button>
      </div>

      <div class="sidebar-content">
        <div v-if="chatStore.sessions.length === 0" class="empty-state">
          <div style="color: #94a3b8; text-align: center; padding: 20px 0">
            暂无对话记录
          </div>
        </div>

        <div
          v-for="session in chatStore.sessions"
          :key="session.id"
          :class="['session-item', { active: chatStore.activeSessionId === session.id }]"
          @click="switchSession(session.id)"
        >
          <div class="session-title">
            <span class="session-icon">💬</span>
            <span class="session-name">{{ session.title }}</span>
          </div>

          <div class="session-actions" @click.stop>
  <el-popover
    placement="right"
    :width="140"
    trigger="hover"
    popper-class="session-popover"
  >
    <template #reference>
      <el-icon class="action-btn" style="cursor: pointer">
        <MoreFilled />
      </el-icon>
    </template>
    <div class="action-menu">
      <div class="action-item" @click.stop="handleRenameSession(session.id, session.title)">
        ✏️ 重命名
      </div>
      <el-divider style="margin: 4px 0" />
      <div class="action-item danger" @click.stop="handleDeleteSession(session.id)">
        🗑️ 删除
      </div>
    </div>
  </el-popover>
</div>
        </div>
      </div>

      <div class="sidebar-footer"></div>
    </div>

    <div class="chat-page-main">
      <div class="chat-top-bar">
        <el-button
          type="text"
          :icon="chatStore.sidebarCollapsed ? ArrowRight : ArrowLeft"
          @click="chatStore.toggleSidebar"
          class="toggle-btn"
          title="展开/收起侧边栏"
        />

        <div class="chat-header">
          <div class="kb-selector">
            <span class="label">选择知识库:</span>
            <el-select
              v-model="selectedKbId"
              placeholder="请选择"
              filterable
              clearable
              @change="onKbChange"
              @clear="onKbClear"
            >
              <el-option v-for="kb in kbList" :key="kb.id" :label="kb.name" :value="kb.id" />
            </el-select>
          </div>
          <div class="info-text">
            <span v-if="selectedKbId"
              >已选择: <strong>{{ currentKbName }}</strong></span
            >
            <span v-else class="text-muted">未选择知识库（默认对话模式）</span>
          </div>

          <div class="chat-options">
            <el-radio-group v-model="chatMode" size="small" :disabled="chatStore.isLoading">
              
              <el-radio-button label="hybrid">混合</el-radio-button>
              <el-radio-button label="naive">向量</el-radio-button>
              <el-radio-button label="local">局部</el-radio-button>
              <el-radio-button label="global">全局</el-radio-button>
            </el-radio-group>

            <div class="option-item">
              <span class="option-label">  重排  </span>
              <el-switch
                v-model="rerankEnabled"
                :disabled="chatStore.isLoading || !isRerankEligible"
              />
              <span class="option-hint">  仅 naive/local/hybrid</span>
            </div>

            <el-select
              v-model="chatTopK"
              placeholder="结果数"
              size="small"
              :disabled="chatStore.isLoading"
              style="width: 100px; margin-left: 8px"
            >
              <el-option :label="'精确 (3)'" :value="3" />
              <el-option :label="'标准 (5)'" :value="5" />
              <el-option :label="'广泛 (10)'" :value="10" />
            </el-select>

            <el-button
              size="small"
              :icon="Delete"
              @click="handleClearMessages"
              style="margin-left: 8px"
            >
              清空记录
            </el-button>
          </div>
        </div>
      </div>

      <div class="chat-container">
        <div class="messages-wrapper">
          <div class="messages-scroll" ref="messagesRef">
            <div v-if="currentMessages.length === 0" class="welcome-section">
              <div class="welcome-icon">💬</div>
              <h3>开始对话</h3>
              <p>选择知识库后，输入你的问题，我会基于知识库内容为你解答</p>
              <div class="example-questions">
                <div class="example-title">示例问题：</div>
                <div
                  class="example-item"
                  v-for="(q, idx) in exampleQuestions"
                  :key="idx"
                  @click="selectExample(q)"
                >
                  {{ q }}
                </div>
              </div>
            </div>

            <div v-for="(msg, idx) in currentMessages" :key="idx" :class="['message-item', msg.role]">
              <div class="message-avatar">
                <span v-if="msg.role === 'user'" class="avatar-icon">👤</span>
                <span v-else class="avatar-icon">🤖</span>
              </div>
              <div class="message-content">
                <div :class="['message-bubble', { loading: msg.role === 'assistant' && chatStore.isLoading && !msg.content }]">
                  <div v-if="msg.role === 'user'" class="user-message-content">
                    <div v-if="msg.content" class="text-content">
                      {{ msg.content }}
                    </div>
                    <div
                      v-if="msg.attachments && msg.attachments.length"
                      class="message-image-list"
                    >
                      <el-image
                        v-for="(attachment, aIdx) in msg.attachments"
                        :key="attachment.id || aIdx"
                        class="message-image"
                        :src="getAttachmentDisplayUrl(attachment)"
                        :alt="attachment.filename || 'uploaded-image'"
                        fit="cover"
                        :preview-src-list="getAttachmentPreviewList(msg.attachments)"
                        :initial-index="aIdx"
                        preview-teleported
                      />
                    </div>
                  </div>

                  <div
                    v-else-if="msg.content"
                    class="text-content assistant-markdown"
                    v-html="renderAssistantMarkdown(msg.content)"
                  ></div>
                  <div v-else class="typing">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>

                  <div v-if="msg.references && msg.references.length" class="references">
                    <div class="ref-title">
                      <span>📚 参考来源：</span>
                      <el-button
                        v-if="msg.graph_path && msg.graph_path.length"
                        class="reference-action-btn"
                        link
                        type="primary"
                        size="small"
                        @click="openGraphPath(msg)"
                      >
                        推理路径
                      </el-button>
                    </div>
                    <div
                      v-for="group in groupReferences(msg.references)"
                      :key="group.key"
                      class="ref-item"
                    >
                      <div class="ref-main" @click="openReferenceGroup(group, msg)">
                        <span class="ref-file">{{ group.sourceFile || '未知来源' }}</span>
                        <span class="ref-count">共 {{ group.items.length }} 条引用</span>
                      </div>
                      <el-button
                        class="reference-action-btn"
                        link
                        type="primary"
                        size="small"
                        @click="openReferenceGroup(group, msg)"
                      >
                        查看原文
                      </el-button>
                    </div>
                  </div>
                </div>
                <div class="message-time">{{ formatTime(msg.timestamp) }}</div>
              </div>
            </div>
          </div>
        </div>

        <div class="chat-input-area">
          <div class="input-wrapper">
            <el-input
              v-model="inputValue"
              type="textarea"
              :rows="3"
              placeholder="输入你的问题... (Shift+Enter 换行, Enter 发送)"
              resize="none"
              @keydown.enter="handleKeyDown"
            />
          </div>
          <input
            ref="imageInputRef"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            class="hidden-file-input"
            @change="handleImageSelect"
          />
          <div v-if="selectedImages.length" class="selected-image-list">
            <div
              v-for="(item, idx) in selectedImages"
              :key="item.id"
              class="selected-image-item"
            >
              <img :src="item.preview_url" :alt="item.name" class="selected-image-thumb" />
              <div class="selected-image-name">{{ item.name }}</div>
              <el-button size="small" link type="danger" @click="removeSelectedImage(idx)">
                移除
              </el-button>
            </div>
          </div>
          <div class="input-controls">
            <el-button
              plain
              :disabled="chatStore.isLoading"
              @click="openImagePicker"
            >
              上传图片
            </el-button>
            <el-button
              v-if="chatStore.isLoading"
              type="danger"
              plain
              @click="handleCancelRequest"
            >
              取消
            </el-button>
            <el-button
              type="primary"
              :disabled="(!inputValue.trim() && selectedImages.length === 0) || chatStore.isLoading"
              :loading="chatStore.isLoading"
              @click="sendMessage"
            >
              发送
            </el-button>
          </div>
        </div>
      </div>
    </div>
    </div>

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
      <div v-else-if="markdownContent" class="markdown-preview">
        <div v-if="markdownAnchors.length" class="anchor-list">
          <div
            v-for="item in markdownAnchors"
            :key="item.id"
            :class="['anchor-item', { disabled: !item.matched }]"
            @click="item.matched && scrollToAnchor(item.id)"
          >
            {{ item.text }}
          </div>
        </div>
        <div
          ref="markdownBodyRef"
          class="markdown-body"
          v-html="markdownHtml"
        ></div>
      </div>
      <div v-else class="markdown-empty">
        <el-empty description="暂无可预览内容" />
      </div>
    </el-scrollbar>

    <template #footer>
      <el-button @click="markdownVisible = false">关闭</el-button>
    </template>
    </el-dialog>

    <el-drawer v-model="graphDrawerVisible" size="70%" direction="rtl" class="graph-drawer">
    <template #header>
      <div class="graph-drawer-header">
        <div class="graph-drawer-title">推理路径</div>
        <div class="graph-drawer-subtitle" v-if="graphPath && graphPath.length">
          当前路径节点已高亮
        </div>
      </div>
    </template>

    <div class="graph-drawer-body">
      <div v-if="graphLoading" class="graph-loading">
        <el-skeleton :rows="6" animated />
      </div>
      <div v-else-if="!graphData.nodes.length" class="graph-empty">
        <el-empty description="暂无图谱数据" />
      </div>
      <GraphCanvas
        v-else
        :data="graphData"
        :loading="graphLoading"
        :highlight-nodes="highlightNodes"
        :highlight-edges="highlightEdges"
      />
    </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick, watch, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, MoreFilled, ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import api, { chatStreamRequest, getKnowledgeGraph } from '@/api/index'
import { useChatStore } from '@/stores/chat'
import GraphCanvas from '@/components/GraphCanvas.vue'

const chatStore = useChatStore()

const selectedKbId = ref(null)
const inputValue = ref('')
const imageInputRef = ref(null)
const selectedImages = ref([])
const kbList = ref([])
const messagesRef = ref(null)
const chatMode = ref('hybrid')
const chatTopK = ref(5)
const rerankEnabled = ref(true)
const mdParser = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
})
const previewParser = new MarkdownIt({
  html: true,
  linkify: true,
  breaks: true,
})

const markdownVisible = ref(false)
const markdownLoading = ref(false)
const markdownError = ref('')
const markdownContent = ref('')
const markdownTitle = ref('')
const markdownStatusText = ref('')
const markdownBodyRef = ref(null)
const markdownBlobUrls = ref([])
const markdownAnchors = ref([])
const markdownHtml = computed(() =>
  markdownContent.value ? previewParser.render(markdownContent.value) : ''
)

const graphDrawerVisible = ref(false)
const graphLoading = ref(false)
const graphData = ref({ nodes: [], edges: [] })
const graphPath = ref([])

const kbFileCache = ref(new Map())
const kbFileMarkdownCache = ref(new Map())
const resolvedRefCache = ref(new Map())

const MAX_CHAT_IMAGE_COUNT = 3
const MAX_CHAT_IMAGE_SIZE = 5 * 1024 * 1024
const ALLOWED_CHAT_IMAGE_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp'])

const exampleQuestions = [
  '这份文档的主要内容是什么？',
  '如何使用这个产品？',
  '能否总结一下关键要点？',
  '有什么需要注意的地方吗？',
]

const currentMessages = computed(() => {
  const sessionId = chatStore.activeSessionId
  if (!sessionId) return []
  return chatStore.getMessages(sessionId)
})

const currentKbName = computed(() => {
  const kb = kbList.value.find((k) => k.id === selectedKbId.value)
  return kb ? kb.name : ''
})

const isRerankEligible = computed(() => ['naive', 'local', 'hybrid'].includes(chatMode.value))
const effectiveRerank = computed(() => (isRerankEligible.value ? rerankEnabled.value : false))
const highlightNodes = computed(() => {
  const nodes = new Set()
  ;(graphPath.value || []).forEach((item) => {
    if (item?.source) nodes.add(String(item.source))
    if (item?.target) nodes.add(String(item.target))
  })
  return Array.from(nodes)
})
const highlightEdges = computed(() => graphPath.value || [])

const loadKbs = async () => {
  try {
    const res = await api.get('/knowledge/list').catch(() => null)
    if (res && res.data) {
      kbList.value = res.data
    }
  } catch (err) {
    console.error('加载知识库失败', err)
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

const injectAnchor = (rawText, anchor) => {
  if (!anchor) return { text: rawText, matched: false }
  const escaped = anchor.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const regex = new RegExp(escaped)
  if (!regex.test(rawText)) return { text: rawText, matched: false }
  const text = rawText.replace(regex, `<mark class="anchor-mark">${anchor}</mark>`)
  return { text, matched: true }
}

const injectAnchors = (rawText, anchors = []) => {
  let text = rawText
  const items = []

  anchors.forEach((anchor, idx) => {
    const safeAnchor = String(anchor || '').trim()
    if (!safeAnchor) return
    const id = `ref-${idx}`
    if (text.includes(safeAnchor)) {
      text = text.replace(
        safeAnchor,
        `<mark id="${id}" class="anchor-mark">${safeAnchor}</mark>`
      )
      items.push({ id, text: safeAnchor, matched: true })
    } else {
      items.push({ id, text: safeAnchor, matched: false })
    }
  })

  markdownAnchors.value = items
  return text
}

const scrollToAnchor = async (id = null) => {
  await nextTick()
  const selector = id ? `#${id}` : 'mark.anchor-mark'
  const el = markdownBodyRef.value?.querySelector(selector)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

const getKbFiles = async (kbId) => {
  if (!kbId) return []
  if (kbFileCache.value.has(kbId)) {
    return kbFileCache.value.get(kbId)
  }
  try {
    const res = await api.get(`/knowledge/${kbId}/files`)
    const files = res?.data || []
    kbFileCache.value.set(kbId, files)
    kbFileCache.value = new Map(kbFileCache.value)
    return files
  } catch (err) {
    console.warn('加载知识库文件列表失败:', kbId, err)
    return []
  }
}

const resolveFileIdByName = async (kbId, filename) => {
  if (!kbId || !filename) return null
  const files = await getKbFiles(kbId)
  const hit = files.find((item) => item.filename === filename)
  return hit?.id || null
}

const normalizeText = (text) => String(text || '').replace(/\s+/g, '').toLowerCase()
const getRefCacheKey = (ref) => ref?.anchor || (ref?.content ? ref.content.slice(0, 120) : '')

const updateMessageReferences = (sessionId, message, references) => {
  if (!sessionId || !message) return
  const messages = chatStore.getMessages(sessionId)
  const index = messages.indexOf(message)
  if (index >= 0) {
    chatStore.updateMessageAt(sessionId, index, { references })
  } else {
    message.references = references
  }
}

const getMarkdownText = async (fileId) => {
  if (!fileId) return ''
  if (kbFileMarkdownCache.value.has(fileId)) {
    return kbFileMarkdownCache.value.get(fileId)
  }
  const res = await api.get(`/knowledge/files/${fileId}/markdown`, {
    responseType: 'text',
  })
  const rawText = typeof res?.data === 'string' ? res.data : ''
  kbFileMarkdownCache.value.set(fileId, rawText)
  kbFileMarkdownCache.value = new Map(kbFileMarkdownCache.value)
  return rawText
}

const resolveFileIdByContent = async (kbId, anchor) => {
  if (!kbId || !anchor) return null
  const files = await getKbFiles(kbId)
  const anchorKey = normalizeText(anchor)
  if (!anchorKey) return null

  for (const file of files) {
    try {
      const rawText = await getMarkdownText(file.id)
      if (!rawText) continue
      if (normalizeText(rawText).includes(anchorKey)) {
        return { fileId: file.id, filename: file.filename, rawText }
      }
    } catch (err) {
      console.warn('匹配原文失败:', file?.id, err)
    }
  }
  return null
}

const groupReferences = (refs = []) => {
  const groups = new Map()
  refs.forEach((ref, index) => {
    const cacheKey = getRefCacheKey(ref)
    const cached = cacheKey ? resolvedRefCache.value.get(cacheKey) : null
    const fileId = ref?.file_id || cached?.fileId || null
    const sourceFile = ref?.source_file || cached?.sourceFile || null
    const key = fileId
      ? `file:${fileId}`
      : sourceFile
      ? `name:${sourceFile}`
      : `unknown:${index}`

    if (!groups.has(key)) {
      groups.set(key, {
        key,
        fileId,
        sourceFile,
        items: [],
      })
    }
    groups.get(key).items.push(ref)
  })
  return Array.from(groups.values())
}

const resolveUnknownReferencesForMessage = async (sessionId, message) => {
  try {
    const kbId = message?.kb_id || selectedKbId.value
    if (!kbId) return

    const refs = Array.isArray(message?.references) ? message.references : []
    if (!refs.length) return

    const unresolved = refs
      .map((ref, idx) => ({ ref, idx }))
      .filter((item) => !item.ref?.file_id && !item.ref?.source_file && item.ref?.anchor)

    if (!unresolved.length) return

    const files = await getKbFiles(kbId)
    if (!files.length) return

    const normalizedAnchors = unresolved.map((item) => ({
      idx: item.idx,
      anchor: item.ref.anchor,
      key: normalizeText(item.ref.anchor),
    }))

    const updated = refs.map((ref) => ({ ...ref }))
    const pending = new Set(normalizedAnchors.map((item) => item.idx))

    for (const file of files) {
      if (pending.size === 0) break
      let rawText = ''
      try {
        rawText = await getMarkdownText(file.id)
      } catch (err) {
        console.warn('匹配原文失败:', file?.id, err)
        continue
      }
      if (!rawText) continue
      const normalizedDoc = normalizeText(rawText)
      for (const item of normalizedAnchors) {
        if (!pending.has(item.idx)) continue
        if (!item.key) {
          pending.delete(item.idx)
          continue
        }
        if (normalizedDoc.includes(item.key)) {
          const ref = updated[item.idx]
          ref.file_id = ref.file_id || String(file.id)
          ref.source_file = ref.source_file || file.filename
          const cacheKey = getRefCacheKey(ref)
          if (cacheKey) {
            resolvedRefCache.value.set(cacheKey, {
              fileId: String(file.id),
              sourceFile: file.filename,
            })
          }
          pending.delete(item.idx)
        }
      }
    }

    if (pending.size !== normalizedAnchors.length) {
      resolvedRefCache.value = new Map(resolvedRefCache.value)
      updateMessageReferences(sessionId, message, updated)
    }
  } catch (err) {
    console.warn('解析引用失败:', err)
  }
}

const resolveUnknownReferencesForSession = async (sessionId) => {
  try {
    const messages = chatStore.getMessages(sessionId)
    for (const message of messages) {
      if (message?.references?.length) {
        await resolveUnknownReferencesForMessage(sessionId, message)
      }
    }
  } catch (err) {
    console.warn('解析历史引用失败:', err)
  }
}

const openReferenceGroup = async (group, msg) => {
  markdownVisible.value = true
  markdownLoading.value = true
  markdownError.value = ''
  markdownContent.value = ''
  markdownAnchors.value = []
  markdownTitle.value = group?.sourceFile || '文档预览'
  markdownStatusText.value = '正在加载文档内容...'

  try {
    const kbId = msg?.kb_id || selectedKbId.value
    let fileId = group?.fileId || null
    let rawText = ''

    if (!fileId && kbId && group?.sourceFile) {
      fileId = await resolveFileIdByName(kbId, group.sourceFile)
    }

    if (!fileId && kbId) {
      const firstAnchor = (group?.items || []).find((item) => item?.anchor)?.anchor
      if (firstAnchor) {
        markdownStatusText.value = '正在匹配原文...'
        const hit = await resolveFileIdByContent(kbId, firstAnchor)
        if (hit?.fileId) {
          fileId = hit.fileId
          rawText = hit.rawText || ''
          if (hit.filename) {
            markdownTitle.value = hit.filename
          }
        }
      }
    }

    if (!fileId) {
      markdownError.value = '未匹配到原文文件'
      markdownStatusText.value = '无法定位'
      return
    }

    if (!rawText) {
      rawText = await getMarkdownText(fileId)
    }

    const anchors = (group?.items || [])
      .map((item) => item?.anchor)
      .filter((val) => val)

    let injectedText = rawText
    let matchedCount = 0
    if (anchors.length > 0) {
      injectedText = injectAnchors(rawText, anchors)
      matchedCount = markdownAnchors.value.filter((item) => item.matched).length
    }

    const processed = await hydrateMarkdownAssets(injectedText)
    markdownContent.value = processed
    markdownStatusText.value = matchedCount > 0 ? '已定位到引用片段' : '已打开文档，未精准定位'

    const firstMatched = markdownAnchors.value.find((item) => item.matched)
    await scrollToAnchor(firstMatched?.id || null)

    if (anchors.length > 0 && fileId) {
      const fileName = markdownTitle.value
      ;(group?.items || []).forEach((refItem) => {
        const key = getRefCacheKey(refItem)
        if (!key) return
        resolvedRefCache.value.set(key, { fileId, sourceFile: fileName })
      })
      resolvedRefCache.value = new Map(resolvedRefCache.value)
    }
  } catch (err) {
    console.error(err)
    markdownError.value = err?.response?.data?.detail || err?.message || 'Markdown 预览失败'
    markdownStatusText.value = '加载失败'
  } finally {
    markdownLoading.value = false
  }
}

const openReference = (ref, msg) => {
  openReferenceGroup(
    { fileId: ref?.file_id || null, sourceFile: ref?.source_file || null, items: [ref] },
    msg
  )
}

const loadGraphForMessage = async (kbId) => {
  graphLoading.value = true
  try {
    const res = await getKnowledgeGraph(kbId, 300)
    const payload = res?.data || res
    graphData.value = payload?.data || payload || { nodes: [], edges: [] }
  } catch (err) {
    console.error(err)
    graphData.value = { nodes: [], edges: [] }
  } finally {
    graphLoading.value = false
  }
}

const openGraphPath = async (msg) => {
  const kbId = msg?.kb_id || selectedKbId.value
  if (!kbId) {
    ElMessage.warning('未找到知识库')
    return
  }
  graphPath.value = msg?.graph_path || []
  graphDrawerVisible.value = true
  await loadGraphForMessage(kbId)
  if (!graphPath.value.length) {
    ElMessage.info('暂无推理路径')
  }
}

const handleNewSession = () => {
  chatStore.createSession('新对话', selectedKbId.value)
  inputValue.value = ''
  ElMessage.success('已创建新对话')
}

const switchSession = async (sessionId) => {
  chatStore.activeSessionId = sessionId
  const session = chatStore.sessions.find(s => s.id === sessionId)
  if (session) {
    selectedKbId.value = session.kb_id || null
  }
  inputValue.value = ''

  await chatStore.loadMessages(sessionId)
  await resolveUnknownReferencesForSession(sessionId)
  await scrollToBottom()
}

const handleDeleteSession = async (sessionId) => {
  try {
    await ElMessageBox.confirm('确定要删除这个对话吗？', '提示', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await chatStore.deleteSession(sessionId)
    ElMessage.success('已删除对话')
  } catch (err) {
    if (err !== 'cancel') console.error('删除失败', err)
  }
}

const handleRenameSession = async (sessionId, currentTitle) => {
  try {
    const { value } = await ElMessageBox.prompt('请输入新的对话名称', '重命名对话', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputValue: currentTitle || '',
      inputPlaceholder: '例如：用药咨询',
      inputPattern: /\S+/,
      inputErrorMessage: '标题不能为空',
      closeOnClickModal: false,
    })

    const nextTitle = value.trim()
    if (!nextTitle || nextTitle === currentTitle) return

    await chatStore.renameSession(sessionId, nextTitle)
    ElMessage.success('已重命名对话')
  } catch (err) {
    if (err !== 'cancel') console.error('重命名失败', err)
  }
}


const onKbChange = () => {
  inputValue.value = ''
  if (chatStore.activeSessionId) {
    const session = chatStore.sessions.find(s => s.id === chatStore.activeSessionId)
    if (session) {
      session.kb_id = selectedKbId.value
    }
  }
  scrollToBottom()
}

const onKbClear = () => {
  selectedKbId.value = null
  inputValue.value = ''
  if (chatStore.activeSessionId) {
    const session = chatStore.sessions.find(s => s.id === chatStore.activeSessionId)
    if (session) {
      session.kb_id = null
    }
  }
}

const selectExample = (question) => {
  inputValue.value = question
}

const renderAssistantMarkdown = (content) => {
  if (!content) return ''
  return mdParser.render(content)
}

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

const revokeLocalPreviewUrl = (url) => {
  // 预览 URL 生命周期管理：移除或替换后及时释放，避免浏览器内存持续增长。
  if (url && String(url).startsWith('blob:')) {
    try {
      URL.revokeObjectURL(url)
    } catch (err) {
      console.warn('释放图片预览 URL 失败:', err)
    }
  }
}

const openImagePicker = () => {
  imageInputRef.value?.click()
}

const clearSelectedImages = () => {
  selectedImages.value.forEach((item) => revokeLocalPreviewUrl(item.preview_url))
  selectedImages.value = []
  if (imageInputRef.value) {
    imageInputRef.value.value = ''
  }
}

const removeSelectedImage = (index) => {
  const item = selectedImages.value[index]
  if (item) {
    revokeLocalPreviewUrl(item.preview_url)
  }
  selectedImages.value.splice(index, 1)
}

const handleImageSelect = (evt) => {
  const files = Array.from(evt.target?.files || [])
  if (!files.length) return

  if (selectedImages.value.length + files.length > MAX_CHAT_IMAGE_COUNT) {
    ElMessage.warning(`最多上传 ${MAX_CHAT_IMAGE_COUNT} 张图片`)
    evt.target.value = ''
    return
  }

  for (const file of files) {
    // 校验逻辑说明：前端只做“提前拦截”，最终以后端校验为准。
    if (!ALLOWED_CHAT_IMAGE_TYPES.has(file.type)) {
      ElMessage.warning(`不支持的图片格式: ${file.type || 'unknown'}`)
      continue
    }
    if (file.size > MAX_CHAT_IMAGE_SIZE) {
      ElMessage.warning('单张图片大小不能超过 5MB')
      continue
    }

    selectedImages.value.push({
      id: `${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
      name: file.name,
      size: file.size,
      type: file.type,
      file,
      preview_url: URL.createObjectURL(file),
    })
  }

  // 允许用户重复选择同一文件。
  evt.target.value = ''
}

const getAttachmentDisplayUrl = (attachment) => {
  if (!attachment || typeof attachment !== 'object') return ''
  return (
    attachment.display_url ||
    attachment.preview_url ||
    attachment.minio_url ||
    ''
  )
}

const getAttachmentPreviewList = (attachments = []) => {
  // 预览列表统一从结构化附件里生成，保证“点击任意一张”都能在同组里左右切换浏览。
  return (attachments || [])
    .map((item) => getAttachmentDisplayUrl(item))
    .filter((url) => Boolean(url))
}

const scrollToBottom = async () => {
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

const handleClearMessages = async () => {
  try {
    await ElMessageBox.confirm('确定要清空当前对话记录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    chatStore.clearMessages(chatStore.activeSessionId)
    ElMessage.success('已清空记录')
  } catch {
  }
}

const handleCancelRequest = () => {
  chatStore.abortCurrentRequest()
  ElMessage.info('已取消请求')
}

const sendMessage = async () => {
  if (!inputValue.value.trim() && selectedImages.value.length === 0) return

  if (!chatStore.activeSessionId) {
    chatStore.createSession('新对话', selectedKbId.value)
  }

  const currentSessionId = chatStore.activeSessionId
  const selectedImageFiles = selectedImages.value.map((item) => item.file).filter(Boolean)
  const localUserAttachments = selectedImages.value.map((item) => ({
    id: item.id,
    filename: item.name,
    content_type: item.type,
    size: item.size,
    preview_url: item.preview_url,
    display_url: item.preview_url,
  }))

  const userMsg = {
    role: 'user',
    content: inputValue.value.trim() || '【已上传图片】',
    attachments: localUserAttachments,
    timestamp: Date.now(),
  }
  const userMsgIndex = chatStore.getMessages(currentSessionId).length
  chatStore.addMessage(currentSessionId, userMsg)

  const userQuestion = inputValue.value
  const pendingLocalPreviewUrls = localUserAttachments
    .map((item) => item.preview_url)
    .filter((url) => typeof url === 'string' && url.startsWith('blob:'))
  inputValue.value = ''
  selectedImages.value = []
  if (imageInputRef.value) {
    imageInputRef.value.value = ''
  }
  chatStore.setLoading(true)

  const assistantMsg = {
    role: 'assistant',
    content: '',
    timestamp: Date.now(),
    references: [],
    graph_path: [],
    kb_id: selectedKbId.value,
  }
  chatStore.addMessage(currentSessionId, assistantMsg)

  const controller = chatStore.createAbortController()

  // 前端 sessionId 作为 thread_id 传入，保持会话关联。
  try {
    await chatStreamRequest(
      userQuestion,
      selectedKbId.value,
      currentSessionId,        // ← 传真实 sessionId，而非 'default_user'
      chatTopK.value,
      chatMode.value,
      effectiveRerank.value,
      selectedImageFiles,

      (tokenContent) => {
        assistantMsg.content += tokenContent
        chatStore.updateLastMessage(currentSessionId, { content: assistantMsg.content })
        scrollToBottom()
      },

      (metadata) => {
        console.log('📚 元数据:', metadata)
        // 兜底：若后端因流式差异未产出 token，但 metadata 已判定需要澄清，
        // 则直接把澄清问题写入当前助手消息，保证用户可见。
        // metadata 回写 user_attachments 时，替换本地 blob 预览，避免一直占用内存。
        if (Array.isArray(metadata?.user_attachments) && metadata.user_attachments.length > 0) {
          pendingLocalPreviewUrls.forEach((url) => revokeLocalPreviewUrl(url))
          chatStore.updateMessageAt(currentSessionId, userMsgIndex, {
            attachments: metadata.user_attachments,
          })
        }
        if (metadata?.clarification_needed && metadata?.clarification_question && !assistantMsg.content) {
          assistantMsg.content = metadata.clarification_question
          chatStore.updateLastMessage(currentSessionId, { content: assistantMsg.content })
          scrollToBottom()
        }

        // metadata 统一回写：不依赖 references 是否存在。
        // 原因：图片链路（effective_query/understanding_status）即使没有 references 也要可见。
        chatStore.updateLastMessage(currentSessionId, {
          references: metadata.references || [],
          graph_path: metadata.graph_path || [],
          kb_id: metadata.kb_id || selectedKbId.value,
          rewrite_applied: metadata.rewrite_applied,
          original_query: metadata.original_query,
          rewritten_query: metadata.rewritten_query,
          rewrite_reason: metadata.rewrite_reason,
          rewrite_confidence: metadata.rewrite_confidence,
          clarification_needed: metadata.clarification_needed,
          clarification_question: metadata.clarification_question,
          clarification_reason: metadata.clarification_reason,
          clarification_confidence: metadata.clarification_confidence,
          pending_query: metadata.pending_query,
          has_images: metadata.has_images,
          image_count: metadata.image_count,
          effective_query: metadata.effective_query,
          image_summary: metadata.image_summary,
          image_understanding_status: metadata.image_understanding_status,
          image_understanding_reason: metadata.image_understanding_reason,
        })

        const messages = chatStore.getMessages(currentSessionId)
        const lastMessage = messages[messages.length - 1]
        if (lastMessage?.references?.length) {
          resolveUnknownReferencesForMessage(currentSessionId, lastMessage)
        }
      },

      (error) => {
        console.error('❌ 聊天出错:', error)
        if (error.name !== 'AbortError') {
          ElMessage.error(`请求失败: ${error.message}`)
          const messages = chatStore.getMessages(currentSessionId)
          if (messages.length > 0 && messages[messages.length - 1]?.role === 'assistant' && !messages[messages.length - 1].content) {
            messages.pop()
          }
        }
      },

      // onDone — 流式完成后，刷新后端自动生成的标题
      async (data) => {
        console.log('✅ 聊天完成:', data)
        chatStore.setLoading(false)
        scrollToBottom()

        await chatStore.refreshSessionTitle(currentSessionId)
      },

      controller.signal
    )
  } catch (err) {
    if (err.name !== 'AbortError') {
      console.error('❌ 发送消息失败:', err)
      ElMessage.error('发送失败')
    }
  } finally {
    // 确保万一，在这里兜底重置加载状态，防止发生按钮持续加载的情况
    chatStore.setLoading(false)
  }
}


// 键盘事件处理（Shift+Enter 换行，Enter 发送）
const handleKeyDown = (evt) => {
  if (evt.key === 'Enter' && !evt.shiftKey) {
    evt.preventDefault()
    sendMessage()
  }
}

watch(
  () => currentMessages.value.length,
  () => {
    scrollToBottom()
  }
)

watch(markdownVisible, (visible) => {
  if (!visible) {
    releaseMarkdownBlobs()
    markdownAnchors.value = []
  }
})

// 页面切换时保留流式请求；卸载仅释放未发送图片的预览 URL。
onBeforeUnmount(() => {
  clearSelectedImages()
})

onMounted(async () => {
  await loadKbs()

  await chatStore.loadSessions()

  if (chatStore.sessions.length === 0) {
    chatStore.createSession('新对话', null)
  }

  if (!chatStore.activeSessionId && chatStore.sessions.length > 0) {
    const firstSession = chatStore.sessions[0]
    chatStore.activeSessionId = firstSession.id
    selectedKbId.value = firstSession.kb_id || null
    await chatStore.loadMessages(firstSession.id)
    await resolveUnknownReferencesForSession(firstSession.id)
  }

  await scrollToBottom()
})

</script>

<style scoped>
.chat-view-root {
  --chat-ink: #15313b;
  --chat-subtle: #6b7f86;
  --chat-line: rgba(21, 49, 59, 0.1);
  --chat-card: rgba(255, 252, 247, 0.94);
  --chat-accent: #0f766e;
  height: 100%;
  color: var(--chat-ink);
}

.chat-page-wrapper {
  display: flex;
  height: 100%;
  gap: 16px;
  padding: 4px 0 8px;
  background:
    radial-gradient(circle at top right, rgba(15, 118, 110, 0.08), transparent 24%),
    linear-gradient(180deg, #f5f0e8 0%, #f6faf8 36%, #f7f8f4 100%);
  overflow: hidden;
}

.chat-sidebar,
.messages-wrapper,
.chat-input-area,
.chat-top-bar {
  border: 1px solid var(--chat-line);
  border-radius: 24px;
  background: var(--chat-card);
  box-shadow: 0 18px 40px rgba(31, 49, 58, 0.06);
}

.chat-sidebar {
  width: 300px;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease, margin-left 0.3s ease;
  overflow: hidden;
}

.chat-sidebar.collapsed {
  width: 0;
  border: none;
  box-shadow: none;
}

.sidebar-header {
  padding: 18px;
  border-bottom: 1px solid rgba(21, 49, 59, 0.08);
  background:
    radial-gradient(circle at top, rgba(15, 118, 110, 0.12), transparent 55%),
    rgba(255, 255, 255, 0.55);
}

.sidebar-header button {
  width: 100%;
  min-height: 44px;
  border-radius: 14px;
  font-weight: 700;
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.empty-state {
  display: grid;
  place-items: center;
  height: 100%;
  color: #94a3b8;
}

.session-item {
  padding: 14px 16px;
  margin-bottom: 10px;
  border-radius: 18px;
  cursor: pointer;
  transition: transform 0.18s ease, background 0.18s ease, border-color 0.18s ease;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1px solid transparent;
  background: rgba(255, 255, 255, 0.66);
}

.session-item:hover {
  transform: translateY(-2px);
  background: rgba(255, 255, 255, 0.9);
  border-color: rgba(15, 118, 110, 0.12);
}

.session-item.active {
  background: rgba(15, 118, 110, 0.1);
  border-color: rgba(15, 118, 110, 0.18);
}

.session-item.active .session-name {
  color: var(--chat-accent);
  font-weight: 700;
}

.session-title {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.session-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.session-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #334155;
  font-size: 14px;
}

.session-actions {
  opacity: 0;
  transition: opacity 0.2s;
}

.session-item:hover .session-actions {
  opacity: 1;
}

.action-btn {
  font-size: 16px;
  color: #94a3b8;
}

.action-btn:hover {
  color: var(--chat-accent);
}

.action-menu {
  padding: 6px;
  display: grid;
  gap: 4px;
}

.action-item {
  min-height: 38px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  border-radius: 14px;
  transition: background 0.2s, color 0.2s;
  color: #475569;
}

.action-item:hover {
  background: rgba(15, 118, 110, 0.08);
  color: var(--chat-accent);
}

.action-item.danger:hover {
  background: #fee2e2;
  color: #ef4444;
}

.sidebar-footer {
  height: 16px;
  border-top: 1px solid rgba(21, 49, 59, 0.08);
}

.chat-page-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
  gap: 16px;
}

.chat-top-bar {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-height: 76px;
  padding: 18px;
  overflow: visible;
}

.toggle-btn {
  font-size: 18px;
  padding: 10px;
  color: #64748b;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
}

.toggle-btn:hover {
  color: var(--chat-accent);
  background: rgba(15, 118, 110, 0.08);
}

.chat-header {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
  min-width: 0;
  flex-wrap: wrap;
}

.kb-selector {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.kb-selector .label,
.option-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--chat-subtle);
  white-space: nowrap;
}

.kb-selector :deep(.el-select) {
  width: 220px;
}

.info-text {
  min-height: 36px;
  padding: 0 14px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.72);
  color: #64748b;
  font-size: 13px;
}

.info-text strong {
  color: var(--chat-accent);
  font-weight: 700;
}

.text-muted {
  color: #94a3b8;
}

.chat-options {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-left: auto;
}

.option-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
}

.option-hint {
  font-size: 11px;
  color: #94a3b8;
}

.chat-container {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  gap: 16px;
  overflow: hidden;
}

.messages-wrapper {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.messages-scroll {
  height: 100%;
  overflow-y: auto;
  padding: 28px 24px;
}

.welcome-section {
  max-width: 720px;
  margin: 0 auto;
  text-align: center;
  padding: 56px 20px;
  color: #64748b;
}

.welcome-icon {
  display: grid;
  place-items: center;
  width: 88px;
  height: 88px;
  margin: 0 auto 18px;
  border-radius: 28px;
  background:
    radial-gradient(circle at top, rgba(15, 118, 110, 0.16), transparent 60%),
    rgba(255, 255, 255, 0.9);
  font-size: 40px;
}

.welcome-section h3 {
  margin: 0 0 10px;
  font-size: 34px;
  font-family: Georgia, 'Times New Roman', serif;
  color: var(--chat-ink);
}

.welcome-section p {
  margin-bottom: 26px;
  line-height: 1.8;
}

.example-questions {
  display: grid;
  gap: 10px;
  max-width: 560px;
  margin: 0 auto;
}

.example-title {
  font-weight: 700;
  color: var(--chat-subtle);
  margin-bottom: 4px;
}

.example-item {
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(21, 49, 59, 0.08);
  border-radius: 18px;
  cursor: pointer;
  transition: transform 0.18s ease, border-color 0.18s ease;
  text-align: left;
}

.example-item:hover {
  transform: translateY(-2px);
  border-color: rgba(15, 118, 110, 0.18);
}

.message-item {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

.message-item.user {
  flex-direction: row-reverse;
}

.message-avatar {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: 16px;
  background: rgba(21, 49, 59, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
}

.message-content {
  max-width: 74%;
}

.message-bubble {
  padding: 14px 16px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(21, 49, 59, 0.08);
  line-height: 1.72;
}

.message-item.user .message-bubble {
  background: linear-gradient(135deg, #0f766e, #146c94);
  border-color: transparent;
  color: #fff;
}

.message-bubble.loading {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 18px;
}

.typing {
  display: flex;
  gap: 6px;
}

.typing span {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #94a3b8;
  animation: typing 1.4s infinite;
}

.typing span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 60%, 100% {
    transform: translateY(0);
  }
  30% {
    transform: translateY(-10px);
  }
}

.text-content {
  line-height: 1.72;
}

.message-item.user .text-content {
  white-space: pre-wrap;
}

.user-message-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.message-image-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.message-image {
  width: 120px;
  height: 120px;
  border-radius: 12px;
  object-fit: cover;
  border: 1px solid rgba(255, 255, 255, 0.28);
  cursor: zoom-in;
}

.assistant-markdown :deep(p) {
  margin: 0 0 10px;
}

.assistant-markdown :deep(h1),
.assistant-markdown :deep(h2),
.assistant-markdown :deep(h3),
.assistant-markdown :deep(h4) {
  margin: 14px 0 8px;
  font-weight: 700;
  line-height: 1.35;
}

.assistant-markdown :deep(h1) {
  font-size: 22px;
}

.assistant-markdown :deep(h2) {
  font-size: 19px;
}

.assistant-markdown :deep(h3) {
  font-size: 16px;
}

.assistant-markdown :deep(a) {
  color: #0f766e;
  text-decoration: none;
}

.assistant-markdown :deep(a:hover) {
  text-decoration: underline;
}

.assistant-markdown :deep(code) {
  background: rgba(15, 118, 110, 0.08);
  padding: 2px 6px;
  border-radius: 6px;
  font-size: 12px;
}

.assistant-markdown :deep(pre) {
  background: #112128;
  color: #e7f3ef;
  padding: 12px 14px;
  border-radius: 12px;
  overflow: auto;
  margin: 10px 0;
}

.assistant-markdown :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
}

.assistant-markdown :deep(ul),
.assistant-markdown :deep(ol) {
  margin: 8px 0;
  padding-left: 20px;
}

.assistant-markdown :deep(blockquote) {
  margin: 10px 0;
  padding: 10px 14px;
  border-left: 3px solid rgba(15, 118, 110, 0.3);
  background: rgba(15, 118, 110, 0.06);
  color: #475569;
}

.assistant-markdown :deep(table) {
  display: block;
  width: max-content;
  max-width: 100%;
  overflow-x: auto;
  border-collapse: collapse;
  margin: 10px 0;
}

.assistant-markdown :deep(th),
.assistant-markdown :deep(td) {
  border: 1px solid #cbd5e1;
  padding: 6px 8px;
  text-align: left;
}

.references {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px dashed rgba(21, 49, 59, 0.12);
}

.ref-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 13px;
  font-weight: 700;
  color: #475569;
  margin-bottom: 8px;
}

.ref-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.72);
  border-radius: 12px;
  margin-bottom: 6px;
}

.references :deep(.el-button.is-link) {
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  min-height: 34px;
  border-radius: 14px !important;
  padding: 0 12px !important;
  background: rgba(15, 118, 110, 0.1) !important;
  border: 1px solid rgba(15, 118, 110, 0.12) !important;
  box-shadow: none !important;
  line-height: 1 !important;
  align-self: center;
}

.reference-action-btn {
  flex: 0 0 auto;
}

.references :deep(.reference-action-btn.el-button) {
  margin: 0 !important;
}

.references :deep(.el-button.is-link > span) {
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  line-height: 1 !important;
}

.ref-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  cursor: pointer;
}

.ref-file {
  color: #0f766e;
  font-weight: 700;
}

.ref-count,
.message-time {
  color: #64748b;
  font-size: 11px;
}

.chat-input-area {
  padding: 16px;
}

.input-wrapper {
  margin-bottom: 12px;
}

.hidden-file-input {
  display: none;
}

.selected-image-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
}

.selected-image-item {
  width: 120px;
  padding: 8px;
  border-radius: 12px;
  border: 1px solid rgba(21, 49, 59, 0.08);
  background: rgba(255, 255, 255, 0.72);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.selected-image-thumb {
  width: 100%;
  height: 88px;
  object-fit: cover;
  border-radius: 8px;
}

.selected-image-name {
  font-size: 12px;
  color: #475569;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.input-controls {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.markdown-header,
.graph-drawer-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.markdown-title,
.graph-drawer-title {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

.markdown-subtitle,
.graph-drawer-subtitle {
  font-size: 12px;
  color: #6b7280;
}

.markdown-scroll {
  padding-right: 8px;
}

.markdown-body {
  font-size: 14px;
  line-height: 1.78;
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

.markdown-body :deep(.anchor-mark) {
  background: #fde68a;
  padding: 0 2px;
  border-radius: 3px;
}

.markdown-preview {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.anchor-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  max-height: 180px;
  overflow-y: auto;
}

.anchor-item {
  font-size: 12px;
  color: #0f172a;
  cursor: pointer;
  padding: 6px 8px;
  border-radius: 6px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
}

.anchor-item:hover {
  border-color: rgba(15, 118, 110, 0.2);
  background: rgba(15, 118, 110, 0.08);
}

.anchor-item.disabled {
  color: #94a3b8;
  cursor: not-allowed;
  background: #f8fafc;
  border-color: #e2e8f0;
}

.graph-drawer-body {
  height: calc(100vh - 120px);
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

:deep(.el-radio-button__inner) {
  min-height: 40px;
  padding: 0 18px !important;
  border-radius: 999px !important;
  border: 1px solid rgba(21, 49, 59, 0.08);
  background: rgba(255, 255, 255, 0.72);
  color: #15313b;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  line-height: 1 !important;
  box-shadow: none !important;
}

:deep(.el-radio-button__inner > span) {
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  line-height: 1 !important;
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

.option-item :deep(.el-switch.is-checked .el-switch__core) {
  background: #0f766e !important;
  border-color: #0f766e !important;
}

:deep(.session-popover) {
  padding: 0 !important;
  border: none !important;
  border-radius: 18px !important;
  background: rgba(255, 252, 247, 0.98) !important;
  box-shadow: 0 14px 28px rgba(31, 49, 58, 0.1) !important;
  overflow: hidden;
}

:deep(.session-popover .el-popper__arrow),
:deep(.session-popover .el-popper__arrow::before) {
  display: none !important;
}

@media (max-width: 1100px) {
  .chat-top-bar,
  .chat-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .chat-options {
    margin-left: 0;
  }
}

@media (max-width: 768px) {
  .chat-page-wrapper {
    flex-direction: column;
  }

  .chat-sidebar {
    width: 100%;
    height: auto;
    max-height: 320px;
  }

  .chat-sidebar.collapsed {
    max-height: 0;
    overflow: hidden;
  }

  .message-content {
    max-width: 100%;
  }
}
</style>
