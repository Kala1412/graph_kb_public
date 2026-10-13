<template>
  <div class="kb-page">
    <section class="kb-hero">
      <div class="hero-copy">
        <span class="hero-kicker">Knowledge Base</span>
        <h1>文档知识库</h1>
        <p>
          将医学文献、指南、病例文档与研究材料整理为可检索、可问答、可查看关联关系的知识库。
        </p>
        <div class="hero-tags">
          <span class="hero-tag">{{ isAdmin ? '管理员模式' : '个人资料库' }}</span>
          <span class="hero-tag">{{ totalFiles }} 份文档</span>
          <span class="hero-tag accent">{{ kbs.length }} 个知识库</span>
        </div>
      </div>
      <div class="hero-actions">
        <el-button class="primary-btn" type="primary" size="large" @click="openCreate">
          新建知识库
        </el-button>
      </div>
    </section>

    <section class="summary-grid">
      <article class="summary-card">
        <span>知识库总数</span>
        <strong>{{ kbs.length }}</strong>
        <p>展示当前已沉淀的知识主题规模。</p>
      </article>
      <article class="summary-card">
        <span>文档总量</span>
        <strong>{{ totalFiles }}</strong>
        <p>按各知识库 `file_count` 估算的文档总量。</p>
      </article>
      <article class="summary-card">
        <span>平均文档数</span>
        <strong>{{ averageFiles }}</strong>
        <p>帮助你快速判断每个知识库是否过于稀疏。</p>
      </article>
    </section>

    <section v-if="kbs.length > 0" class="kb-grid">
      <article v-for="kb in kbs" :key="kb.id" class="kb-card" @click="openKb(kb)">
        <div class="card-top">
          <div>
            <span class="card-kicker">KB-{{ kb.id }}</span>
            <h2>{{ kb.name }}</h2>
          </div>
          <span class="file-pill">{{ kb.file_count || 0 }} 文件</span>
        </div>

        <p class="card-desc">{{ kb.description || '这个知识库暂未填写描述，可点击进入继续完善。' }}</p>

        <div class="card-meta">
          <div class="meta-item">
            <span>{{ isAdmin ? '创建者' : '归属' }}</span>
            <strong>{{ getCreatorName(kb) }}</strong>
          </div>
          <div class="meta-item">
            <span>知识状态</span>
            <strong>{{ getKnowledgeStatus(kb) }}</strong>
          </div>
        </div>

        <div class="card-tags">
          <el-tag
            v-for="tag in getKnowledgeTags(kb)"
            :key="tag"
            effect="plain"
            round
          >
            {{ tag }}
          </el-tag>
        </div>

        <div class="card-actions" @click.stop>
          <el-button class="secondary-btn" @click="openKb(kb)">进入详情</el-button>
          <el-button
            class="danger-btn"
            :loading="deletingKbId === kb.id"
            @click="deleteKb(kb)"
          >
            删除
          </el-button>
        </div>
      </article>
    </section>

    <section v-else class="empty-panel">
      <el-empty description="暂无知识库，点击上方按钮开始创建" />
    </section>

    <el-dialog v-model="createVisible" title="新建知识库" width="520px" append-to-body>
      <div class="dialog-copy">
        <span class="dialog-kicker">Create New</span>
        <h3>创建一个新的知识容器</h3>
        <p>建议按文档主题、疾病类型或研究方向拆分，后续检索体验会更清晰。</p>
      </div>

      <el-form :model="form" label-position="top" class="create-form">
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="例如：糖尿病诊疗指南库" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="4"
            placeholder="补充这个知识库的来源、用途或适用场景"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button class="secondary-btn" @click="createVisible = false">取消</el-button>
        <el-button class="primary-btn" type="primary" @click="createKb">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api, { getMyProfile } from '@/api/index'
import { useRouter } from 'vue-router'

const router = useRouter()
const kbs = ref([])
const createVisible = ref(false)
const form = ref({ name: '', description: '' })
const deletingKbId = ref(null)
const currentUsername = ref('')
const isAdmin = computed(() => localStorage.getItem('role') === 'admin')

const totalFiles = computed(() =>
  kbs.value.reduce((sum, kb) => sum + Number(kb.file_count || 0), 0)
)

const averageFiles = computed(() => {
  if (!kbs.value.length) return 0
  return Math.round(totalFiles.value / kbs.value.length)
})

const getCreatorName = (kb) => {
  if (kb?.creator?.username || kb?.owner_name) {
    return kb?.creator?.username || kb?.owner_name
  }

  if (!isAdmin.value) {
    return currentUsername.value || '我'
  }

  return kb?.creator?.id || kb?.owner_id || '-'
}

const getKnowledgeStatus = (kb) => {
  const fileCount = Number(kb?.file_count || 0)
  if (fileCount <= 0) return '待导入文档'
  return '已接入文档'
}

const getKnowledgeTags = (kb) => {
  if (Array.isArray(kb?.tags) && kb.tags.length > 0) {
    return kb.tags
  }

  const fileCount = Number(kb?.file_count || 0)
  if (fileCount <= 0) return ['医疗知识', '待构建']
  return ['医疗知识', '知识库']
}

const loadKbs = async () => {
  try {
    const res = await api.get('/knowledge/list').catch(() => null)
    if (res && res.data) {
      kbs.value = res.data
    }
  } catch (err) {
    console.error('加载知识库失败', err)
    ElMessage.error('获取知识库列表失败，请检查登录状态')
  }
}

const loadCurrentUser = async () => {
  if (isAdmin.value) return

  try {
    const { data } = await getMyProfile()
    currentUsername.value = data?.username || ''
  } catch (err) {
    console.warn('加载当前用户信息失败', err)
  }
}

const openCreate = () => {
  createVisible.value = true
}

const createKb = async () => {
  if (!form.value.name || form.value.name.trim() === '') {
    return ElMessage.warning('请填写知识库名称')
  }

  try {
    const params = new URLSearchParams()
    params.append('name', form.value.name.trim())
    params.append('description', form.value.description || '')

    const res = await api.post('/knowledge/create', params)

    if (res && res.data && res.data.status === 'success') {
      ElMessage.success('创建成功')
      createVisible.value = false
      form.value.name = ''
      form.value.description = ''
      await loadKbs()
      return
    }

    const msg = res?.data?.message || '创建失败'
    ElMessage.error(msg)
  } catch (err) {
    console.error('创建知识库异常', err)
    const msg = err?.response?.data?.detail || err?.response?.data || err.message || '创建失败'
    ElMessage.error(msg)
  }
}

const openKb = (kb) => {
  router.push(`/knowledge/${kb.id}`)
}

const deleteKb = async (kb) => {
  try {
    await ElMessageBox.confirm(
      `确认删除知识库“${kb.name}”吗？该操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
        customClass: 'kb-delete-message-box',
        confirmButtonClass: 'kb-delete-confirm-btn',
        cancelButtonClass: 'kb-delete-cancel-btn',
      }
    )

    deletingKbId.value = kb.id
    await api.delete(`/knowledge/delete/${kb.id}`)
    ElMessage.success('知识库已删除')
    await loadKbs()
  } catch (err) {
    if (err === 'cancel') return
    const msg = err?.response?.data?.detail || err?.response?.data || err.message || '删除失败'
    ElMessage.error(msg)
  } finally {
    if (deletingKbId.value === kb.id) {
      deletingKbId.value = null
    }
  }
}

onMounted(() => {
  loadCurrentUser()
  loadKbs()
})
</script>

<style scoped>
.kb-page {
  --kb-ink: #15313b;
  --kb-subtle: #6b7f86;
  --kb-line: rgba(21, 49, 59, 0.1);
  --kb-card: rgba(255, 252, 247, 0.94);
  --kb-accent: #0f766e;
  min-height: 100%;
  padding: 4px 0 24px;
  color: var(--kb-ink);
}

.kb-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 20px;
  padding: 28px;
  border-radius: 30px;
  border: 1px solid var(--kb-line);
  background:
    radial-gradient(circle at top right, rgba(15, 118, 110, 0.16), transparent 28%),
    linear-gradient(135deg, #fffaf2 0%, #f3ede2 52%, #edf7f5 100%);
  box-shadow: 0 24px 48px rgba(33, 52, 61, 0.08);
}

.hero-kicker,
.dialog-kicker,
.card-kicker {
  display: inline-block;
  margin-bottom: 10px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--kb-accent);
}

.kb-hero h1,
.kb-card h2,
.dialog-copy h3 {
  margin: 0;
  font-family: Georgia, 'Times New Roman', serif;
}

.kb-hero h1 {
  font-size: clamp(30px, 4vw, 44px);
  line-height: 1.05;
}

.kb-hero p,
.dialog-copy p,
.summary-card p,
.card-desc {
  margin: 12px 0 0;
  line-height: 1.8;
  color: var(--kb-subtle);
}

.hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 20px;
}

.hero-tag {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 14px;
  border-radius: 999px;
  border: 1px solid rgba(21, 49, 59, 0.08);
  background: rgba(255, 255, 255, 0.72);
  font-size: 13px;
}

.hero-tag.accent {
  color: var(--kb-accent);
  background: rgba(15, 118, 110, 0.12);
  border-color: transparent;
}

.primary-btn {
  min-width: 132px;
  border-radius: 14px;
}

.secondary-btn,
.danger-btn {
  min-width: 108px;
  border-radius: 14px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.summary-card,
.kb-card,
.empty-panel {
  border-radius: 24px;
  border: 1px solid var(--kb-line);
  background: var(--kb-card);
  box-shadow: 0 18px 40px rgba(31, 49, 58, 0.06);
}

.summary-card {
  padding: 18px 20px;
}

.summary-card span {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--kb-subtle);
}

.summary-card strong {
  display: block;
  margin-top: 10px;
  font-size: 38px;
  line-height: 1;
  font-family: Georgia, 'Times New Roman', serif;
}

.kb-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 18px;
}

.kb-card {
  display: flex;
  flex-direction: column;
  min-height: 280px;
  padding: 20px;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.kb-card:hover {
  transform: translateY(-6px);
  border-color: rgba(15, 118, 110, 0.18);
  box-shadow: 0 26px 48px rgba(15, 118, 110, 0.1);
}

.card-top {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.kb-card h2 {
  font-size: 26px;
  line-height: 1.15;
}

.file-pill {
  display: inline-flex;
  align-items: center;
  height: 34px;
  padding: 0 14px;
  border-radius: 999px;
  background: rgba(15, 118, 110, 0.1);
  color: var(--kb-accent);
  font-size: 13px;
  white-space: nowrap;
}

.card-desc {
  min-height: 88px;
}

.card-meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: auto;
  padding-top: 14px;
}

.meta-item {
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.74);
  border: 1px solid rgba(21, 49, 59, 0.08);
}

.meta-item span {
  display: block;
  color: var(--kb-subtle);
  font-size: 12px;
}

.meta-item strong {
  display: block;
  margin-top: 6px;
  word-break: break-word;
  color: var(--kb-ink);
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.card-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid rgba(21, 49, 59, 0.08);
}

.card-actions :deep(.el-button) {
  margin: 0;
  min-height: 40px;
  padding: 0 18px;
  border-radius: 999px;
}

.secondary-btn :deep(span),
.danger-btn :deep(span),
.primary-btn :deep(span) {
  font-weight: 600;
}

.secondary-btn {
  border-color: rgba(21, 49, 59, 0.12);
  background: rgba(255, 255, 255, 0.84);
  color: var(--kb-ink);
}

.secondary-btn:hover,
.secondary-btn:focus {
  border-color: rgba(15, 118, 110, 0.24);
  background: rgba(15, 118, 110, 0.08);
  color: var(--kb-accent);
}

.danger-btn {
  border-color: rgba(191, 71, 73, 0.16);
  background: rgba(255, 245, 245, 0.95);
  color: #b42318;
}

.danger-btn:hover,
.danger-btn:focus {
  border-color: rgba(191, 71, 73, 0.28);
  background: rgba(254, 236, 236, 1);
  color: #912018;
}

.card-tags :deep(.el-tag) {
  border-color: rgba(15, 118, 110, 0.3) !important;
  background: rgba(255, 255, 255, 0.78) !important;
  color: var(--kb-accent) !important;
}

.card-tags :deep(.el-tag__content) {
  color: var(--kb-accent) !important;
  font-weight: 600;
}

.empty-panel {
  padding: 40px 20px;
}

.dialog-copy {
  margin-bottom: 16px;
}

.create-form :deep(.el-textarea__inner),
.create-form :deep(.el-input__wrapper) {
  border-radius: 14px;
}

:deep(.el-button--primary) {
  --el-button-bg-color: #0f766e;
  --el-button-border-color: #0f766e;
  --el-button-hover-bg-color: #0d655e;
  --el-button-hover-border-color: #0d655e;
}

@media (max-width: 1300px) {
  .kb-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1024px) {
  .kb-hero,
  .card-top {
    flex-direction: column;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }

  .kb-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 700px) {
  .kb-hero,
  .summary-card,
  .kb-card {
    border-radius: 22px;
  }

  .kb-grid,
  .card-meta {
    grid-template-columns: 1fr;
  }
}
:global(.kb-delete-message-box) {
  border-radius: 28px;
  border: 1px solid rgba(21, 49, 59, 0.1);
  background:
    radial-gradient(circle at top right, rgba(15, 118, 110, 0.1), transparent 28%),
    linear-gradient(135deg, #fffaf2 0%, #f6efe4 56%, #eff8f6 100%);
  box-shadow: 0 28px 56px rgba(31, 49, 58, 0.16);
  overflow: hidden;
}

:global(.kb-delete-message-box .el-message-box__header) {
  padding: 24px 24px 8px;
}

:global(.kb-delete-message-box .el-message-box__title) {
  font-family: Georgia, 'Times New Roman', serif;
  font-size: 24px;
  color: #15313b;
}

:global(.kb-delete-message-box .el-message-box__content) {
  padding: 8px 24px 18px;
}

:global(.kb-delete-message-box .el-message-box__message) {
  color: #5f737a;
  font-size: 14px;
  line-height: 1.8;
}

:global(.kb-delete-message-box .el-message-box__status) {
  color: #b42318 !important;
}

:global(.kb-delete-message-box .el-message-box__btns) {
  padding: 0 24px 24px;
  gap: 12px;
}

:global(.kb-delete-message-box .el-message-box__btns .el-button) {
  min-width: 108px;
  min-height: 42px;
  margin-left: 0;
  border-radius: 999px;
  font-weight: 600;
}

:global(.kb-delete-message-box .kb-delete-cancel-btn) {
  border-color: rgba(21, 49, 59, 0.12);
  background: rgba(255, 255, 255, 0.86);
  color: #15313b;
}

:global(.kb-delete-message-box .kb-delete-cancel-btn:hover),
:global(.kb-delete-message-box .kb-delete-cancel-btn:focus) {
  border-color: rgba(15, 118, 110, 0.24);
  background: rgba(15, 118, 110, 0.08);
  color: #0f766e;
}

:global(.kb-delete-message-box .kb-delete-confirm-btn) {
  border-color: rgba(180, 35, 24, 0.9);
  background: #b42318;
  color: #fff;
}

:global(.kb-delete-message-box .kb-delete-confirm-btn:hover),
:global(.kb-delete-message-box .kb-delete-confirm-btn:focus) {
  border-color: #912018;
  background: #912018;
  color: #fff;
}
</style>
