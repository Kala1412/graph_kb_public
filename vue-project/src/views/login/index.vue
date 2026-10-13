<template>
  <div class="login-container">
    <div class="login-left">
      <div class="system-info">
        <div class="brand-kicker">Medical Knowledge System</div>
        <div class="icon-container">
          <div class="system-icon">
            <div class="brand-orb orb-left"></div>
            <div class="brand-orb orb-right"></div>
            <div class="knowledge-mark">
              <div class="knowledge-card">
                <div class="card-spine"></div>
                <div class="card-lines">
                  <span class="line-short"></span>
                  <span class="line-long"></span>
                  <span class="line-mid"></span>
                </div>
                <div class="card-corner-chip">
                  <span></span>
                  <span></span>
                </div>
              </div>
              <div class="knowledge-lens">
                <div class="lens-core"></div>
                <div class="lens-scan"></div>
              </div>
              <div class="graph-links">
                <span class="graph-node node-a"></span>
                <span class="graph-node node-b"></span>
                <span class="graph-node node-c"></span>
              </div>
              <div class="brand-badge">RAG + Graph</div>
            </div>
          </div>
        </div>
        <h1 class="system-title">基于 RAG 的向量融合<br>医疗问答知识库系统</h1>
        <p class="system-desc">深度融合非结构化文本与结构化知识图谱，提供精准、可溯源的智能医疗建议</p>
        <div class="brand-pills">
          <span>向量检索</span>
          <span>图谱推理</span>
          <span>来源可追溯</span>
        </div>
      </div>
    </div>

    <div class="login-right">
      <div class="login-box">
        <div class="welcome-section">
          <h2 class="welcome-title">欢迎回来 👋</h2>
          <p class="welcome-desc">请输入您的账户信息以开始使用此管理您的项目</p>
        </div>

        <el-tabs v-model="activeTab" class="auth-tabs" stretch>
          <el-tab-pane label="登录" name="login">
            <el-form :model="loginForm" :rules="loginRules" ref="loginFormRef" class="login-form">
          <el-form-item v-if="false">
            <el-select
              v-model="loginForm.accountType"
              placeholder="请选择账户类型"
              size="large"
              style="width: 100%"
            >
              <el-option label="超级管理员" value="super" />
              <el-option label="管理员" value="admin" />
              <el-option label="普通用户" value="user" />
            </el-select>
          </el-form-item>

          <el-form-item prop="username">
            <el-input
              v-model="loginForm.username"
              placeholder="请输入用户名"
              size="large"
              clearable
            >
              <template #prefix>
                <el-icon><User /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="请输入密码"
              size="large"
              show-password
              @keyup.enter="handleLogin"
            >
              <template #prefix>
                <el-icon><Lock /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <div class="form-options">
            <el-checkbox v-model="loginForm.rememberMe">记住账号</el-checkbox>
            <el-link type="primary" :underline="false">忘记密码?</el-link>
          </div>

          <el-form-item>
            <el-button
              type="primary"
              size="large"
              style="width: 100%"
              :loading="loading"
              @click="handleLogin"
            >
              登录
            </el-button>
          </el-form-item>

          <div class="register-link" @click="switchToRegister">
            还没有账号? <el-link type="primary" :underline="false">创建账号</el-link>
          </div>
        </el-form>
      </el-tab-pane>
      <el-tab-pane label="注册" name="register">
        <el-form :model="registerForm" :rules="registerRules" ref="registerFormRef" class="login-form">
          <el-form-item prop="username">
            <el-input
              v-model="registerForm.username"
              placeholder="请输入用户名"
              size="large"
              clearable
            >
              <template #prefix>
                <el-icon><User /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item prop="email">
            <el-input
              v-model="registerForm.email"
              placeholder="邮箱地址 (可选)"
              size="large"
              clearable
            />
          </el-form-item>

          <el-form-item prop="password">
            <el-input
              v-model="registerForm.password"
              type="password"
              placeholder="请输入密码"
              size="large"
              show-password
            >
              <template #prefix>
                <el-icon><Lock /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item prop="confirmPassword">
            <el-input
              v-model="registerForm.confirmPassword"
              type="password"
              placeholder="请再次输入密码"
              size="large"
              show-password
              @keyup.enter="handleRegister"
            >
              <template #prefix>
                <el-icon><Lock /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item prop="role">
            <el-select
              v-model="registerForm.role"
              placeholder="请选择用户类型"
              size="large"
              style="width: 100%"
            >
              <el-option label="管理员" value="admin" />
              <el-option label="普通用户" value="user" />
            </el-select>
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              size="large"
              style="width: 100%"
              :loading="registerLoading"
              @click="handleRegister"
            >
              注册
            </el-button>
          </el-form-item>

          <div class="login-link" @click="switchToLogin">
            已有账号？
            <el-link type="primary" :underline="false">返回登录</el-link>
          </div>
        </el-form>
      </el-tab-pane>
    </el-tabs>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { loginRequest, registerRequest } from '@/api/index'

const router = useRouter()
const activeTab = ref('login')
const loginFormRef = ref(null)
const registerFormRef = ref(null)
const loading = ref(false)
const registerLoading = ref(false)

const loginForm = reactive({
  accountType: 'user',
  username: '',
  password: '',
  rememberMe: false
})

const registerForm = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  role: 'user'
})

const loginRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' }
  ]
}

const validateEmail = (rule, value, callback) => {
  if (!value) {
    callback()
    return
  }
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(value)) {
    callback(new Error('邮箱地址格式错误！'))
  } else {
    callback()
  }
}

const validateConfirmPassword = (rule, value, callback) => {
  if (!value) {
    callback(new Error('请再次输入密码以确认！'))
    return
  }
  if (value !== registerForm.password) {
    callback(new Error('两次输入的密码不一致！'))
  } else {
    callback()
  }
}

const registerRules = {
  username: [
    { required: true, message: '请输入用户名！', trigger: 'blur' }
  ],
  email: [
    { validator: validateEmail, trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码！', trigger: 'blur' },
    { min: 6, message: '密码必须大于6位！', trigger: 'blur' }
  ],
  confirmPassword: [
    { validator: validateConfirmPassword, trigger: 'blur' }
  ],
  role: [
    { required: true, message: '请选择用户类型！', trigger: 'change' }
  ]
}

const handleLogin = async () => {
  if (!loginFormRef.value) return

  // 使用 promise 风格的 validate()，校验失败会抛出异常
  try {
    await loginFormRef.value.validate()
  } catch (validateErr) {
    return
  }

  loading.value = true
  try {
    const data = await loginRequest(loginForm.username, loginForm.password)
    if (data && data.access_token) {
      if (data.role) {
        localStorage.setItem('role', data.role)
      }
      localStorage.setItem('token', data.access_token)
      localStorage.setItem('refreshToken', data.refresh_token)  // 新增
      ElMessage.success('登录成功')
      if (data.role === 'admin') {
        router.push('/admin/dashboard')
      } else {
        router.push('/dashboard')
      }
    } else {
      ElMessage.error('登录失败，服务器返回异常')
    }
  } catch (err) {
    console.error(err)
    const msg = err?.response?.data?.detail || err.message || '登录失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

const handleRegister = async () => {
  if (!registerFormRef.value) return

  try {
    await registerFormRef.value.validate()
  } catch (validateErr) {
    return
  }

  registerLoading.value = true
  try {
    const payload = {
      username: registerForm.username,
      password: registerForm.password,
      role: registerForm.role
    }
    if (registerForm.email) {
      payload.email = registerForm.email
    }
    await registerRequest(payload)

    const registeredUsername = registerForm.username
    ElMessage.success('注册成功！请继续登录')

    registerForm.username = ''
    registerForm.email = ''
    registerForm.password = ''
    registerForm.confirmPassword = ''
    registerForm.role = 'user'

    activeTab.value = 'login'
    loginForm.username = registeredUsername
    loginForm.password = ''
  } catch (err) {
    console.error(err)
    const msg = err?.response?.data?.detail || err.message || '注册失败'
    ElMessage.error(msg)
  } finally {
    registerLoading.value = false
  }
}

const switchToRegister = () => {
  activeTab.value = 'register'
}

const switchToLogin = () => {
  activeTab.value = 'login'
}

</script>

<style scoped>
.login-container {
  display: flex;
  height: 100vh;
  background: linear-gradient(135deg, #0f766e 0%, #146c94 100%);
}

/* 左侧区域 */
.login-left {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60px;
  color: white;
}

.system-info {
  text-align: center;
  max-width: 600px;
}

.brand-kicker {
  width: fit-content;
  min-height: 36px;
  margin: 0 auto 22px;
  padding: 0 16px;
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.16);
  border: 1px solid rgba(255, 255, 255, 0.18);
  color: rgba(244, 250, 248, 0.96);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  backdrop-filter: blur(14px);
}

.icon-container {
  margin-bottom: 40px;
}

/* 3D图标样式 */
.system-icon {
  width: 300px;
  height: 300px;
  margin: 0 auto;
  position: relative;
  animation: float 3s ease-in-out infinite;
}

@keyframes float {
  0%, 100% { transform: translateY(0px); }
  50% { transform: translateY(-20px); }
}

.platform {
  position: relative;
  width: 100%;
  height: 100%;
}

.platform-base {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  width: 240px;
  height: 40px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
}

.platform-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

.center-cylinder {
  width: 80px;
  height: 120px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.9) 0%, rgba(255, 255, 255, 0.6) 100%);
  border-radius: 10px;
  margin: 0 auto;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
  position: relative;
}

.center-cylinder::before {
  content: '';
  position: absolute;
  top: -10px;
  left: 50%;
  transform: translateX(-50%);
  width: 40px;
  height: 16px;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 50%;
}

.center-ring {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 120px;
  height: 50px;
  border: 3px solid rgba(255, 255, 255, 0.6);
  border-radius: 50%;
  animation: ring-rotate 4s linear infinite;
}

@keyframes ring-rotate {
  from { transform: translate(-50%, -50%) rotateZ(0deg); }
  to { transform: translate(-50%, -50%) rotateZ(360deg); }
}

.cloud {
  position: absolute;
  top: 60px;
  left: 30px;
  width: 50px;
  height: 30px;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 50%;
  box-shadow:
    20px 0 0 -5px rgba(255, 255, 255, 0.8),
    10px -5px 0 -3px rgba(255, 255, 255, 0.8);
  animation: cloud-move 5s ease-in-out infinite;
}

@keyframes cloud-move {
  0%, 100% { transform: translateX(0); }
  50% { transform: translateX(20px); }
}

.screen {
  position: absolute;
  top: 80px;
  right: 40px;
  width: 60px;
  height: 40px;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 5px;
  padding: 5px;
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
}

.screen-content {
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #0f766e 0%, #146c94 100%);
  border-radius: 3px;
  opacity: 0.5;
}

.data-flow {
  position: absolute;
  width: 2px;
  height: 60px;
  background: linear-gradient(to bottom, rgba(255, 255, 255, 0.8), transparent);
}

.flow-1 {
  top: 100px;
  left: 80px;
  transform: rotate(-30deg);
}

.flow-2 {
  top: 100px;
  right: 80px;
  transform: rotate(30deg);
}

.flow-dot {
  width: 6px;
  height: 6px;
  background: white;
  border-radius: 50%;
  position: absolute;
  top: -3px;
  left: -2px;
  animation: dot-pulse 2s ease-in-out infinite;
}

@keyframes dot-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.5); }
}

.brand-orb {
  position: absolute;
  border-radius: 999px;
  filter: blur(1px);
  opacity: 0.88;
}

.orb-left {
  width: 128px;
  height: 128px;
  top: 22px;
  left: 16px;
  background: radial-gradient(circle, rgba(255, 241, 212, 0.46) 0%, rgba(255, 241, 212, 0) 72%);
}

.orb-right {
  width: 144px;
  height: 144px;
  right: 8px;
  bottom: 18px;
  background: radial-gradient(circle, rgba(159, 224, 215, 0.34) 0%, rgba(159, 224, 215, 0) 74%);
}

.knowledge-mark {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
}

.knowledge-card {
  position: relative;
  width: 190px;
  height: 190px;
  border-radius: 48px;
  background: linear-gradient(155deg, rgba(255, 251, 245, 0.98) 0%, rgba(239, 249, 246, 0.96) 100%);
  border: 1px solid rgba(255, 255, 255, 0.52);
  box-shadow:
    0 28px 60px rgba(9, 36, 47, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.7);
  overflow: hidden;
}

.knowledge-card::before {
  content: '';
  position: absolute;
  inset: 18px;
  border-radius: 34px;
  background: rgba(255, 253, 248, 0.92);
  box-shadow: inset 0 0 0 1px rgba(21, 49, 59, 0.08);
}

.card-spine {
  position: absolute;
  left: 44px;
  top: 48px;
  width: 26px;
  height: 98px;
  border-radius: 18px;
  background: linear-gradient(180deg, #0f766e 0%, #146c94 100%);
  box-shadow: 0 14px 24px rgba(15, 118, 110, 0.26);
}

.card-lines {
  position: absolute;
  top: 62px;
  left: 82px;
  display: grid;
  gap: 12px;
}

.card-lines span {
  display: block;
  height: 14px;
  border-radius: 999px;
  background: linear-gradient(90deg, #f59e0b 0%, #fcd34d 100%);
  box-shadow: inset 0 -1px 0 rgba(0, 0, 0, 0.06);
}

.line-short {
  width: 50px;
}

.line-long {
  width: 72px;
}

.line-mid {
  width: 58px;
  opacity: 0.92;
}

.card-corner-chip {
  position: absolute;
  top: 42px;
  right: 30px;
  width: 44px;
  height: 44px;
  border-radius: 16px;
  background: linear-gradient(155deg, #fff8dc 0%, #d6f4ee 100%);
  box-shadow:
    0 14px 24px rgba(20, 108, 148, 0.16),
    inset 0 1px 0 rgba(255, 255, 255, 0.92);
  display: grid;
  place-items: center;
}

.card-corner-chip span {
  position: absolute;
  display: block;
  border-radius: 999px;
  background: linear-gradient(90deg, #0f766e 0%, #146c94 100%);
}

.card-corner-chip span:first-child {
  width: 18px;
  height: 8px;
  top: 12px;
  left: 13px;
}

.card-corner-chip span:last-child {
  width: 8px;
  height: 18px;
  right: 13px;
  bottom: 12px;
}

.knowledge-lens {
  position: absolute;
  right: 34px;
  bottom: 42px;
  width: 76px;
  height: 76px;
  border-radius: 50%;
  background: radial-gradient(circle at 30% 30%, rgba(255, 255, 255, 0.94) 0%, rgba(228, 249, 245, 0.96) 100%);
  border: 4px solid #146c94;
  box-shadow: 0 18px 28px rgba(20, 108, 148, 0.22);
}

.knowledge-lens::before {
  content: '';
  position: absolute;
  right: -10px;
  bottom: -20px;
  width: 16px;
  height: 54px;
  border-radius: 999px;
  background: linear-gradient(180deg, #0f766e 0%, #146c94 100%);
  transform: rotate(-38deg);
  transform-origin: top center;
}

.lens-core {
  position: absolute;
  inset: 50%;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(20, 108, 148, 0.95) 0%, rgba(15, 118, 110, 0.72) 58%, rgba(15, 118, 110, 0.18) 100%);
  box-shadow: 0 0 0 10px rgba(20, 108, 148, 0.08);
  transform: translate(-50%, -50%);
}

.lens-scan {
  position: absolute;
  left: 16px;
  right: 16px;
  top: 50%;
  height: 3px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(245, 158, 11, 0) 0%, rgba(245, 158, 11, 0.92) 50%, rgba(245, 158, 11, 0) 100%);
  transform: translateY(-50%);
  box-shadow: 0 0 18px rgba(245, 158, 11, 0.35);
  animation: scan-pulse 2.8s ease-in-out infinite;
}

@keyframes scan-pulse {
  0%, 100% { opacity: 0.72; transform: translateY(-10px); }
  50% { opacity: 1; transform: translateY(10px); }
}

.graph-links {
  position: absolute;
  left: 44px;
  bottom: 46px;
  width: 88px;
  height: 72px;
}

.graph-links::before,
.graph-links::after {
  content: '';
  position: absolute;
  height: 2px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(255, 210, 122, 0.2) 0%, rgba(255, 210, 122, 0.95) 50%, rgba(140, 220, 207, 0.92) 100%);
  transform-origin: left center;
}

.graph-links::before {
  left: 18px;
  top: 18px;
  width: 42px;
  transform: rotate(18deg);
}

.graph-links::after {
  left: 20px;
  top: 42px;
  width: 48px;
  transform: rotate(-18deg);
}

.graph-node {
  position: absolute;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 3px solid rgba(255, 255, 255, 0.7);
  box-shadow: 0 10px 18px rgba(9, 36, 47, 0.14);
}

.node-a {
  left: 0;
  top: 12px;
  background: linear-gradient(180deg, #fbbf24 0%, #f59e0b 100%);
}

.node-b {
  left: 50px;
  top: 24px;
  background: linear-gradient(180deg, #3dd6c6 0%, #0f766e 100%);
}

.node-c {
  left: 18px;
  top: 50px;
  background: linear-gradient(180deg, #f8fafc 0%, #d8f3ee 100%);
}

.brand-badge {
  position: absolute;
  right: 24px;
  top: 26px;
  min-height: 34px;
  padding: 0 14px;
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
  color: #0f766e;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  box-shadow: 0 10px 24px rgba(9, 36, 47, 0.12);
}

.system-title {
  font-size: 32px;
  font-weight: 600;
  margin-bottom: 16px;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.system-desc {
  font-size: 16px;
  opacity: 0.9;
}

.brand-pills {
  margin-top: 22px;
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 10px;
}

.brand-pills span {
  min-height: 38px;
  padding: 0 16px;
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.16);
  color: rgba(248, 251, 249, 0.98);
  font-size: 13px;
  font-weight: 600;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(12px);
}

/* 右侧登录区域 */
.login-right {
  width: 580px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: white;
  box-shadow: -4px 0 20px rgba(0, 0, 0, 0.1);
}

.login-box {
  width: 420px;
  padding: 40px;
}

.welcome-section {
  margin-bottom: 32px;
}

.welcome-title {
  font-size: 28px;
  font-weight: 600;
  color: #1d2129;
  margin-bottom: 12px;
}

.welcome-desc {
  font-size: 14px;
  color: #86909c;
  line-height: 1.6;
}

.login-form {
  margin-top: 24px;
}

.auth-tabs :deep(.el-tabs__header) {
  margin: 0 0 16px;
}

.auth-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.auth-tabs :deep(.el-tabs__nav) {
  width: 100%;
  padding: 6px;
  border-radius: 999px;
  background: rgba(243, 239, 232, 0.96);
  border: 1px solid rgba(21, 49, 59, 0.08);
  gap: 6px;
}

.auth-tabs :deep(.el-tabs__item) {
  min-height: 44px;
  border-radius: 999px;
  color: #6b7f86 !important;
  font-size: 14px;
  font-weight: 700;
  transition: all 0.24s ease;
}

.auth-tabs :deep(.el-tabs__item.is-top:last-child),
.auth-tabs :deep(.el-tabs__item.is-top:nth-child(2)) {
  padding-left: 20px;
}

.auth-tabs :deep(.el-tabs__item.is-active) {
  color: #0f766e !important;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 10px 20px rgba(15, 118, 110, 0.14);
}

.auth-tabs :deep(.el-tabs__active-bar) {
  display: none;
}

.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.register-link {
  text-align: center;
  font-size: 14px;
  color: #86909c;
  margin-top: 24px;
}

.login-link {
  text-align: center;
  font-size: 14px;
  color: #86909c;
  margin-top: 16px;
}

/* Element Plus 样式覆盖 */
:deep(.el-form-item) {
  margin-bottom: 20px;
}

:deep(.el-button--primary) {
  background: linear-gradient(135deg, #0f766e 0%, #146c94 100%);
  border: none;
  height: 48px;
  border-radius: 22px;
  font-size: 16px;
  font-weight: 500;
}

:deep(.el-button--primary:hover) {
  opacity: 0.9;
}

:deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px #e5e7eb inset;
  transition: all 0.3s;
}

:deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #0f766e inset;
}

:deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #0f766e inset !important;
}
</style>
