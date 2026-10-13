<template>
  <div class="layout-container">
    <el-container>
      <el-aside :width="isCollapse ? '92px' : '264px'" class="shell-aside">
        <div class="logo">
          <div class="logo-mark">
            <el-icon :size="20"><Connection /></el-icon>
          </div>
          <div v-show="!isCollapse" class="logo-copy">
            <strong>MedGraph RAG</strong>
            <span>Clinical Knowledge System</span>
          </div>
        </div>

        <div class="collapse-btn" @click="toggleCollapse">
          <el-icon :size="18">
            <Expand v-if="isCollapse" />
            <Fold v-else />
          </el-icon>
          <span v-show="!isCollapse">折叠导航</span>
        </div>

        <el-menu
          :default-active="activeMenu"
          class="side-menu"
          @select="handleMenuSelect"
          :collapse="isCollapse"
          :collapse-transition="false"
        >
          <el-sub-menu index="overview">
            <template #title>
              <el-icon><Grid /></el-icon>
              <span>概览</span>
            </template>
            <el-menu-item index="/dashboard">
              <el-icon><DataLine /></el-icon>
              <span>分析页</span>
            </el-menu-item>
            <el-menu-item index="/workspace">
              <el-icon><Monitor /></el-icon>
              <span>工作台</span>
            </el-menu-item>
          </el-sub-menu>

          <el-menu-item index="/chat">
            <el-icon><ChatLineRound /></el-icon>
            <span>聊天</span>
          </el-menu-item>

          <el-menu-item index="/knowledge">
            <el-icon><Files /></el-icon>
            <span>知识库</span>
          </el-menu-item>

          <el-menu-item index="/forum">
            <el-icon><ChatDotRound /></el-icon>
            <span>讨论区</span>
          </el-menu-item>

          <el-menu-item index="/graph">
            <el-icon><Share /></el-icon>
            <span>知识图谱</span>
          </el-menu-item>

          <el-menu-item index="/about">
            <el-icon><InfoFilled /></el-icon>
            <span>关于</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <el-container>
        <el-header class="shell-header">
          <div class="header-left">
            <transition name="breadcrumb-fade" mode="out-in">
              <div :key="route.fullPath" class="breadcrumb-shell">
                <el-breadcrumb separator="/" class="breadcrumb">
                  <el-breadcrumb-item v-for="(item, index) in breadcrumbs" :key="item.path">
                    <router-link
                      v-if="index !== breadcrumbs.length - 1"
                      :to="item.path"
                      class="breadcrumb-link"
                    >
                      <el-icon v-if="index === 0"><House /></el-icon>
                      {{ item.title }}
                    </router-link>
                    <span v-else class="breadcrumb-current">
                      <el-icon v-if="index === 0"><House /></el-icon>
                      {{ item.title }}
                    </span>
                  </el-breadcrumb-item>
                </el-breadcrumb>
              </div>
            </transition>
          </div>

          <div class="header-right">
            <div class="header-chip">
              <span>环境</span>
              <strong>{{ roleLabel }}</strong>
            </div>

            <el-tooltip content="搜索">
              <el-button class="header-action" circle :icon="Search" />
            </el-tooltip>
            <el-tooltip content="通知">
              <el-badge :value="12" :max="99">
                <el-button class="header-action" circle :icon="Bell" />
              </el-badge>
            </el-tooltip>
            <el-tooltip content="全屏">
              <el-button class="header-action" circle :icon="FullScreen" />
            </el-tooltip>

            <el-dropdown @command="handleCommand">
              <div class="user-avatar">
                <el-avatar :src="headerAvatar" :size="38" />
              </div>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="profile">个人中心</el-dropdown-item>
                  <el-dropdown-item command="settings">系统设置</el-dropdown-item>
                  <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </el-header>

        <el-main class="shell-main">
          <router-view v-slot="{ Component, route: viewRoute }">
            <keep-alive>
              <component
                v-if="viewRoute.meta?.keepAlive"
                :is="Component"
                :key="String(viewRoute.name || viewRoute.path)"
              />
            </keep-alive>
            <transition name="fade-slide" mode="out-in">
              <component
                v-if="!viewRoute.meta?.keepAlive"
                :is="Component"
                :key="viewRoute.fullPath"
              />
            </transition>
          </router-view>
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getMyProfile } from '@/api/index'
import {
  Bell,
  ChatDotRound,
  ChatLineRound,
  Connection,
  DataLine,
  Expand,
  Files,
  Fold,
  FullScreen,
  Grid,
  House,
  InfoFilled,
  Monitor,
  Search,
  Share
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const isCollapse = ref(false)
const defaultAvatar = 'https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55bcpng.png'
const headerAvatar = ref(defaultAvatar)

const roleLabel = computed(() =>
  localStorage.getItem('role') === 'admin' ? '管理员' : '用户空间'
)

const toggleCollapse = () => {
  isCollapse.value = !isCollapse.value
}

const activeMenu = computed(() => {
  const path = route.path || ''
  if (path.startsWith('/knowledge')) return '/knowledge'
  if (path.startsWith('/forum')) return '/forum'
  if (path.startsWith('/graph')) return '/graph'
  if (path.startsWith('/chat')) return '/chat'
  if (path.startsWith('/about')) return '/about'
  return path
})

const handleMenuSelect = (index) => {
  router.push(index)
}

const handleCommand = (command) => {
  if (command === 'logout') {
    localStorage.removeItem('token')
    localStorage.removeItem('refreshToken')
    localStorage.removeItem('role')
    ElMessage.success('退出成功')
    window.location.href = '/login'
  } else if (command === 'profile') {
    router.push('/profile')
  } else if (command === 'settings') {
    ElMessage.info('系统设置')
  }
}

const loadHeaderProfile = async () => {
  try {
    const { data } = await getMyProfile()
    headerAvatar.value = data?.avatar_url || defaultAvatar
  } catch {
    headerAvatar.value = defaultAvatar
  }
}

const breadcrumbs = computed(() => {
  const matched = route.matched.filter((rec) => rec.meta && rec.meta.title)
  const crumbs = []
  let fullPath = ''

  matched.forEach((rec) => {
    let segment = rec.path || ''
    Object.keys(route.params || {}).forEach((k) => {
      segment = segment.replace(`:${k}`, route.params[k])
    })
    if (!segment.startsWith('/')) {
      if (fullPath === '' || fullPath.endsWith('/')) fullPath += segment
      else fullPath += `/${segment}`
    } else {
      fullPath = segment
    }
    crumbs.push({ title: rec.meta.title || rec.name, path: fullPath || route.path })
  })

  if (crumbs.length === 0 || crumbs[0].path !== '/dashboard') {
    crumbs.unshift({ title: '概览', path: '/dashboard' })
  }

  return crumbs
})

onMounted(() => {
  loadHeaderProfile()
})
</script>

<style scoped>
.layout-container {
  width: 100%;
  height: 100vh;
  background: linear-gradient(180deg, #f5f0e8 0%, #f6faf8 36%, #f7f8f4 100%);
}

.el-container {
  height: 100%;
}

.shell-aside {
  margin: 14px 0 14px 14px;
  border-radius: 28px;
  border: 1px solid rgba(21, 49, 59, 0.08);
  background:
    linear-gradient(180deg, rgba(255, 250, 242, 0.96), rgba(248, 251, 248, 0.96));
  box-shadow: 0 24px 48px rgba(31, 49, 58, 0.08);
  overflow-x: hidden;
  overflow-y: auto;
  transition: width 0.3s ease;
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 82px;
  padding: 18px 18px 16px;
  border-bottom: 1px solid rgba(21, 49, 59, 0.08);
}

.logo-mark {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  border-radius: 18px;
  color: #0f766e;
  background: rgba(15, 118, 110, 0.12);
}

.logo-copy {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.logo-copy strong {
  font-family: Georgia, 'Times New Roman', serif;
  font-size: 18px;
  color: #15313b;
}

.logo-copy span {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #6b7f86;
}

.collapse-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 44px;
  margin: 14px 14px 8px;
  border-radius: 16px;
  cursor: pointer;
  color: #6b7f86;
  background: rgba(255, 255, 255, 0.7);
  transition: background-color 0.2s ease, color 0.2s ease;
}

.collapse-btn:hover {
  background: rgba(15, 118, 110, 0.08);
  color: #0f766e;
}

.side-menu {
  border: none;
  padding: 8px 12px 16px;
  background: transparent;
}

:deep(.el-menu) {
  border-right: none;
  background: transparent;
}

:deep(.el-sub-menu__title),
:deep(.el-menu-item) {
  min-height: 52px;
  margin-bottom: 8px;
  border-radius: 18px;
  color: #55686f;
  font-weight: 600;
  line-height: 1;
}

:deep(.el-sub-menu__title:hover),
:deep(.el-menu-item:hover) {
  background: rgba(15, 118, 110, 0.08) !important;
  color: #0f766e !important;
}

:deep(.el-sub-menu .el-menu) {
  background: transparent;
}

:deep(.el-menu-item.is-active) {
  background: linear-gradient(135deg, #0f766e, #146c94) !important;
  color: #fff !important;
  box-shadow: 0 12px 24px rgba(15, 118, 110, 0.22);
}

:deep(.el-menu-item .el-icon),
:deep(.el-sub-menu__title .el-icon) {
  font-size: 18px;
}

:deep(.el-menu--collapse .el-sub-menu__title),
:deep(.el-menu--collapse .el-menu-item) {
  justify-content: center;
  padding: 0 !important;
}

.shell-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  height: 88px;
  margin: 14px 14px 0 16px;
  padding: 0 22px;
  border-radius: 28px;
  border: 1px solid rgba(21, 49, 59, 0.08);
  background: rgba(255, 252, 247, 0.92);
  box-shadow: 0 18px 40px rgba(31, 49, 58, 0.06);
}

.header-left {
  flex: 1;
  min-width: 0;
}

.breadcrumb-shell {
  display: inline-flex;
  min-height: 44px;
  padding: 0 16px;
  align-items: center;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.76);
}

.breadcrumb {
  font-size: 14px;
}

:deep(.el-breadcrumb__item) {
  display: flex;
  align-items: center;
}

:deep(.el-breadcrumb__inner) {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #6b7f86;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  padding: 0 14px;
  border-radius: 999px;
  background: rgba(15, 118, 110, 0.08);
  color: #0f766e;
}

.header-chip span {
  display: inline-flex;
  align-items: center;
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  color: #5f787f;
}

.header-chip strong {
  display: inline-flex;
  align-items: center;
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  color: #0f766e;
}

.header-action {
  width: 42px;
  height: 42px;
}

.user-avatar {
  display: flex;
  align-items: center;
  cursor: pointer;
  padding: 2px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.76);
}

.shell-main {
  padding: 16px 14px 14px 16px;
  overflow-y: auto;
  background: transparent;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(8px) scale(0.995);
}

.fade-slide-enter-active {
  transition: all 240ms cubic-bezier(0.2, 0.9, 0.2, 1);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px) scale(0.995);
}

.fade-slide-leave-active {
  transition: all 200ms cubic-bezier(0.2, 0.9, 0.2, 1);
}

.breadcrumb-fade-enter-from {
  opacity: 0;
  transform: translateY(-8px) scale(0.995);
}

.breadcrumb-fade-enter-active {
  transition: all 220ms cubic-bezier(0.2, 0.9, 0.2, 1);
}

.breadcrumb-fade-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.995);
}

.breadcrumb-fade-leave-active {
  transition: all 180ms cubic-bezier(0.2, 0.9, 0.2, 1);
}

.breadcrumb-link {
  color: #6b7f86;
  text-decoration: none;
}

.breadcrumb-link:hover {
  color: #0f766e;
}

.breadcrumb-current {
  color: #15313b;
  font-weight: 700;
}

@media (max-width: 900px) {
  .shell-header {
    height: auto;
    padding: 14px 18px;
    flex-direction: column;
    align-items: flex-start;
  }

  .header-right {
    width: 100%;
    flex-wrap: wrap;
  }
}
</style>
