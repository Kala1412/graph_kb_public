<template>
  <div class="profile-page">
    <section class="hero-card">
      <div>
        <span class="eyebrow">Personal Hub</span>
        <h1>个人中心</h1>
        <p>维护账户资料、头像、安全设置与个人病状档案，让系统更好地理解你的长期医疗背景。</p>
        <div class="hero-tags">
          <span>{{ roleLabel }}</span>
          <span>完整度 {{ profileCompletion }}%</span>
          <span>病状记录 {{ medicalRecordCount }} 条</span>
          <span :class="{ warning: hasUnsavedChanges }">
            {{ hasUnsavedChanges ? '有未保存修改' : '资料已同步' }}
          </span>
        </div>
      </div>
      <div class="hero-orb" />
    </section>

    <el-row :gutter="20">
      <el-col :xs="24" :xl="8">
        <section class="panel accent-panel">
          <div class="identity">
            <div class="avatar-shell">
              <el-avatar :src="profileForm.avatar_url || defaultAvatar" :size="110" />
            </div>
            <div>
              <h2>{{ profileForm.username || '未设置用户名' }}</h2>
              <p>{{ profileForm.email || '建议补充邮箱，方便通知与找回' }}</p>
              <div class="hero-tags compact">
                <span>{{ roleLabel }}</span>
                <span>医疗问答系统用户</span>
              </div>
            </div>
          </div>

          <el-upload
            class="avatar-upload"
            :show-file-list="false"
            :http-request="handleAvatarUpload"
            :before-upload="beforeAvatarUpload"
            accept="image/jpeg,image/png,image/webp,image/gif"
          >
            <el-button class="rounded-btn" type="primary">
              <el-icon><UploadFilled /></el-icon>
              上传新头像
            </el-button>
          </el-upload>
          <p class="tip">支持 JPG / PNG / WEBP / GIF，大小不超过 5MB。</p>

          <div class="status-list">
            <div v-for="item in completionItems" :key="item.label" class="status-item" :class="{ done: item.done }">
              <el-icon><component :is="item.done ? CircleCheckFilled : WarningFilled" /></el-icon>
              <div>
                <strong>{{ item.label }}</strong>
                <span>{{ item.description }}</span>
              </div>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <span class="eyebrow">Overview</span>
              <h3>我的使用概览</h3>
            </div>
            <el-tag round effect="plain">{{ statsLoading ? '同步中' : '已更新' }}</el-tag>
          </div>
          <div class="metric-grid">
            <div v-for="item in overviewCards" :key="item.label" class="metric-card">
              <div class="metric-icon" :class="item.tone">
                <el-icon><component :is="item.icon" /></el-icon>
              </div>
              <div>
                <strong>{{ item.value }}</strong>
                <span>{{ item.label }}</span>
              </div>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <span class="eyebrow">Security</span>
              <h3>密码与账户安全</h3>
            </div>
            <el-button class="soft-btn toggle-btn" @click="togglePasswordPanel">
              {{ showPasswordPanel ? '收起面板' : '展开修改' }}
            </el-button>
          </div>

          <div class="security-banner">
            <div>
              <span class="eyebrow">Status</span>
              <strong>{{ passwordStrengthLabel }}</strong>
            </div>
            <p>系统不会展示当前密码明文。建议定期更新密码，避免与其他平台复用相同口令。</p>
          </div>

          <div v-if="!showPasswordPanel" class="placeholder">
            <el-icon><Lock /></el-icon>
            <span>点击右上角“展开修改”后可更新密码。</span>
          </div>

          <el-form
            v-else
            ref="passwordFormRef"
            :model="passwordForm"
            :rules="passwordRules"
            label-position="top"
          >
            <div class="form-grid">
              <el-form-item label="旧密码" prop="old_password">
                <el-input v-model="passwordForm.old_password" type="password" show-password size="large" />
              </el-form-item>
              <el-form-item label="新密码" prop="new_password">
                <el-input v-model="passwordForm.new_password" type="password" show-password size="large" />
              </el-form-item>
              <el-form-item label="确认新密码" prop="confirm_password" class="full-span">
                <el-input v-model="passwordForm.confirm_password" type="password" show-password size="large" />
              </el-form-item>
            </div>
            <div class="footer-bar">
              <div class="save-hint">
                <span class="dot" :class="{ changed: hasUnsavedPasswordChanges }" />
                {{ hasUnsavedPasswordChanges ? '已填写新的密码信息' : '暂无密码改动' }}
              </div>
              <el-button
                class="rounded-btn"
                type="primary"
                size="large"
                :loading="passwordSaving"
                :disabled="passwordSaving || !hasUnsavedPasswordChanges"
                @click="savePassword"
              >
                修改密码
              </el-button>
            </div>
          </el-form>
        </section>
      </el-col>

      <el-col :xs="24" :xl="16">
        <section class="panel">
          <div class="panel-head">
            <div>
              <span class="eyebrow">Profile</span>
              <h3>基础信息</h3>
            </div>
            <span class="tip-text">修改用户名后需要重新登录，邮箱可选但建议填写。</span>
          </div>

          <el-form ref="profileFormRef" :model="profileForm" :rules="profileRules" label-position="top">
            <div class="form-grid">
              <el-form-item label="用户名" prop="username">
                <el-input v-model="profileForm.username" size="large" placeholder="请输入用户名" />
              </el-form-item>
              <el-form-item label="邮箱" prop="email">
                <el-input v-model="profileForm.email" size="large" placeholder="请输入邮箱（可选）" />
              </el-form-item>
            </div>
            <div class="footer-bar">
              <div class="save-hint">
                <span class="dot" :class="{ changed: hasUnsavedProfileChanges }" />
                {{ hasUnsavedProfileChanges ? '基础信息有未保存修改' : '当前基础信息与服务器一致' }}
              </div>
              <el-button
                class="rounded-btn"
                type="primary"
                size="large"
                :loading="profileSaving"
                :disabled="profileSaving || !hasUnsavedProfileChanges"
                @click="saveProfile"
              >
                保存资料
              </el-button>
            </div>
          </el-form>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <span class="eyebrow">Medical Notes</span>
              <h3>个人病状信息</h3>
            </div>
            <div class="panel-actions">
              <el-button class="soft-btn" :loading="medicalLoading" @click="loadMedicalRecords">刷新</el-button>
              <el-button class="rounded-btn" type="primary" @click="openCreateMedicalDialog">
                <el-icon><Plus /></el-icon>
                新增记录
              </el-button>
            </div>
          </div>

          <div class="medical-banner">
            <div class="medical-summary">
              <span class="eyebrow">Snapshot</span>
              <strong>{{ medicalRecordCount }} 条长期记录</strong>
              <p>{{ latestMedicalSnippet }}</p>
            </div>
            <div class="medical-stats">
              <div v-for="item in medicalTypeCards" :key="item.value" class="stat-chip">
                <span>{{ item.label }}</span>
                <strong>{{ item.count }}</strong>
              </div>
            </div>
          </div>

          <div class="hero-tags compact source-row">
            <span>手动录入 {{ sourceStats.manual }}</span>
            <span>对话导入 {{ sourceStats.chat_import }}</span>
            <span>迁移记录 {{ sourceStats.migration }}</span>
          </div>

          <div v-loading="medicalLoading">
            <div v-if="!medicalLoading && !medicalRecords.length" class="empty-card">
              <span class="eyebrow">Medical</span>
              <h4>还没有病状档案</h4>
              <p>可以先补充过敏史、疾病、症状、既往史或长期用药，后续问答会更容易结合长期背景。</p>
              <el-button class="rounded-btn" type="primary" @click="openCreateMedicalDialog">立即添加</el-button>
            </div>

            <div v-else class="record-list">
              <article v-for="record in medicalRecords" :key="record.id" class="record-card">
                <div class="record-head">
                  <div class="hero-tags compact">
                    <span class="type-chip" :style="{ '--chip-color': typeMetaMap[record.record_type]?.tint || '#0f766e' }">
                      {{ typeMetaMap[record.record_type]?.label || '其他' }}
                    </span>
                    <span>{{ sourceLabelMap[record.source] || '手动录入' }}</span>
                  </div>
                  <div class="record-actions">
                    <el-button text @click="openEditMedicalDialog(record)">
                      <el-icon><EditPen /></el-icon>
                      编辑
                    </el-button>
                    <el-button text type="danger" @click="handleDeleteMedicalRecord(record)">
                      <el-icon><Delete /></el-icon>
                      删除
                    </el-button>
                  </div>
                </div>
                <p class="record-content">{{ record.content }}</p>
                <div class="record-foot">
                  <span>更新于 {{ formatDateTime(record.updated_at) }}</span>
                  <span>ID {{ record.id }}</span>
                </div>
              </article>
            </div>
          </div>
        </section>

      </el-col>
    </el-row>

    <el-dialog
      v-model="medicalDialogVisible"
      :title="medicalDialogMode === 'create' ? '新增病状记录' : '编辑病状记录'"
      width="620px"
      destroy-on-close
    >
      <el-form ref="medicalFormRef" :model="medicalForm" :rules="medicalRules" label-position="top">
        <div class="form-grid">
          <el-form-item label="分类" prop="record_type">
            <el-select v-model="medicalForm.record_type" size="large">
              <el-option v-for="item in medicalTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="来源" prop="source">
            <el-select v-model="medicalForm.source" size="large">
              <el-option v-for="item in medicalSourceOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="病状内容" prop="content">
          <el-input
            v-model="medicalForm.content"
            type="textarea"
            :rows="5"
            resize="none"
            placeholder="例如：青霉素过敏；近两周反复咳嗽；长期服用降压药。"
          />
          <div class="tip">建议一条记录描述一个明确事实，便于后续维护与检索。</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="medicalDialogVisible = false">取消</el-button>
          <el-button class="rounded-btn" type="primary" :loading="medicalSaving" @click="submitMedicalRecord">
            {{ medicalDialogMode === 'create' ? '保存记录' : '更新记录' }}
          </el-button>
        </div>
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
          <span class="eyebrow">Delete Record</span>
          <h4>删除这条病状信息？</h4>
          <p>删除后将无法恢复，这条长期病状档案会从当前个人资料中移除。</p>
          <div
            v-if="deletingRecord"
            class="delete-record-preview"
            :style="{ '--preview-accent': typeMetaMap[deletingRecord.record_type]?.tint || '#0f766e' }"
          >
            <div class="delete-record-meta">
              <span class="type-chip preview-chip">
                {{ typeMetaMap[deletingRecord.record_type]?.label || '其他' }}
              </span>
              <span>{{ sourceLabelMap[deletingRecord.source] || '手动录入' }}</span>
              <span>{{ formatDateTime(deletingRecord.updated_at) }}</span>
            </div>
            <div class="delete-record-text">{{ deletingRecord.content }}</div>
          </div>
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button class="ghost-btn" @click="closeDeleteDialog">取消</el-button>
          <el-button class="danger-btn" :loading="medicalDeleting" @click="confirmDeleteMedicalRecord">
            删除
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatDotRound, CircleCheckFilled, DataAnalysis, Delete, EditPen, FolderOpened, Lock, Message, Plus, UploadFilled, WarningFilled } from '@element-plus/icons-vue'
import { changeMyPassword, createMyMedicalProfileRecord, deleteMyMedicalProfileRecord, getDashboardStats, getMyProfile, listMyMedicalProfileRecords, updateMyMedicalProfileRecord, updateMyProfile, uploadMyAvatar } from '@/api/index'

const router = useRouter()
const profileFormRef = ref(null)
const passwordFormRef = ref(null)
const medicalFormRef = ref(null)
const profileSaving = ref(false)
const passwordSaving = ref(false)
const medicalSaving = ref(false)
const medicalDeleting = ref(false)
const showPasswordPanel = ref(false)
const statsLoading = ref(false)
const medicalLoading = ref(false)
const medicalDialogVisible = ref(false)
const medicalDialogMode = ref('create')
const deleteDialogVisible = ref(false)
const editingMedicalRecordId = ref(null)
const deletingRecord = ref(null)
const defaultAvatar = 'https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55bcpng.png'

const profileBaseline = ref({ username: '', email: '' })
const medicalRecords = ref([])
const dashboardCards = ref({ questions_7d: 0, total_kb: 0, total_sessions: 0, total_messages: 0 })
const profileForm = reactive({ username: '', email: '', avatar_url: '' })
const passwordForm = reactive({ old_password: '', new_password: '', confirm_password: '' })
const medicalForm = reactive({ record_type: 'symptom', source: 'manual', content: '' })

const medicalTypeOptions = [
  { value: 'allergy', label: '过敏史', tint: '#ef4444' },
  { value: 'disease', label: '疾病', tint: '#0f766e' },
  { value: 'symptom', label: '症状', tint: '#2563eb' },
  { value: 'history', label: '既往史', tint: '#7c3aed' },
  { value: 'constitution', label: '体质', tint: '#d97706' },
  { value: 'medication', label: '用药', tint: '#db2777' },
  { value: 'other', label: '其他', tint: '#475569' }
]
const medicalSourceOptions = [
  { value: 'manual', label: '手动录入' },
  { value: 'chat_import', label: '对话导入' },
  { value: 'migration', label: '历史迁移' }
]
const typeMetaMap = Object.fromEntries(medicalTypeOptions.map((item) => [item.value, item]))
const sourceLabelMap = Object.fromEntries(medicalSourceOptions.map((item) => [item.value, item.label]))

const showProfileToast = (message, type = 'success') => {
  ElMessage({
    message,
    type,
    customClass: `profile-toast profile-toast-${type}`,
    offset: 28,
    duration: 2200,
    showClose: false
  })
}

const normalizeProfile = (username, email) => ({ username: (username || '').trim(), email: (email || '').trim() })
const roleLabel = computed(() => (localStorage.getItem('role') === 'admin' ? '管理员账户' : '普通用户'))
const medicalRecordCount = computed(() => medicalRecords.value.length)
const sourceStats = computed(() => medicalRecords.value.reduce((acc, item) => ({ ...acc, [item.source]: (acc[item.source] || 0) + 1 }), { manual: 0, chat_import: 0, migration: 0 }))
const medicalTypeCards = computed(() => medicalTypeOptions.map((item) => ({ ...item, count: medicalRecords.value.filter((record) => record.record_type === item.value).length })))
const latestMedicalSnippet = computed(() => {
  if (!medicalRecords.value.length) return '暂未填写病状档案，新增后可统一在这里维护个人长期医疗背景。'
  const latest = medicalRecords.value[0]
  return `最近一条为“${typeMetaMap[latest.record_type]?.label || '其他'}”：${latest.content}`
})
const completionItems = computed(() => [
  { label: '头像设置', done: Boolean(profileForm.avatar_url), description: profileForm.avatar_url ? '已上传个性头像' : '建议上传头像提升辨识度' },
  { label: '用户名完善', done: Boolean(profileForm.username.trim()), description: profileForm.username ? '用户名已设置完成' : '用户名不能为空' },
  { label: '邮箱绑定', done: Boolean(profileForm.email.trim()), description: profileForm.email ? '已绑定常用邮箱' : '建议补充邮箱方便通知与恢复' },
  { label: '病状档案', done: medicalRecordCount.value > 0, description: medicalRecordCount.value ? `已维护 ${medicalRecordCount.value} 条长期病状记录` : '建议补充基础病状信息以提升问答上下文' }
])
const profileCompletion = computed(() => Math.round((completionItems.value.filter((item) => item.done).length / completionItems.value.length) * 100))
const overviewCards = computed(() => [
  { label: '近 7 天提问', value: dashboardCards.value.questions_7d, icon: DataAnalysis, tone: 'tone-blue' },
  { label: '知识库数量', value: dashboardCards.value.total_kb, icon: FolderOpened, tone: 'tone-amber' },
  { label: '会话数量', value: dashboardCards.value.total_sessions, icon: ChatDotRound, tone: 'tone-green' },
  { label: '消息总数', value: dashboardCards.value.total_messages, icon: Message, tone: 'tone-rose' }
])
const hasUnsavedProfileChanges = computed(() => {
  const current = normalizeProfile(profileForm.username, profileForm.email)
  return current.username !== profileBaseline.value.username || current.email !== profileBaseline.value.email
})
const hasUnsavedPasswordChanges = computed(() => Boolean(passwordForm.old_password || passwordForm.new_password || passwordForm.confirm_password))
const hasUnsavedChanges = computed(() => hasUnsavedProfileChanges.value || hasUnsavedPasswordChanges.value)
const passwordStrengthLabel = computed(() => {
  const length = passwordForm.new_password.length
  if (!length) return '稳定'
  if (length < 8) return '偏弱'
  return /^(?=.*[A-Za-z])(?=.*\d).+$/.test(passwordForm.new_password) ? '良好' : '一般'
})

const profileRules = {
  username: [{ required: true, message: '用户名不能为空', trigger: 'blur' }],
  email: [{ validator: (rule, value, callback) => (!value || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) ? callback() : callback(new Error('邮箱格式不正确'))), trigger: 'blur' }]
}
const passwordRules = {
  old_password: [{ required: true, message: '请输入旧密码', trigger: 'blur' }],
  new_password: [{ required: true, message: '请输入新密码', trigger: 'blur' }, { min: 6, message: '新密码至少 6 位', trigger: 'blur' }],
  confirm_password: [{ validator: (rule, value, callback) => (!value ? callback(new Error('请确认新密码')) : value !== passwordForm.new_password ? callback(new Error('两次密码不一致')) : callback()), trigger: 'blur' }]
}
const medicalRules = {
  record_type: [{ required: true, message: '请选择分类', trigger: 'change' }],
  source: [{ required: true, message: '请选择来源', trigger: 'change' }],
  content: [{ required: true, message: '请输入病状内容', trigger: 'blur' }, { min: 2, message: '内容至少 2 个字符', trigger: 'blur' }]
}

// 这里做了兜底处理：时间为空或无法解析时直接返回 '--'，避免页面出现 Invalid Date。
const formatDateTime = (value) => {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '--'
  const pad = (num) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}
// 每次新增病状记录前，把弹窗表单恢复到默认状态。
// 这样可以避免“上一次编辑的内容”残留到下一次新增流程里。
const resetMedicalForm = () => {
  medicalForm.record_type = 'symptom'
  medicalForm.source = 'manual'
  medicalForm.content = ''
  editingMedicalRecordId.value = null
  medicalFormRef.value?.clearValidate?.()
}

// 页面首次进入时会调用它，把用户名、邮箱、头像回填到表单中，
// 同时记录一份 baseline，用于后面判断用户是否真的改过内容。
const loadProfile = async () => {
  try {
    const { data } = await getMyProfile()
    profileForm.username = data.username || ''
    profileForm.email = data.email || ''
    profileForm.avatar_url = data.avatar_url || ''
    profileBaseline.value = normalizeProfile(profileForm.username, profileForm.email)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '获取个人信息失败')
  }
}
// 加载左侧“我的使用概览”统计卡片。
// 这里和 profile 分开请求，避免任意一个接口失败时把整页都卡住。
const loadStats = async () => {
  statsLoading.value = true
  try {
    const { data } = await getDashboardStats()
    dashboardCards.value = {
      questions_7d: data?.cards?.questions_7d || 0,
      total_kb: data?.cards?.total_kb || 0,
      total_sessions: data?.cards?.total_sessions || 0,
      total_messages: data?.cards?.total_messages || 0
    }
  } finally {
    statsLoading.value = false
  }
}
// 后端已经按更新时间倒序返回，所以这里拿到的数据可以直接用于展示“最近一条记录”。
const loadMedicalRecords = async () => {
  medicalLoading.value = true
  try {
    const { data } = await listMyMedicalProfileRecords({ skip: 0, limit: 100 })
    medicalRecords.value = Array.isArray(data?.items) ? data.items : []
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '获取病状档案失败')
  } finally {
    medicalLoading.value = false
  }
}
// 保存后更新 baseline；用户名变更时按后端要求重新登录。
const saveProfile = async () => {
  if (profileSaving.value || !hasUnsavedProfileChanges.value || !profileFormRef.value) return
  try {
    await profileFormRef.value.validate()
    profileSaving.value = true
    const { data } = await updateMyProfile({ username: profileForm.username, email: profileForm.email || null })
    profileForm.avatar_url = data?.user?.avatar_url || profileForm.avatar_url
    profileBaseline.value = normalizeProfile(profileForm.username, profileForm.email)
    showProfileToast('个人信息保存成功')
    if (data?.require_relogin) {
      ElMessage.warning('用户名已修改，请重新登录')
      localStorage.removeItem('token')
      localStorage.removeItem('refreshToken')
      localStorage.removeItem('role')
      router.push('/login')
    }
  } catch (err) {
    if (err) ElMessage.error(err?.response?.data?.detail || '保存失败')
  } finally {
    profileSaving.value = false
  }
}
// 提交成功后清空密码输入，避免敏感内容残留。
const savePassword = async () => {
  if (passwordSaving.value || !hasUnsavedPasswordChanges.value || !passwordFormRef.value) return
  try {
    await passwordFormRef.value.validate()
    passwordSaving.value = true
    await changeMyPassword({ old_password: passwordForm.old_password, new_password: passwordForm.new_password })
    showProfileToast('密码修改成功')
    passwordForm.old_password = ''
    passwordForm.new_password = ''
    passwordForm.confirm_password = ''
  } catch (err) {
    if (err) ElMessage.error(err?.response?.data?.detail || '修改密码失败')
  } finally {
    passwordSaving.value = false
  }
}
const openCreateMedicalDialog = async () => {
  medicalDialogMode.value = 'create'
  resetMedicalForm()
  medicalDialogVisible.value = true
  await nextTick()
}
const openEditMedicalDialog = async (record) => {
  medicalDialogMode.value = 'edit'
  editingMedicalRecordId.value = record.id
  medicalForm.record_type = record.record_type || 'symptom'
  medicalForm.source = record.source || 'manual'
  medicalForm.content = record.content || ''
  medicalDialogVisible.value = true
  await nextTick()
}
const submitMedicalRecord = async () => {
  if (medicalSaving.value || !medicalFormRef.value) return
  try {
    await medicalFormRef.value.validate()
    medicalSaving.value = true
    const payload = { record_type: medicalForm.record_type, source: medicalForm.source, content: medicalForm.content.trim() }
    if (medicalDialogMode.value === 'create') {
      await createMyMedicalProfileRecord(payload)
      showProfileToast('病状记录已新增')
    } else {
      await updateMyMedicalProfileRecord(editingMedicalRecordId.value, payload)
      showProfileToast('病状记录已更新')
    }
    medicalDialogVisible.value = false
    resetMedicalForm()
    await loadMedicalRecords()
  } catch (err) {
    if (err) ElMessage.error(err?.response?.data?.detail || '保存病状记录失败')
  } finally {
    medicalSaving.value = false
  }
}
const handleDeleteMedicalRecord = async (record) => {
  deletingRecord.value = record
  deleteDialogVisible.value = true
}
// 关闭删除确认弹窗。
// 删除请求发送过程中不允许关闭，避免用户在“请求进行中”反复点击导致状态混乱。
const closeDeleteDialog = (force = false) => {
  if (medicalDeleting.value && !force) return
  deleteDialogVisible.value = false
  deletingRecord.value = null
}
const confirmDeleteMedicalRecord = async () => {
  if (medicalDeleting.value || !deletingRecord.value?.id) return
  medicalDeleting.value = true
  try {
    await deleteMyMedicalProfileRecord(deletingRecord.value.id)
    closeDeleteDialog(true)
    await loadMedicalRecords()
    showProfileToast('病状记录已删除')
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '删除病状记录失败')
  } finally {
    medicalDeleting.value = false
  }
}
// 收起时顺手把密码输入框和校验状态全部清掉，防止旧密码停留在页面上。
const togglePasswordPanel = () => {
  showPasswordPanel.value = !showPasswordPanel.value
  if (!showPasswordPanel.value) {
    passwordForm.old_password = ''
    passwordForm.new_password = ''
    passwordForm.confirm_password = ''
    passwordFormRef.value?.clearValidate?.()
  }
}
const beforeAvatarUpload = (rawFile) => {
  const allowed = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
  if (!allowed.includes(rawFile.type)) return ElMessage.error('仅支持 JPG / PNG / WEBP / GIF 格式'), false
  if (rawFile.size > 5 * 1024 * 1024) return ElMessage.error('头像大小不能超过 5MB'), false
  return true
}
const handleAvatarUpload = async (options) => {
  const formData = new FormData()
  formData.append('file', options.file)
  try {
    const { data } = await uploadMyAvatar(formData)
    profileForm.avatar_url = data.avatar_url
    showProfileToast('头像上传成功')
    options.onSuccess?.(data)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '头像上传失败')
    options.onError?.(err)
  }
}
// 浏览器原生离开保护：
// 如果页面还有未保存的基础资料或密码修改内容，刷新 / 关页时给出提示。
const handleBeforeUnload = (event) => {
  if (!hasUnsavedChanges.value) return
  event.preventDefault()
  event.returnValue = ''
}

onBeforeRouteLeave((to, from, next) => {
  if (!hasUnsavedChanges.value) return next()
  ElMessageBox.confirm('你有未保存的修改，确定离开当前页面吗？', '离开确认', { confirmButtonText: '离开', cancelButtonText: '取消', type: 'warning' })
    .then(() => next())
    .catch(() => next(false))
})
onMounted(() => {
  window.addEventListener('beforeunload', handleBeforeUnload)
  loadProfile()
  loadStats()
  loadMedicalRecords()
})
onBeforeUnmount(() => window.removeEventListener('beforeunload', handleBeforeUnload))
</script>

<style scoped>
.profile-page { --ink:#15313b; --subtle:#6b7f86; --line:rgba(21,49,59,.1); --card:rgba(255,252,247,.92); --accent:#0f766e; color:var(--ink); padding:4px 0 24px; }
.hero-card,.panel { border:1px solid var(--line); border-radius:26px; background:var(--card); box-shadow:0 18px 40px rgba(31,49,58,.06); backdrop-filter:blur(12px); }
.hero-card { display:flex; justify-content:space-between; gap:20px; padding:28px; margin-bottom:20px; background:radial-gradient(circle at top right, rgba(15,118,110,.18), transparent 30%),linear-gradient(135deg,#fffaf2 0%,#f3ede2 52%,#ecf7f5 100%); }
.hero-card h1,.panel h3,.identity h2,.medical-summary strong,.security-banner strong,.empty-card h4 { margin:0; font-family:Georgia,'Times New Roman',serif; }
.hero-card h1 { font-size:clamp(30px,4vw,44px); }
.hero-card p,.identity p,.tip,.tip-text,.medical-summary p,.empty-card p,.record-foot,.security-banner p { color:var(--subtle); line-height:1.75; }
.eyebrow { display:inline-block; margin-bottom:10px; font-size:12px; font-weight:700; letter-spacing:.22em; text-transform:uppercase; color:var(--accent); }
.hero-tags { display:flex; flex-wrap:wrap; gap:10px; margin-top:18px; }
.hero-tags span,.el-tag,.type-chip { display:inline-flex; align-items:center; min-height:34px; padding:0 14px; border-radius:999px; border:1px solid rgba(21,49,59,.08); background:rgba(255,255,255,.75); font-size:13px; }
.hero-tags.compact { margin-top:12px; }
.hero-tags .warning { color:#b45309; background:rgba(255,248,235,.9); border-color:rgba(180,83,9,.2); }
.hero-orb { width:140px; height:140px; border-radius:34px; background:linear-gradient(145deg, rgba(255,255,255,.95), rgba(15,118,110,.08)), radial-gradient(circle at 30% 30%, rgba(15,118,110,.25), transparent 55%); transform:rotate(12deg); }
.panel { padding:24px; margin-bottom:20px; }
.accent-panel { background:linear-gradient(180deg, rgba(15,118,110,.08), rgba(255,252,247,.98) 34%),var(--card); }
.identity,.panel-head,.footer-bar,.record-head,.record-foot,.panel-actions,.dialog-footer,.security-banner { display:flex; align-items:flex-start; justify-content:space-between; gap:14px; }
.identity { align-items:center; }
.avatar-shell { display:grid; place-items:center; width:128px; height:128px; border-radius:34px; background:radial-gradient(circle at top, rgba(15,118,110,.18), rgba(15,118,110,.04) 55%, transparent 75%), rgba(255,255,255,.8); }
.identity h2 { font-size:30px; }
.avatar-upload { margin-top:20px; }
.rounded-btn { min-width:132px; border-radius:14px; }
.soft-btn,
.ghost-btn,
.danger-btn { border-radius:14px; min-width:108px; }
.soft-btn { border-color:rgba(21,49,59,.12); color:var(--ink); background:rgba(255,255,255,.92); box-shadow:none; }
.soft-btn:hover,
.soft-btn:focus { color:var(--accent); border-color:rgba(15,118,110,.22); background:rgba(240,253,250,.92); box-shadow:none; }
.toggle-btn { min-width:120px; }
.ghost-btn { border-color:rgba(21,49,59,.12); color:var(--ink); background:rgba(255,255,255,.92); }
.danger-btn { color:#fff; background:linear-gradient(135deg, #c2410c, #b91c1c); border-color:transparent; box-shadow:0 10px 24px rgba(185,28,28,.18); }
.danger-btn:hover,
.danger-btn:focus { color:#fff; border-color:transparent; background:linear-gradient(135deg, #b45309, #991b1b); box-shadow:0 12px 28px rgba(153,27,27,.24); }
.status-list,.record-list { display:grid; gap:12px; margin-top:18px; }
.status-item,.metric-card,.record-card,.empty-card,.medical-banner,.security-banner { border:1px solid rgba(21,49,59,.08); border-radius:20px; background:rgba(255,255,255,.8); }
.status-item { display:flex; gap:12px; padding:14px 16px; }
.status-item.done { background:rgba(240,253,250,.7); border-color:rgba(15,118,110,.18); }
.status-item .el-icon { margin-top:2px; color:#b45309; }
.status-item.done .el-icon { color:var(--accent); }
.status-item strong,.metric-card strong,.medical-summary strong { display:block; }
.status-item span,.metric-card span { font-size:13px; color:var(--subtle); }
.metric-grid,.medical-stats,.form-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }
.metric-card { display:flex; gap:14px; min-height:94px; padding:16px; }
.metric-icon { display:grid; place-items:center; width:48px; height:48px; border-radius:16px; font-size:20px; }
.tone-blue { color:#1d4ed8; background:rgba(59,130,246,.12); }
.tone-amber { color:#b45309; background:rgba(245,158,11,.14); }
.tone-green { color:#0f766e; background:rgba(16,185,129,.14); }
.tone-rose { color:#be185d; background:rgba(244,114,182,.14); }
.tip-text { max-width:280px; font-size:13px; text-align:right; }
.footer-bar { margin-top:8px; padding-top:12px; border-top:1px dashed rgba(21,49,59,.12); }
.save-hint { display:inline-flex; align-items:center; gap:10px; color:var(--subtle); font-size:13px; }
.dot { width:10px; height:10px; border-radius:999px; background:rgba(15,118,110,.24); }
.dot.changed { background:#f59e0b; box-shadow:0 0 0 6px rgba(245,158,11,.14); }
.medical-banner { display:grid; grid-template-columns:minmax(0,1.2fr) minmax(0,1fr); gap:16px; padding:18px; margin-bottom:14px; background:linear-gradient(135deg, rgba(255,255,255,.95), rgba(238,249,246,.95)); }
.medical-summary strong { font-size:30px; }
.stat-chip { padding:14px 16px; border-radius:16px; background:rgba(255,255,255,.85); }
.stat-chip span { display:block; font-size:12px; color:var(--subtle); }
.stat-chip strong { display:block; margin-top:8px; font-size:24px; }
.source-row { margin-bottom:16px; }
.empty-card { display:grid; gap:10px; justify-items:start; padding:26px; background:linear-gradient(135deg, rgba(255,252,247,.96), rgba(238,249,246,.78)); }
.record-card { position:relative; padding:18px 18px 18px 22px; background:linear-gradient(180deg, rgba(255,255,255,.96), rgba(250,246,240,.92)); overflow:hidden; }
.record-card::before { content:''; position:absolute; left:0; top:14px; bottom:14px; width:6px; border-radius:0 999px 999px 0; background:var(--chip-color, var(--accent)); box-shadow:0 0 0 1px color-mix(in srgb, var(--chip-color, var(--accent)) 16%, white); }
.record-head,.record-foot,.record-actions { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }
.type-chip { color:var(--chip-color); background:color-mix(in srgb, var(--chip-color) 12%, white); }
.record-content { margin:14px 0 16px; line-height:1.85; white-space:pre-wrap; word-break:break-word; }
.placeholder { display:flex; align-items:center; gap:12px; min-height:88px; color:var(--subtle); }
.placeholder .el-icon { font-size:22px; color:var(--accent); }
.delete-dialog-body { display:flex; align-items:flex-start; gap:18px; padding:8px 4px 4px; }
.delete-icon { display:grid; place-items:center; width:48px; height:48px; border-radius:18px; font-size:24px; font-weight:700; color:#b91c1c; background:linear-gradient(135deg, rgba(248,113,113,.18), rgba(251,191,36,.18)); box-shadow:inset 0 1px 0 rgba(255,255,255,.7); }
.delete-copy { flex:1; }
.delete-copy h4 { margin:2px 0 10px; font-size:28px; font-family:Georgia,'Times New Roman',serif; }
.delete-copy p { margin:0; color:var(--subtle); line-height:1.8; word-break:break-word; }
.delete-record-preview { margin-top:16px; padding:16px; border-radius:20px; border:1px solid color-mix(in srgb, var(--preview-accent) 18%, white); background:linear-gradient(180deg, color-mix(in srgb, var(--preview-accent) 8%, white), rgba(255,255,255,.92)); box-shadow:inset 0 1px 0 rgba(255,255,255,.78); }
.delete-record-meta { display:flex; align-items:center; gap:10px; flex-wrap:wrap; color:var(--subtle); font-size:12px; }
.preview-chip { color:var(--preview-accent); background:color-mix(in srgb, var(--preview-accent) 12%, white); }
.delete-record-text { margin-top:12px; padding:14px 16px; border-radius:16px; background:rgba(255,255,255,.82); line-height:1.8; word-break:break-word; }
.full-span { grid-column:1 / -1; }
:deep(.el-form-item__label) { font-size:13px; font-weight:700; color:var(--ink); }
:deep(.el-input__wrapper),:deep(.el-select__wrapper),:deep(.el-textarea__inner) { border-radius:14px; box-shadow:0 0 0 1px rgba(21,49,59,.08) inset; }
:deep(.el-input__wrapper),:deep(.el-select__wrapper) { min-height:46px; }
:deep(.el-textarea__inner) { min-height:132px; }
:deep(.el-input__wrapper.is-focus),:deep(.el-select__wrapper.is-focused),:deep(.el-textarea__inner:focus) { box-shadow:0 0 0 1px rgba(15,118,110,.28) inset,0 0 0 4px rgba(15,118,110,.08); }
:deep(.el-button--primary) { --el-button-bg-color:#0f766e; --el-button-border-color:#0f766e; --el-button-hover-bg-color:#0d655e; --el-button-hover-border-color:#0d655e; }
:deep(.soft-btn.el-button:hover),
:deep(.soft-btn.el-button:focus),
:deep(.soft-btn.el-button:active) { box-shadow:none; }
:deep(.delete-dialog .el-overlay-dialog) { animation:dialog-fade-in .28s cubic-bezier(.2,.8,.2,1); }
:deep(.delete-dialog .el-dialog) { border-radius:28px; overflow:hidden; background:linear-gradient(180deg, rgba(255,252,247,.98), rgba(255,248,240,.98)); box-shadow:0 28px 80px rgba(31,49,58,.2); transform-origin:center; animation:dialog-pop-in .3s cubic-bezier(.2,.8,.2,1); }
:deep(.delete-dialog .el-dialog__header) { display:none; }
:deep(.delete-dialog .el-dialog__body) { padding:28px 28px 8px; }
:deep(.delete-dialog .el-dialog__footer) { padding:0 28px 26px; }
:deep(.profile-toast) { min-width:260px; padding:14px 16px; border:none; border-radius:18px; background:linear-gradient(180deg, rgba(255,252,247,.98), rgba(246,241,232,.96)); box-shadow:0 18px 44px rgba(31,49,58,.14); color:var(--ink); }
:deep(.profile-toast .el-message__content) { color:var(--ink); font-weight:600; letter-spacing:.01em; }
:deep(.profile-toast .el-message__icon) { color:var(--accent); }
:deep(.profile-toast-success .el-message__icon) { color:#0f766e; }
:deep(.profile-toast-error .el-message__icon) { color:#b91c1c; }
@keyframes dialog-fade-in { from { opacity:0; } to { opacity:1; } }
@keyframes dialog-pop-in { from { opacity:0; transform:translateY(18px) scale(.96); filter:blur(4px); } to { opacity:1; transform:translateY(0) scale(1); filter:blur(0); } }
@media (max-width: 900px) { .hero-card,.identity,.panel-head,.footer-bar,.security-banner,.panel-actions,.record-head,.record-foot { flex-direction:column; align-items:flex-start; } .hero-orb { display:none; } .metric-grid,.medical-stats,.form-grid,.medical-banner { grid-template-columns:1fr; } .tip-text { max-width:none; text-align:left; } }
@media (max-width: 600px) { .hero-card,.panel { border-radius:22px; } .avatar-shell { width:112px; height:112px; border-radius:28px; } .identity h2,.panel h3,.medical-summary strong { font-size:24px; } }
</style>
