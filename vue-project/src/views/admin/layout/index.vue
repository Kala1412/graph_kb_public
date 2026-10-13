<template>
  <div class="admin-layout">
    <el-container class="admin-shell">
      <el-aside :width="isCollapse ? '92px' : '264px'" class="admin-aside">
        <div class="admin-logo">
          <div class="logo-mark">
            <el-icon :size="20"><Connection /></el-icon>
          </div>
          <div v-show="!isCollapse" class="logo-copy">
            <strong>Admin Console</strong>
            <span>Audit · Users · KB</span>
          </div>
        </div>

        <div class="collapse-trigger" @click="isCollapse = !isCollapse">
          <el-icon :size="18">
            <Expand v-if="isCollapse" />
            <Fold v-else />
          </el-icon>
          <span v-show="!isCollapse">折叠导航</span>
        </div>

        <el-menu
          :default-active="activeMenu"
          class="admin-menu"
          :collapse="isCollapse"
          :collapse-transition="false"
          @select="handleMenuSelect"
        >
          <el-menu-item index="/admin/dashboard">
            <el-icon><DataLine /></el-icon>
            <span>管理概览</span>
          </el-menu-item>
          <el-menu-item index="/admin/users">
            <el-icon><User /></el-icon>
            <span>用户管理</span>
          </el-menu-item>
          <el-menu-item index="/admin/knowledge">
            <el-icon><Files /></el-icon>
            <span>知识库管理</span>
          </el-menu-item>
          <el-menu-item index="/admin/sessions">
            <el-icon><ChatLineRound /></el-icon>
            <span>会话管理</span>
          </el-menu-item>
          <el-menu-item index="/admin/medical-profiles">
            <el-icon><Memo /></el-icon>
            <span>个人病症管理</span>
          </el-menu-item>
          <el-menu-item index="/admin/audit-logs">
            <el-icon><Document /></el-icon>
            <span>审计日志</span>
          </el-menu-item>
          <el-menu-item index="/admin/forum">
            <el-icon><ChatDotRound /></el-icon>
            <span>讨论区管理</span>
          </el-menu-item>
          <el-menu-item index="/dashboard">
            <el-icon><House /></el-icon>
            <span>返回前台</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <el-container>
        <el-header class="admin-header">
          <div class="header-left">
            <div class="breadcrumb-shell">
              <el-breadcrumb separator="/">
                <el-breadcrumb-item v-for="item in breadcrumbs" :key="item.path">
                  <router-link v-if="item.path !== route.path" :to="item.path" class="crumb-link">
                    {{ item.title }}
                  </router-link>
                  <span v-else>{{ item.title }}</span>
                </el-breadcrumb-item>
              </el-breadcrumb>
            </div>
          </div>

          <div class="header-right">
            <div class="admin-chip">
              <span>环境</span>
              <strong>Admin</strong>
            </div>
            <el-dropdown @command="handleCommand">
              <div class="avatar-wrap">
                <el-avatar :src="headerAvatar" :size="38" />
              </div>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="profile">个人中心</el-dropdown-item>
                  <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </el-header>

        <el-main class="admin-main">
          <router-view />
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
  ChatDotRound,
  ChatLineRound,
  Connection,
  DataLine,
  Document,
  Expand,
  Files,
  Fold,
  House,
  Memo,
  User,
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const isCollapse = ref(false)
const defaultAvatar = 'https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55bcpng.png'
const headerAvatar = ref(defaultAvatar)

const activeMenu = computed(() => {
  const path = route.path || ''
  if (path.startsWith('/admin/knowledge')) return '/admin/knowledge'
  if (path.startsWith('/admin/users')) return '/admin/users'
  if (path.startsWith('/admin/sessions')) return '/admin/sessions'
  if (path.startsWith('/admin/medical-profiles')) return '/admin/medical-profiles'
  if (path.startsWith('/admin/audit-logs')) return '/admin/audit-logs'
  if (path.startsWith('/admin/forum')) return '/admin/forum'
  if (path.startsWith('/admin/dashboard')) return '/admin/dashboard'
  return path
})

const breadcrumbs = computed(() => {
  const matched = route.matched.filter((item) => item.meta?.title)
  if (matched.length === 0) return [{ title: '系统管理', path: '/admin/users' }]
  return matched.map((item) => ({
    title: item.meta.title,
    path: item.path.includes(':') ? route.path : item.path,
  }))
})

const handleMenuSelect = (path) => {
  router.push(path)
}

const handleCommand = (command) => {
  if (command === 'logout') {
    localStorage.removeItem('token')
    localStorage.removeItem('refreshToken')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('role')
    ElMessage.success('退出成功')
    window.location.href = '/login'
    return
  }

  if (command === 'profile') {
    router.push('/profile')
  }
}

const loadHeaderProfile = async () => {
  try {
    const { data } = await getMyProfile()
    headerAvatar.value = data?.avatar_url || defaultAvatar
    if (data?.role) {
      localStorage.setItem('role', data.role)
    }
  } catch {
    headerAvatar.value = defaultAvatar
  }
}

onMounted(() => {
  loadHeaderProfile()
})
</script>

<style scoped>
.admin-layout {
  width: 100%;
  height: 100vh;
  background: linear-gradient(180deg, #f5f0e8 0%, #f6faf8 36%, #f7f8f4 100%);
}

.admin-shell {
  height: 100%;
}

.admin-aside {
  margin: 14px 0 14px 14px;
  border-radius: 28px;
  border: 1px solid rgba(21, 49, 59, 0.08);
  background: linear-gradient(180deg, rgba(255, 250, 242, 0.96), rgba(248, 251, 248, 0.96));
  box-shadow: 0 24px 48px rgba(31, 49, 58, 0.08);
  overflow-x: hidden;
  transition: width 0.25s ease;
}

.admin-logo {
  min-height: 82px;
  display: flex;
  align-items: center;
  gap: 12px;
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

.collapse-trigger {
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
}

.collapse-trigger:hover {
  background: rgba(15, 118, 110, 0.08);
  color: #0f766e;
}

.admin-menu {
  border-right: none;
  padding: 8px 12px 16px;
  background: transparent;
}

.admin-menu :deep(.el-menu-item) {
  min-height: 52px;
  margin-bottom: 8px;
  border-radius: 18px;
  color: #55686f;
  font-weight: 600;
}

.admin-menu :deep(.el-menu-item:hover) {
  background: rgba(15, 118, 110, 0.08);
  color: #0f766e;
}

.admin-menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(135deg, #0f766e, #146c94);
  color: #fff;
  box-shadow: 0 12px 24px rgba(15, 118, 110, 0.22);
}

.admin-menu :deep(.el-menu--collapse .el-menu-item) {
  justify-content: center;
  padding: 0 !important;
}

.admin-header {
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

.crumb-link {
  color: #475569;
  text-decoration: none;
}

.crumb-link:hover {
  color: #0f766e;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.admin-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  padding: 0 14px;
  border-radius: 999px;
  background: rgba(15, 118, 110, 0.08);
  color: #0f766e;
}

.admin-chip span {
  display: inline-flex;
  align-items: center;
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  color: #5f787f;
}

.admin-chip strong {
  display: inline-flex;
  align-items: center;
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  color: #0f766e;
}

.avatar-wrap {
  display: flex;
  align-items: center;
  cursor: pointer;
  padding: 2px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.76);
}

.admin-main {
  padding: 16px 14px 14px 16px;
  background: transparent;
}
</style>
