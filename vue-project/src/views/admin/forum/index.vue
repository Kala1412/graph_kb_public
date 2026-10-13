<template>
  <div class="admin-forum-page">
    <section class="admin-hero">
      <div>
        <span class="eyebrow">Community Control</span>
        <h1>讨论区治理与分类配置</h1>
        <p>统一管理分类启用状态，查看帖子列表，并对评论内容执行基础隐藏治理。</p>
      </div>
      <div class="hero-stats">
        <div class="hero-chip">
          <strong>{{ postTotal }}</strong>
          <span>帖子总量</span>
        </div>
        <div class="hero-chip">
          <strong>{{ categories.length }}</strong>
          <span>分类数量</span>
        </div>
      </div>
    </section>

    <section class="admin-grid">
      <div class="admin-card">
        <div class="card-head">
          <div>
            <span class="eyebrow">Categories</span>
            <h2>分类管理</h2>
          </div>
        </div>

        <el-form :model="categoryForm" label-position="top" class="category-form">
          <el-form-item label="分类名称">
            <el-input v-model="categoryForm.name" placeholder="例如：案例交流" />
          </el-form-item>
          <el-form-item label="描述">
            <el-input v-model="categoryForm.description" placeholder="简要说明这个分类适合讨论什么" />
          </el-form-item>
          <div class="category-row">
            <el-form-item label="排序">
              <el-input-number v-model="categoryForm.sort_order" :min="0" :max="999" />
            </el-form-item>
            <el-form-item label="启用">
              <el-switch v-model="categoryForm.is_enabled" />
            </el-form-item>
          </div>
          <div class="category-actions">
            <el-button v-if="editingCategoryId" class="ghost-btn" @click="resetCategoryForm">取消编辑</el-button>
            <el-button class="primary-btn" :loading="categorySaving" @click="saveCategory">
              {{ editingCategoryId ? '更新分类' : '新增分类' }}
            </el-button>
          </div>
        </el-form>

        <el-table :data="categories" class="category-table">
          <el-table-column prop="name" label="名称" min-width="140" />
          <el-table-column prop="description" label="描述" min-width="220" show-overflow-tooltip />
          <el-table-column prop="sort_order" label="排序" width="90" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag class="status-tag" :class="{ muted: !row.is_enabled }">{{ row.is_enabled ? '启用' : '停用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <div class="action-group single">
                <button class="action-pill" type="button" @click="editCategory(row)">编辑</button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="admin-card">
        <div class="card-head posts-head">
          <div>
            <span class="eyebrow">Moderation</span>
            <h2>帖子治理</h2>
          </div>
          <el-select v-model="postFilter" placeholder="帖子状态">
            <el-option label="全部可见帖子" value="all" />
            <el-option label="仅正常帖子" value="active" />
            <el-option label="仅隐藏帖子" value="hidden" />
          </el-select>
        </div>

        <el-table :data="filteredPosts" v-loading="postsLoading">
          <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
          <el-table-column label="分类" width="110">
            <template #default="{ row }">{{ row.category.name }}</template>
          </el-table-column>
          <el-table-column label="作者" width="110">
            <template #default="{ row }">{{ row.author.username }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag class="status-tag" :class="{ muted: row.status !== 'active' }">
                {{ row.status === 'active' ? '正常' : '隐藏' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="互动" width="120">
            <template #default="{ row }">{{ row.like_count }} 赞 / {{ row.comment_count }} 评</template>
          </el-table-column>
          <el-table-column label="操作" width="220">
            <template #default="{ row }">
              <div class="action-group">
                <button class="action-pill" type="button" @click="togglePostStatus(row)">
                  {{ row.status === 'active' ? '隐藏' : '恢复' }}
                </button>
                <button class="action-pill" type="button" @click="openComments(row)">评论治理</button>
                <button class="action-pill" type="button" @click="openPostPreview(row)">查看</button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </section>

    <el-drawer
      v-model="postPreviewVisible"
      size="42%"
      :title="currentPreviewPost ? `帖子查看 · ${currentPreviewPost.title}` : '帖子查看'"
    >
      <div class="post-preview-shell" v-loading="postPreviewLoading">
        <template v-if="currentPreviewPost">
          <div class="preview-meta">
            <el-tag class="status-tag" :class="{ muted: currentPreviewPost.status !== 'active' }">
              {{ currentPreviewPost.status === 'active' ? '正常' : '隐藏' }}
            </el-tag>
            <span>{{ currentPreviewPost.category.name }}</span>
            <span>{{ formatDate(currentPreviewPost.created_at) }}</span>
          </div>
          <h3>{{ currentPreviewPost.title }}</h3>
          <div class="preview-author">
            <strong>{{ currentPreviewPost.author.username }}</strong>
            <span>
              {{ currentPreviewPost.view_count }} 浏览 · {{ currentPreviewPost.comment_count }} 评论 ·
              {{ currentPreviewPost.like_count }} 点赞
            </span>
          </div>
          <p>{{ currentPreviewPost.content }}</p>
        </template>
      </div>
    </el-drawer>

    <el-drawer v-model="commentDrawerVisible" size="42%" :title="currentPost ? `评论治理 · ${currentPost.title}` : '评论治理'">
      <div class="comment-admin-list" v-loading="commentsLoading">
        <article v-for="comment in commentItems" :key="comment.id" class="comment-admin-card">
          <div class="comment-admin-head">
            <div>
              <strong>{{ comment.author.username }}</strong>
              <span>{{ formatDate(comment.created_at) }}</span>
            </div>
            <el-tag :type="comment.status === 'active' ? 'success' : 'warning'">
              {{ comment.status === 'active' ? '正常' : '隐藏' }}
            </el-tag>
          </div>
          <p>{{ comment.content }}</p>
          <div class="comment-admin-actions">
            <span>{{ comment.like_count }} 赞</span>
            <button class="action-pill" type="button" @click="toggleCommentStatus(comment)">
              {{ comment.status === 'active' ? '隐藏评论' : '恢复评论' }}
            </button>
          </div>
        </article>
        <el-empty v-if="!commentsLoading && commentItems.length === 0" description="该帖子暂无评论" />
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  createAdminForumCategory,
  fetchAdminForumCategories,
  fetchForumComments,
  fetchForumPostDetail,
  fetchForumPosts,
  updateAdminForumCategory,
  updateAdminForumCommentStatus,
  updateAdminForumPostStatus,
} from '@/api/index'

const categories = ref([])
const posts = ref([])
const postTotal = ref(0)
const postsLoading = ref(false)
const commentsLoading = ref(false)
const categorySaving = ref(false)
const editingCategoryId = ref(null)
const postFilter = ref('all')
const commentDrawerVisible = ref(false)
const postPreviewVisible = ref(false)
const postPreviewLoading = ref(false)
const currentPost = ref(null)
const currentPreviewPost = ref(null)
const commentItems = ref([])
const categoryForm = reactive({ name: '', description: '', sort_order: 0, is_enabled: true })

const filteredPosts = computed(() => {
  // 后台先把帖子拉全，再在前端做轻量状态筛选，便于快速切换查看。
  if (postFilter.value === 'all') return posts.value
  return posts.value.filter((item) => item.status === postFilter.value)
})

const formatDate = (value) =>
  new Date(value).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })

const loadCategories = async () => {
  // 后台分类列表要包含停用分类，因此必须走 admin 接口而不是普通用户接口。
  const { data } = await fetchAdminForumCategories()
  categories.value = data.items || []
}

const loadPosts = async () => {
  postsLoading.value = true
  try {
    // 这里复用普通帖子列表接口，因为管理员身份访问时后端本身就会放宽可见范围。
    const { data } = await fetchForumPosts({ page: 1, page_size: 50, sort_by: 'latest' })
    posts.value = data.items || []
    postTotal.value = data.total || 0
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '加载帖子失败')
  } finally {
    postsLoading.value = false
  }
}

const resetCategoryForm = () => {
  editingCategoryId.value = null
  categoryForm.name = ''
  categoryForm.description = ''
  categoryForm.sort_order = 0
  categoryForm.is_enabled = true
}

const editCategory = (category) => {
  editingCategoryId.value = category.id
  categoryForm.name = category.name
  categoryForm.description = category.description || ''
  categoryForm.sort_order = category.sort_order
  categoryForm.is_enabled = category.is_enabled
}

const saveCategory = async () => {
  if (!categoryForm.name.trim()) {
    ElMessage.warning('请输入分类名称')
    return
  }
  categorySaving.value = true
  try {
    if (editingCategoryId.value) {
      await updateAdminForumCategory(editingCategoryId.value, categoryForm)
      ElMessage.success('分类已更新')
    } else {
      await createAdminForumCategory(categoryForm)
      ElMessage.success('分类已新增')
    }
    resetCategoryForm()
    await loadCategories()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '保存分类失败')
  } finally {
    categorySaving.value = false
  }
}

const togglePostStatus = async (post) => {
  try {
    // 治理仅开放 active 与 hidden 状态切换。
    const nextStatus = post.status === 'active' ? 'hidden' : 'active'
    const { data } = await updateAdminForumPostStatus(post.id, nextStatus)
    Object.assign(post, data)
    ElMessage.success(nextStatus === 'active' ? '帖子已恢复' : '帖子已隐藏')
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '更新帖子状态失败')
  }
}

const openComments = async (post) => {
  currentPost.value = post
  commentDrawerVisible.value = true
  commentsLoading.value = true
  try {
    // 评论接口返回的是“顶层评论 + replies”，这里展开成平铺列表更适合后台逐条治理。
    const { data } = await fetchForumComments(post.id)
    const flat = []
    ;(data.items || []).forEach((item) => {
      flat.push(item)
      ;(item.replies || []).forEach((reply) => flat.push(reply))
    })
    commentItems.value = flat
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '加载评论失败')
  } finally {
    commentsLoading.value = false
  }
}

const openPostPreview = async (post) => {
  currentPreviewPost.value = post
  postPreviewVisible.value = true
  postPreviewLoading.value = true
  try {
    const { data } = await fetchForumPostDetail(post.id)
    currentPreviewPost.value = data
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '加载帖子详情失败')
  } finally {
    postPreviewLoading.value = false
  }
}

const toggleCommentStatus = async (comment) => {
  try {
    const nextStatus = comment.status === 'active' ? 'hidden' : 'active'
    const { data } = await updateAdminForumCommentStatus(comment.id, nextStatus)
    Object.assign(comment, data)
    ElMessage.success(nextStatus === 'active' ? '评论已恢复' : '评论已隐藏')
    // 评论隐藏/恢复会影响帖子 comment_count，所以这里顺手刷新帖子列表统计。
    await loadPosts()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '更新评论状态失败')
  }
}

onMounted(async () => {
  await Promise.all([loadCategories(), loadPosts()])
})
</script>

<style scoped>
.admin-forum-page {
  --admin-ink: #183642;
  --admin-subtle: #6c7f86;
  --admin-line: rgba(24, 54, 66, 0.1);
  --admin-card: rgba(255, 252, 247, 0.94);
  display: grid;
  gap: 18px;
}

.admin-hero,
.admin-card,
.comment-admin-card {
  border: 1px solid var(--admin-line);
  background: var(--admin-card);
  box-shadow: 0 18px 42px rgba(24, 54, 66, 0.07);
}

.admin-hero {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  padding: 28px 30px;
  border-radius: 30px;
}

.eyebrow {
  display: inline-flex;
  margin-bottom: 10px;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #0f766e;
  background: rgba(15, 118, 110, 0.12);
}

.admin-hero h1,
.card-head h2 {
  margin: 0;
  color: var(--admin-ink);
  font-family: Georgia, 'Times New Roman', serif;
}

.admin-hero p {
  margin: 12px 0 0;
  max-width: 720px;
  color: var(--admin-subtle);
  line-height: 1.8;
}

.hero-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(120px, 1fr));
  gap: 12px;
}

.hero-chip {
  display: grid;
  gap: 6px;
  align-content: center;
  padding: 18px 20px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.76);
}

.hero-chip strong {
  font-size: 28px;
  color: var(--admin-ink);
}

.hero-chip span {
  color: var(--admin-subtle);
}

.admin-grid {
  display: grid;
  grid-template-columns: minmax(320px, 0.9fr) minmax(0, 1.4fr);
  gap: 18px;
}

.admin-card {
  padding: 24px;
  border-radius: 28px;
}

.card-head,
.posts-head,
.comment-admin-head,
.comment-admin-actions {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.category-form {
  margin-top: 18px;
}

.category-row,
.category-actions {
  display: flex;
  gap: 16px;
  align-items: center;
}

.ghost-btn,
.primary-btn {
  min-width: 112px;
  border-radius: 999px;
}

.ghost-btn {
  color: #5e767f;
  border-color: rgba(15, 118, 110, 0.14);
  background: rgba(255, 255, 255, 0.84);
}

.ghost-btn:hover,
.ghost-btn:focus-visible {
  color: #0f766e;
  border-color: rgba(15, 118, 110, 0.24);
  background: rgba(15, 118, 110, 0.08);
}

.primary-btn {
  color: #f8fffd;
  border: none;
  background: linear-gradient(135deg, #0f766e, #176b8a);
  box-shadow: 0 12px 24px rgba(15, 118, 110, 0.18);
}

.primary-btn:hover,
.primary-btn:focus-visible {
  color: #f8fffd;
  background: linear-gradient(135deg, #126f68, #1a6782);
}

.category-table {
  margin-top: 18px;
}

.status-tag {
  border: none;
  color: #0f766e;
  background: rgba(15, 118, 110, 0.12);
}

.status-tag.muted {
  color: #7d7d73;
  background: rgba(116, 126, 131, 0.12);
}

.action-group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: nowrap;
}

.action-group.single {
  justify-content: flex-start;
}

.action-pill {
  border: none;
  min-width: 66px;
  padding: 7px 12px;
  border-radius: 999px;
  color: #5d747c;
  font-size: 13px;
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.12);
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-pill:hover,
.action-pill:focus-visible {
  color: #0f766e;
  background: rgba(15, 118, 110, 0.08);
  box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.22);
}

.comment-admin-list {
  display: grid;
  gap: 14px;
}

.post-preview-shell {
  display: grid;
  gap: 14px;
}

.preview-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  color: var(--admin-subtle);
  font-size: 13px;
}

.post-preview-shell h3 {
  margin: 0;
  color: var(--admin-ink);
  font-family: Georgia, 'Times New Roman', serif;
  font-size: 28px;
  line-height: 1.2;
}

.preview-author {
  display: grid;
  gap: 4px;
}

.preview-author strong {
  color: var(--admin-ink);
}

.preview-author span {
  color: var(--admin-subtle);
  font-size: 13px;
}

.post-preview-shell p {
  margin: 0;
  color: #4f6871;
  line-height: 1.9;
  white-space: pre-wrap;
}

.comment-admin-card {
  padding: 16px;
  border-radius: 22px;
}

.comment-admin-head span,
.comment-admin-actions span {
  color: var(--admin-subtle);
  font-size: 13px;
}

.comment-admin-head .el-tag {
  border: none;
}

.comment-admin-head .el-tag.el-tag--success,
.comment-admin-head .el-tag.el-tag--warning {
  color: #0f766e;
  background: rgba(15, 118, 110, 0.12);
}

.comment-admin-head .el-tag.el-tag--warning {
  color: #7d7d73;
  background: rgba(116, 126, 131, 0.12);
}

.comment-admin-card p {
  margin: 10px 0;
  color: #4f6871;
  line-height: 1.8;
  white-space: pre-wrap;
}

@media (max-width: 1100px) {
  .admin-hero,
  .admin-grid,
  .category-row,
  .category-actions {
    grid-template-columns: 1fr;
    flex-direction: column;
  }

  .action-group {
    flex-wrap: wrap;
  }
}
</style>
