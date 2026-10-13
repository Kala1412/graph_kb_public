<template>
  <div class="forum-page">
    <section class="forum-hero">
      <div class="hero-copy">
        <span class="eyebrow">Forum Commons</span>
        <h1>围绕知识内容展开持续讨论</h1>
        <p>
          在这里分享临床思路、补充知识库细节、交流案例理解。帖子支持分类、评论与点赞，便于把零散经验沉淀成可复用的社区知识。
        </p>
      </div>
      <div class="hero-actions">
        <div class="stat-card">
          <strong>{{ total }}</strong>
          <span>当前帖子</span>
        </div>
        <div class="stat-card">
          <strong>{{ categories.length }}</strong>
          <span>讨论分类</span>
        </div>
        <el-button class="publish-btn" size="large" @click="openComposer">发布帖子</el-button>
      </div>
    </section>

    <section class="forum-toolbar">
      <div class="toolbar-main">
        <el-select v-model="filters.categoryId" clearable placeholder="全部分类" size="large" @change="handleFilterChange">
          <el-option v-for="item in categories" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
        <el-input
          v-model="filters.keyword"
          size="large"
          placeholder="搜索标题或正文"
          clearable
          @keyup.enter="handleFilterChange"
          @clear="handleFilterChange"
        >
          <template #append>
            <el-button @click="handleFilterChange">搜索</el-button>
          </template>
        </el-input>
      </div>
      <div class="toolbar-side">
        <el-radio-group v-model="filters.sortBy" size="large" @change="handleFilterChange">
          <el-radio-button label="latest">最新</el-radio-button>
          <el-radio-button label="hot">最热</el-radio-button>
        </el-radio-group>
      </div>
    </section>

    <section class="category-strip">
      <button class="category-pill" :class="{ active: !filters.categoryId }" @click="chooseCategory(null)">全部</button>
      <button
        v-for="item in categories"
        :key="item.id"
        class="category-pill"
        :class="{ active: filters.categoryId === item.id }"
        @click="chooseCategory(item.id)"
      >
        {{ item.name }}
      </button>
    </section>

    <section class="post-grid" v-loading="loading">
      <article v-for="post in posts" :key="post.id" class="post-card">
        <div class="post-meta">
          <el-tag effect="plain" round>{{ post.category.name }}</el-tag>
          <span>{{ formatDate(post.created_at) }}</span>
        </div>
        <div class="post-body" @click="openPost(post.id)">
          <h3>{{ post.title }}</h3>
          <p>{{ excerpt(post.content) }}</p>
        </div>
        <div class="post-footer">
          <div class="author-block">
            <el-avatar :src="post.author.avatar_url" :size="38">{{ post.author.username?.slice(0, 1) }}</el-avatar>
            <div>
              <strong>{{ post.author.username }}</strong>
              <span>{{ post.comment_count }} 条评论 · {{ post.view_count }} 次浏览</span>
            </div>
          </div>
          <el-button class="like-btn" :type="post.liked_by_me ? 'primary' : 'default'" plain @click.stop="toggleLike(post)">
            👍 {{ post.like_count }}
          </el-button>
        </div>
      </article>

      <el-empty v-if="!loading && posts.length === 0" description="当前筛选下还没有帖子，试试先发布一篇讨论。" />
    </section>

    <section class="pager-shell" v-if="total > pagination.pageSize">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        layout="prev, pager, next"
        :total="total"
        @current-change="loadPosts"
      />
    </section>

    <el-dialog v-model="composerVisible" title="发布讨论" width="720px" @closed="resetComposer">
      <el-form ref="composerRef" :model="composer" :rules="composerRules" label-position="top">
        <el-form-item label="分类" prop="category_id">
          <el-select v-model="composer.category_id" placeholder="选择一个讨论分类" size="large">
            <el-option v-for="item in categories" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题" prop="title">
          <el-input v-model="composer.title" maxlength="200" show-word-limit size="large" placeholder="用一句清晰的话概括你的讨论主题" />
        </el-form-item>
        <el-form-item label="内容" prop="content">
          <el-input
            v-model="composer.content"
            type="textarea"
            :rows="10"
            maxlength="4000"
            show-word-limit
            placeholder="描述你的问题、观察或经验。支持轻量 Markdown 文本。"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="composerVisible = false">取消</el-button>
        <el-button type="primary" :loading="publishing" @click="submitPost">发布</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createForumPost, fetchForumCategories, fetchForumPosts, likeForumPost, unlikeForumPost } from '@/api/index'

const router = useRouter()
const loading = ref(false)
const publishing = ref(false)
const composerVisible = ref(false)
const composerRef = ref(null)
const categories = ref([])
const posts = ref([])
const total = ref(0)
const filters = reactive({ categoryId: null, keyword: '', sortBy: 'latest' })
const pagination = reactive({ page: 1, pageSize: 10 })
const composer = reactive({ category_id: null, title: '', content: '' })

const composerRules = {
  // 这里的校验只是前端第一层提示，真正的兜底仍由后端接口负责。
  category_id: [{ required: true, message: '请选择分类', trigger: 'change' }],
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  content: [{ required: true, message: '请输入内容', trigger: 'blur' }],
}

const formatDate = (value) =>
  new Date(value).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })

const excerpt = (content) => {
  const compact = String(content || '').replace(/\s+/g, ' ').trim()
  return compact.length > 120 ? `${compact.slice(0, 120)}...` : compact
}

const loadCategories = async () => {
  const { data } = await fetchForumCategories()
  categories.value = data.items || []
  if (!composer.category_id && categories.value.length) composer.category_id = categories.value[0].id
}

const loadPosts = async () => {
  loading.value = true
  try {
    const { data } = await fetchForumPosts({
      category_id: filters.categoryId || undefined,
      keyword: filters.keyword || undefined,
      sort_by: filters.sortBy,
      page: pagination.page,
      page_size: pagination.pageSize,
    })
    posts.value = data.items || []
    total.value = data.total || 0
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '加载帖子失败')
  } finally {
    loading.value = false
  }
}

const handleFilterChange = () => {
  // 一旦筛选条件变化，就把分页重置到第一页，避免出现“旧页码超出结果集”的空列表错觉。
  pagination.page = 1
  loadPosts()
}

const chooseCategory = (categoryId) => {
  filters.categoryId = categoryId
  handleFilterChange()
}

const openComposer = () => {
  composerVisible.value = true
}

const resetComposer = () => {
  // 关闭弹窗后主动复位，防止下次打开还残留上一次输入。
  composer.category_id = categories.value[0]?.id || null
  composer.title = ''
  composer.content = ''
  composerRef.value?.clearValidate?.()
}

const submitPost = async () => {
  // Element Plus validate 失败会 reject，这里统一转成 false，便于顺序控制。
  const valid = await composerRef.value?.validate().catch(() => false)
  if (!valid) return
  publishing.value = true
  try {
    const { data } = await createForumPost(composer)
    ElMessage.success('帖子已发布')
    composerVisible.value = false
    router.push(`/forum/${data.id}`)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '发布失败')
  } finally {
    publishing.value = false
  }
}

const openPost = (postId) => {
  router.push(`/forum/${postId}`)
}

const toggleLike = async (post) => {
  // 这里用了“乐观更新”：
  // 1. 先本地切换 liked_by_me / like_count，让按钮响应更快；
  // 2. 如果接口失败，再回滚到旧值。
  const originalLiked = post.liked_by_me
  const originalCount = post.like_count
  post.liked_by_me = !originalLiked
  post.like_count += originalLiked ? -1 : 1
  try {
    if (originalLiked) await unlikeForumPost(post.id)
    else await likeForumPost(post.id)
  } catch (error) {
    post.liked_by_me = originalLiked
    post.like_count = originalCount
    ElMessage.error(error?.response?.data?.detail || '操作失败')
  }
}

onMounted(async () => {
  await loadCategories()
  await loadPosts()
})
</script>

<style scoped>
.forum-page {
  --forum-ink: #163947;
  --forum-subtle: #68808a;
  --forum-line: rgba(22, 57, 71, 0.12);
  --forum-card: rgba(255, 252, 247, 0.92);
  display: grid;
  gap: 18px;
}

.forum-hero,
.forum-toolbar,
.post-card,
.pager-shell,
.category-strip {
  border: 1px solid var(--forum-line);
  background: var(--forum-card);
  box-shadow: 0 18px 42px rgba(24, 54, 66, 0.07);
}

.forum-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(280px, 0.9fr);
  gap: 24px;
  padding: 28px 30px;
  border-radius: 34px;
  background: radial-gradient(circle at top left, rgba(15, 118, 110, 0.12), transparent 34%), linear-gradient(180deg, rgba(255, 249, 242, 0.96), rgba(247, 251, 248, 0.96));
}

.eyebrow {
  display: inline-flex;
  margin-bottom: 14px;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #0f766e;
  background: rgba(255, 255, 255, 0.78);
}

.hero-copy h1 {
  margin: 0;
  font-family: Georgia, 'Times New Roman', serif;
  font-size: clamp(34px, 4vw, 46px);
  line-height: 1.08;
  color: var(--forum-ink);
}

.hero-copy p {
  margin: 14px 0 0;
  color: var(--forum-subtle);
  line-height: 1.8;
}

.hero-actions {
  display: grid;
  gap: 14px;
  align-content: start;
}

.stat-card {
  display: grid;
  gap: 4px;
  padding: 20px 22px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.72);
}

.stat-card strong {
  font-size: 28px;
  color: var(--forum-ink);
}

.stat-card span {
  color: var(--forum-subtle);
}

.publish-btn {
  min-height: 54px;
  border: none;
  border-radius: 20px;
  color: #f8fffd;
  font-weight: 700;
  letter-spacing: 0.04em;
  background: linear-gradient(135deg, #0f766e, #176b8a);
  box-shadow: 0 16px 28px rgba(15, 118, 110, 0.22);
}

.publish-btn:hover,
.publish-btn:focus-visible {
  color: #f8fffd;
  background: linear-gradient(135deg, #126f68, #1a6782);
}

.forum-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  border-radius: 28px;
}

.toolbar-main {
  display: grid;
  grid-template-columns: 220px minmax(280px, 1fr);
  gap: 12px;
  flex: 1;
}

.toolbar-side {
  display: flex;
  align-items: center;
}

.category-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 16px 18px;
  border-radius: 24px;
}

.category-pill {
  border: none;
  border-radius: 999px;
  padding: 10px 16px;
  color: var(--forum-subtle);
  background: rgba(255, 255, 255, 0.84);
  cursor: pointer;
}

.category-pill.active,
.category-pill:hover {
  color: #fff;
  background: linear-gradient(135deg, #0f766e, #146c94);
}

.post-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 18px;
}

.post-card {
  display: grid;
  gap: 16px;
  padding: 22px;
  border-radius: 28px;
}

.post-meta,
.post-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.post-meta span,
.author-block span {
  color: var(--forum-subtle);
  font-size: 13px;
}

.post-meta :deep(.el-tag) {
  border: none;
  color: #0f766e;
  background: rgba(15, 118, 110, 0.1);
}

.post-body {
  cursor: pointer;
}

.post-body h3 {
  margin: 0 0 12px;
  font-size: 22px;
  color: var(--forum-ink);
}

.post-body p {
  margin: 0;
  color: #516972;
  line-height: 1.8;
}

.author-block {
  display: flex;
  align-items: center;
  gap: 12px;
}

.author-block strong {
  display: block;
  margin-bottom: 4px;
  color: var(--forum-ink);
}

.like-btn {
  min-width: 94px;
  border-radius: 999px;
  border: 1px solid rgba(15, 118, 110, 0.12);
  color: #56717a;
  background: rgba(255, 255, 255, 0.82);
  transition: all 0.2s ease;
}

.like-btn:hover,
.like-btn:focus-visible {
  color: #0f766e;
  border-color: rgba(15, 118, 110, 0.24);
  background: rgba(15, 118, 110, 0.08);
}

.like-btn.el-button--primary.is-plain {
  color: #f8fffd;
  border-color: transparent;
  background: linear-gradient(135deg, #0f766e, #1b7d79);
  box-shadow: 0 10px 22px rgba(15, 118, 110, 0.16);
}

.like-btn.el-button--primary.is-plain:hover,
.like-btn.el-button--primary.is-plain:focus-visible {
  color: #f8fffd;
  background: linear-gradient(135deg, #126f68, #1f6d7f);
}

.pager-shell {
  display: flex;
  justify-content: center;
  padding: 18px;
  border-radius: 24px;
}

@media (max-width: 960px) {
  .forum-hero,
  .forum-toolbar {
    grid-template-columns: 1fr;
    flex-direction: column;
  }

  .toolbar-main {
    grid-template-columns: 1fr;
  }
}
</style>
