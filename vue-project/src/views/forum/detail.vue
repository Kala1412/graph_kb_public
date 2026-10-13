<template>
  <div class="forum-detail-page" v-loading="loading">
    <section v-if="post" class="post-panel">
      <div class="post-topline">
        <div class="tag-cluster">
          <el-tag round effect="plain">{{ post.category.name }}</el-tag>
          <span>{{ formatDate(post.created_at) }}</span>
        </div>
        <button class="return-link" type="button" @click="router.push('/forum')">返回讨论区</button>
      </div>

      <h1>{{ post.title }}</h1>
      <div class="post-author">
        <el-avatar :src="post.author.avatar_url" :size="46">{{ post.author.username?.slice(0, 1) }}</el-avatar>
        <div>
          <strong>{{ post.author.username }}</strong>
          <span>{{ post.view_count }} 次浏览 · {{ post.comment_count }} 条评论</span>
        </div>
      </div>

      <div class="post-content">{{ post.content }}</div>

      <div class="post-actions">
        <el-button :type="post.liked_by_me ? 'primary' : 'default'" plain @click="togglePostLike">
          👍 {{ post.like_count }}
        </el-button>
        <button class="jump-link" type="button" @click="scrollToEditor">向下参与评论</button>
      </div>
    </section>

    <section class="comment-shell">
      <div class="comment-header">
        <div>
          <span class="eyebrow">Discussion Thread</span>
          <h2>评论与回复</h2>
        </div>
        <strong>{{ comments.length }} 条顶层评论</strong>
      </div>

      <div ref="editorAnchor" class="comment-editor">
        <el-input
          v-model="commentForm.content"
          type="textarea"
          :rows="5"
          maxlength="2000"
          show-word-limit
          :placeholder="replyTarget ? `回复 @${replyTarget.author.username}` : '补充你的判断、问题或经验'"
        />
        <div class="editor-actions">
          <span v-if="replyTarget">正在回复：{{ replyTarget.author.username }}</span>
          <div class="editor-buttons">
            <el-button v-if="replyTarget" class="soft-btn" @click="clearReply">取消回复</el-button>
            <el-button class="submit-btn" :loading="commentSubmitting" @click="submitComment">发布评论</el-button>
          </div>
        </div>
      </div>

      <div class="comment-list">
        <article v-for="comment in comments" :key="comment.id" class="comment-card">
          <div class="comment-main">
            <el-avatar :src="comment.author.avatar_url" :size="40">{{ comment.author.username?.slice(0, 1) }}</el-avatar>
            <div class="comment-content">
              <div class="comment-title">
                <strong>{{ comment.author.username }}</strong>
                <span>{{ formatDate(comment.created_at) }}</span>
              </div>
              <p>{{ comment.content }}</p>
              <div class="comment-actions">
                <button class="mini-pill" type="button" @click="toggleCommentLike(comment)">👍 {{ comment.like_count }}</button>
                <button class="mini-link" type="button" @click="setReply(comment)">回复</button>
              </div>
            </div>
          </div>

          <div v-if="comment.replies?.length" class="reply-list">
            <article v-for="reply in comment.replies" :key="reply.id" class="reply-card">
              <div class="reply-head">
                <strong>{{ reply.author.username }}</strong>
                <span>{{ formatDate(reply.created_at) }}</span>
              </div>
              <p>{{ reply.content }}</p>
              <button class="mini-pill" type="button" @click="toggleCommentLike(reply)">👍 {{ reply.like_count }}</button>
            </article>
          </div>
        </article>

        <el-empty v-if="!loading && comments.length === 0" description="还没有评论，来发出第一条观点吧。" />
      </div>
    </section>
  </div>
</template>

<script setup>
import { nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  createForumComment,
  fetchForumComments,
  fetchForumPostDetail,
  likeForumComment,
  likeForumPost,
  unlikeForumComment,
  unlikeForumPost,
} from '@/api/index'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const commentSubmitting = ref(false)
const post = ref(null)
const comments = ref([])
const editorAnchor = ref(null)
const replyTarget = ref(null)
const commentForm = reactive({ content: '' })
const postId = Number(route.params.postId)

const formatDate = (value) =>
  new Date(value).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })

const loadDetail = async () => {
  loading.value = true
  try {
    const [postRes, commentsRes] = await Promise.all([fetchForumPostDetail(postId), fetchForumComments(postId)])
    post.value = postRes.data
    comments.value = commentsRes.data.items || []
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '加载帖子失败')
  } finally {
    loading.value = false
  }
}

const scrollToEditor = async () => {
  await nextTick()
  editorAnchor.value?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

const clearReply = () => {
  replyTarget.value = null
}

const setReply = (comment) => {
  // 仅允许回复一级评论，replyTarget 保存顶层评论。
  replyTarget.value = comment
  scrollToEditor()
}

const togglePostLike = async () => {
  if (!post.value) return
  // 帖子点赞与列表页保持同一套乐观更新策略，减少交互迟滞感。
  const originalLiked = post.value.liked_by_me
  const originalCount = post.value.like_count
  post.value.liked_by_me = !originalLiked
  post.value.like_count += originalLiked ? -1 : 1
  try {
    if (originalLiked) await unlikeForumPost(post.value.id)
    else await likeForumPost(post.value.id)
  } catch (error) {
    post.value.liked_by_me = originalLiked
    post.value.like_count = originalCount
    ElMessage.error(error?.response?.data?.detail || '操作失败')
  }
}

const toggleCommentLike = async (comment) => {
  // 这里 comment 既可能是一级评论，也可能是 replies 里的回复对象；
  // 两者出参结构一致，因此可以复用同一套点赞逻辑。
  const originalLiked = comment.liked_by_me
  const originalCount = comment.like_count
  comment.liked_by_me = !originalLiked
  comment.like_count += originalLiked ? -1 : 1
  try {
    if (originalLiked) await unlikeForumComment(comment.id)
    else await likeForumComment(comment.id)
  } catch (error) {
    comment.liked_by_me = originalLiked
    comment.like_count = originalCount
    ElMessage.error(error?.response?.data?.detail || '操作失败')
  }
}

const submitComment = async () => {
  if (!commentForm.content.trim()) {
    ElMessage.warning('请输入评论内容')
    return
  }
  commentSubmitting.value = true
  try {
    // parent_comment_id 为空表示一级评论，有值表示回复某条一级评论。
    await createForumComment(postId, {
      content: commentForm.content,
      parent_comment_id: replyTarget.value?.id || null,
    })
    ElMessage.success('评论已发布')
    commentForm.content = ''
    clearReply()
    // 发布后直接全量刷新详情，保证 comment_count、评论树、点赞态都与服务端一致。
    await loadDetail()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '发布评论失败')
  } finally {
    commentSubmitting.value = false
  }
}

onMounted(loadDetail)
</script>

<style scoped>
.forum-detail-page {
  --detail-ink: #163947;
  --detail-subtle: #6b8189;
  --detail-line: rgba(22, 57, 71, 0.12);
  --detail-card: rgba(255, 252, 247, 0.92);
  display: grid;
  gap: 18px;
}

.post-panel,
.comment-shell,
.comment-card,
.comment-editor,
.reply-card {
  border: 1px solid var(--detail-line);
  background: var(--detail-card);
  box-shadow: 0 18px 42px rgba(24, 54, 66, 0.07);
}

.post-panel,
.comment-shell {
  padding: 28px 30px;
  border-radius: 32px;
}

.post-topline,
.post-actions,
.editor-actions,
.comment-main,
.comment-title,
.comment-actions,
.reply-head,
.comment-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.post-topline,
.comment-title,
.reply-head {
  align-items: center;
}

.tag-cluster {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--detail-subtle);
}

.tag-cluster :deep(.el-tag) {
  border: none;
  color: #0f766e;
  background: rgba(15, 118, 110, 0.1);
}

.post-panel h1,
.comment-header h2 {
  margin: 0;
  color: var(--detail-ink);
  font-family: Georgia, 'Times New Roman', serif;
}

.post-panel h1 {
  font-size: clamp(30px, 4vw, 42px);
  line-height: 1.12;
  margin-top: 10px;
}

.post-author {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 18px;
}

.post-author strong,
.comment-title strong,
.reply-head strong {
  display: block;
  color: var(--detail-ink);
}

.post-author span,
.comment-title span,
.reply-head span,
.comment-header strong,
.editor-actions span {
  color: var(--detail-subtle);
}

.post-content,
.comment-content p,
.reply-card p {
  margin: 22px 0 0;
  white-space: pre-wrap;
  color: #4c6771;
  line-height: 1.88;
}

.post-actions {
  margin-top: 22px;
  align-items: center;
  justify-content: flex-start;
}

.post-actions :deep(.el-button) {
  min-width: 94px;
  border-radius: 999px;
}

.post-actions :deep(.el-button--default.is-plain) {
  color: #56717a;
  border-color: rgba(15, 118, 110, 0.14);
  background: rgba(255, 255, 255, 0.84);
}

.post-actions :deep(.el-button--default.is-plain:hover),
.post-actions :deep(.el-button--default.is-plain:focus-visible) {
  color: #0f766e;
  border-color: rgba(15, 118, 110, 0.24);
  background: rgba(15, 118, 110, 0.08);
}

.post-actions :deep(.el-button--primary.is-plain) {
  color: #f8fffd;
  border-color: transparent;
  background: linear-gradient(135deg, #0f766e, #1b7d79);
  box-shadow: 0 10px 22px rgba(15, 118, 110, 0.16);
}

.post-actions :deep(.el-button--primary.is-plain:hover),
.post-actions :deep(.el-button--primary.is-plain:focus-visible) {
  color: #f8fffd;
  background: linear-gradient(135deg, #126f68, #1f6d7f);
}

.jump-link {
  border: none;
  padding: 0 4px;
  color: #6b8189;
  font-weight: 600;
  background: transparent;
  cursor: pointer;
}

.return-link {
  border: none;
  padding: 10px 18px;
  border-radius: 999px;
  color: #5b747d;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.86);
  box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.12);
  cursor: pointer;
  transition: all 0.2s ease;
}

.return-link:hover,
.return-link:focus-visible {
  color: #0f766e;
  background: rgba(15, 118, 110, 0.08);
  box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.22);
}

.jump-link:hover,
.jump-link:focus-visible {
  color: #0f766e;
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

.comment-shell {
  display: grid;
  gap: 18px;
}

.comment-editor {
  padding: 18px;
  border-radius: 24px;
}

.editor-actions {
  margin-top: 12px;
  align-items: center;
}

.editor-buttons {
  display: inline-flex;
  gap: 10px;
}

.soft-btn,
.submit-btn {
  border-radius: 999px;
  min-width: 108px;
}

.soft-btn {
  color: #5e767f;
  border-color: rgba(15, 118, 110, 0.14);
  background: rgba(255, 255, 255, 0.82);
}

.soft-btn:hover,
.soft-btn:focus-visible {
  color: #0f766e;
  border-color: rgba(15, 118, 110, 0.24);
  background: rgba(15, 118, 110, 0.08);
}

.submit-btn {
  color: #f8fffd;
  border: none;
  background: linear-gradient(135deg, #0f766e, #176b8a);
  box-shadow: 0 12px 24px rgba(15, 118, 110, 0.18);
}

.submit-btn:hover,
.submit-btn:focus-visible {
  color: #f8fffd;
  background: linear-gradient(135deg, #126f68, #1a6782);
}

.comment-list {
  display: grid;
  gap: 16px;
}

.comment-card {
  padding: 18px;
  border-radius: 24px;
}

.comment-main {
  align-items: flex-start;
}

.comment-content {
  flex: 1;
}

.comment-content p {
  margin-top: 10px;
}

.comment-actions {
  margin-top: 10px;
  justify-content: flex-start;
  align-items: center;
}

.mini-pill,
.mini-link {
  border: none;
  background: transparent;
  cursor: pointer;
}

.mini-pill {
  min-width: 74px;
  padding: 8px 14px;
  border-radius: 999px;
  color: #5b747d;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.12);
}

.mini-pill:hover,
.mini-pill:focus-visible {
  color: #0f766e;
  background: rgba(15, 118, 110, 0.08);
}

.mini-link {
  padding: 6px 4px;
  color: #6b8189;
  font-weight: 600;
}

.mini-link:hover,
.mini-link:focus-visible {
  color: #0f766e;
}

.reply-list {
  display: grid;
  gap: 12px;
  margin-top: 14px;
  padding-left: 52px;
}

.reply-card {
  padding: 14px 16px;
  border-radius: 20px;
  background: rgba(251, 253, 252, 0.94);
}

.reply-card p {
  margin-top: 8px;
}

@media (max-width: 900px) {
  .post-panel,
  .comment-shell {
    padding: 22px;
  }

  .comment-main,
  .editor-actions,
  .comment-header,
  .post-actions {
    flex-direction: column;
  }

  .reply-list {
    padding-left: 0;
  }
}
</style>
