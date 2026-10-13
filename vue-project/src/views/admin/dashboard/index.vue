<template>
  <div class="admin-dashboard">
    <div class="hero-card">
      <div class="hero-left">
        <h2>管理概览</h2>
        <p>管理员专用看板，包含系统统计卡片与图表分析。</p>
      </div>
      <el-button type="primary" plain :loading="loading" @click="refreshAll">刷新数据</el-button>
    </div>

    <el-card class="health-card" shadow="never" v-loading="healthLoading">
      <div class="health-header">
        <div class="health-title">系统状态</div>
        <div v-if="healthCheckedAt" class="health-meta">更新: {{ formatDate(healthCheckedAt) }}</div>
        <el-button size="small" @click="fetchHealth" :loading="healthLoading">刷新状态</el-button>
      </div>
      <div class="health-items">
        <div v-for="item in healthList" :key="item.key" class="health-item">
          <span class="health-dot" :class="statusClass(item.status)"></span>
          <div class="health-info">
            <div class="health-name">{{ item.label }}</div>
            <div class="health-desc">{{ item.desc }}</div>
          </div>
          <div class="health-status">
            <div class="health-text">{{ statusText(item.status) }}</div>
            <div v-if="item.latency_ms !== null && item.latency_ms !== undefined" class="health-latency">
              {{ item.latency_ms }} ms
            </div>
            <div v-else class="health-latency">--</div>
          </div>
        </div>
      </div>
    </el-card>

    <el-card class="alerts-card" shadow="never">
      <template #header>
        <div class="alerts-header">
          <span class="card-title">告警与待处理</span>
          <span class="alerts-tip">全站口径</span>
        </div>
      </template>
      <el-row :gutter="12" class="alerts-row">
        <el-col :xs="24" :sm="12" :md="6">
          <div class="alert-item warning">
            <div class="alert-label">解析中</div>
            <div class="alert-value">{{ statsData.alerts.parsing_count }}</div>
            <div class="alert-desc">待解析文件</div>
          </div>
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <div class="alert-item warning">
            <div class="alert-label">索引中</div>
            <div class="alert-value">{{ statsData.alerts.indexing_count }}</div>
            <div class="alert-desc">待索引文件</div>
          </div>
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <div class="alert-item danger">
            <div class="alert-label">失败文件数</div>
            <div class="alert-value">{{ statsData.alerts.error_count }}</div>
            <div class="alert-desc">解析失败 + 索引失败</div>
          </div>
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <div class="alert-item" :class="highErrorRate ? 'danger highlight' : 'normal'">
            <div class="alert-label">失败率</div>
            <div class="alert-value">{{ formatPercent(statsData.alerts.error_rate) }}</div>
            <div class="alert-desc">阈值 10%</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-info">
              <div class="stat-value">{{ statsData.cards.total_users }}</div>
              <div class="stat-label">用户量</div>
              <div class="stat-total">总用户量 {{ statsData.cards.total_users }}</div>
            </div>
            <div class="stat-icon blue">
              <el-icon size="32"><User /></el-icon>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-info">
              <div class="stat-value">{{ statsData.cards.total_kb }}</div>
              <div class="stat-label">知识库数</div>
              <div class="stat-total">总知识库数 {{ statsData.cards.total_kb }}</div>
            </div>
            <div class="stat-icon orange">
              <el-icon size="32"><View /></el-icon>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-info">
              <div class="stat-value">{{ statsData.cards.total_files }}</div>
              <div class="stat-label">文件总数</div>
              <div class="stat-total">累计文件 {{ statsData.cards.total_files }}</div>
            </div>
            <div class="stat-icon purple">
              <el-icon size="32"><Document /></el-icon>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-info">
              <div class="stat-value">{{ statsData.cards.total_sessions }}</div>
              <div class="stat-label">会话数</div>
              <div class="stat-total">总会话数 {{ statsData.cards.total_sessions }}</div>
            </div>
            <div class="stat-icon yellow">
              <el-icon size="32"><Download /></el-icon>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-info">
              <div class="stat-value">{{ statsData.cards.total_messages }}</div>
              <div class="stat-label">对话记录数</div>
              <div class="stat-total">总对话记录数 {{ statsData.cards.total_messages }}</div>
            </div>
            <div class="stat-icon green">
              <el-icon size="32"><PieChart /></el-icon>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-info">
              <div class="stat-value">{{ statsData.cards.storage_mb }}</div>
              <div class="stat-label">存储容量(MB)</div>
              <div class="stat-total">累计存储 {{ statsData.cards.storage_mb }} MB</div>
            </div>
            <div class="stat-icon slate">
              <el-icon size="32"><Coin /></el-icon>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="chart-row">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span class="card-title">系统活跃趋势 (最近14天)</span>
              <el-radio-group v-model="trendTab" size="small">
                <el-radio-button label="访问趋势" />
                <el-radio-button label="月访问量" />
              </el-radio-group>
            </div>
          </template>
          <div ref="trendChartRef" style="height: 400px"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="bottom-charts">
      <el-col :span="8">
        <el-card>
          <template #header>
            <span class="card-title">核心指标</span>
          </template>
          <div ref="radarChartRef" style="height: 300px"></div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card>
          <template #header>
            <span class="card-title">知识库文件分布</span>
          </template>
          <div ref="pieChart1Ref" style="height: 300px"></div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card>
          <template #header>
            <span class="card-title">文件状态分布</span>
          </template>
          <div ref="pieChart2Ref" style="height: 300px"></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { User, View, Download, PieChart, Document, Coin } from '@element-plus/icons-vue'
import { getDashboardStats, getDashboardHealth } from '@/api/index'

const loading = ref(false)
const trendTab = ref('访问趋势')
const trendChartRef = ref(null)
const radarChartRef = ref(null)
const pieChart1Ref = ref(null)
const pieChart2Ref = ref(null)
const healthLoading = ref(false)
const healthCheckedAt = ref('')
const healthStatusMap = ref({})

const statsData = ref({
  cards: {
    total_users: 0,
    total_kb: 0,
    total_files: 0,
    total_sessions: 0,
    total_messages: 0,
    storage_mb: 0,
    questions_7d: 0,
    indexed_files: 0,
  },
  alerts: {
    parsing_count: 0,
    indexing_count: 0,
    error_count: 0,
    error_rate: 0,
  },
  status_counts: {},
  kb_file_distribution: [],
  status_distribution: [],
  activity_trend: [],
})

const healthBaseList = [
  { key: 'milvus', label: 'Milvus', desc: '向量数据库' },
  { key: 'neo4j', label: 'Neo4j', desc: '图数据库' },
  { key: 'minio', label: 'MinIO', desc: '对象存储' },
  { key: 'llm', label: 'LLM', desc: '大模型服务' },
]

const statusClass = (status) => {
  if (status === 'up') return 'ok'
  if (status === 'down') return 'bad'
  return 'unknown'
}

const statusText = (status) => {
  if (status === 'up') return '正常'
  if (status === 'down') return '异常'
  return '未知'
}

const formatDate = (value) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', { hour12: false })
}

const formatPercent = (value) => `${((value || 0) * 100).toFixed(2)}%`

const highErrorRate = computed(() => (statsData.value.alerts.error_rate || 0) > 0.1)

const bindResize = (chart) => {
  if (chart.__resizeBound) return
  chart.__resizeBound = true
  window.addEventListener('resize', () => chart.resize())
}

const refreshCharts = () => {
  initTrendChart(statsData.value.activity_trend, trendTab.value)
  initPieChart1(statsData.value.kb_file_distribution)
  initPieChart2(statsData.value.status_distribution)
  initRadarChart(statsData.value.cards)
}

const fetchStats = async () => {
  loading.value = true
  try {
    // 与普通用户页共用同一接口：管理员身份下后端返回全站口径，告警也基于全站状态聚合。
    const response = await getDashboardStats()
    statsData.value = {
      ...statsData.value,
      ...response.data,
      cards: {
        ...statsData.value.cards,
        ...response.data?.cards,
      },
      alerts: {
        ...statsData.value.alerts,
        ...response.data?.alerts,
      },
      status_counts: response.data?.status_counts || {},
    }
    refreshCharts()
  } catch (error) {
    console.error(error)
    ElMessage.error('数据加载失败')
  } finally {
    loading.value = false
  }
}

const fetchHealth = async () => {
  healthLoading.value = true
  try {
    const response = await getDashboardHealth()
    const services = response?.data?.services || []
    const nextMap = {}
    services.forEach((item) => {
      nextMap[item.key] = {
        status: item.status,
        latency_ms: item.latency_ms,
        message: item.message,
      }
    })
    healthStatusMap.value = nextMap
    healthCheckedAt.value = response?.data?.checked_at || ''
  } catch (error) {
    console.error(error)
    ElMessage.error('状态加载失败')
  } finally {
    healthLoading.value = false
  }
}

const refreshAll = async () => {
  await Promise.all([fetchStats(), fetchHealth()])
}

const healthList = computed(() =>
  healthBaseList.map((item) => ({
    ...item,
    ...healthStatusMap.value[item.key],
  }))
)

const initTrendChart = (data = [], mode = trendTab.value) => {
  if (!trendChartRef.value) return
  const chart = echarts.getInstanceByDom(trendChartRef.value) || echarts.init(trendChartRef.value)

  let labels = []
  let messageData = []
  let fileData = []
  let series = []
  const legend = ['新增对话', '新增文件']

  if (mode === '月访问量') {
    const monthly = {}
    data.forEach((item) => {
      const month = item.date.slice(0, 7)
      if (!monthly[month]) {
        monthly[month] = { messages: 0, files: 0 }
      }
      monthly[month].messages += item.messages || 0
      monthly[month].files += item.files || 0
    })
    labels = Object.keys(monthly).sort()
    messageData = labels.map((m) => monthly[m].messages)
    fileData = labels.map((m) => monthly[m].files)
    series = [
      {
        name: '新增对话',
        type: 'bar',
        itemStyle: { color: '#0f766e' },
        data: messageData,
      },
      {
        name: '新增文件',
        type: 'bar',
        itemStyle: { color: '#52c41a' },
        data: fileData,
      },
    ]
  } else {
    labels = data.map((item) => item.date.split('-').slice(1).join('/'))
    messageData = data.map((item) => item.messages)
    fileData = data.map((item) => item.files)
    series = [
      {
        name: '新增对话',
        type: 'line',
        smooth: true,
        itemStyle: { color: '#0f766e' },
        areaStyle: { color: 'rgba(15, 118, 110, 0.12)' },
        data: messageData,
      },
      {
        name: '新增文件',
        type: 'line',
        smooth: true,
        itemStyle: { color: '#52c41a' },
        areaStyle: { color: 'rgba(82, 196, 26, 0.1)' },
        data: fileData,
      },
    ]
  }

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: legend, bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: mode === '月访问量',
      data: labels,
      axisTick: { show: false },
    },
    yAxis: { type: 'value', splitLine: { lineStyle: { type: 'dashed' } } },
    series,
  })

  bindResize(chart)
}

const getRadarMax = (value) => Math.max(1, Math.ceil((value || 0) * 1.2))

const initRadarChart = (cards = statsData.value.cards) => {
  if (!radarChartRef.value) return
  const chart = echarts.getInstanceByDom(radarChartRef.value) || echarts.init(radarChartRef.value)
  const values = [
    cards.total_users || 0,
    cards.total_kb || 0,
    cards.total_files || 0,
    cards.total_sessions || 0,
    cards.total_messages || 0,
  ]

  chart.setOption({
    radar: {
      indicator: [
        { name: '用户', max: getRadarMax(cards.total_users) },
        { name: '知识库', max: getRadarMax(cards.total_kb) },
        { name: '文件', max: getRadarMax(cards.total_files) },
        { name: '会话', max: getRadarMax(cards.total_sessions) },
        { name: '消息', max: getRadarMax(cards.total_messages) },
      ],
      radius: '60%',
      splitArea: {
        areaStyle: { color: ['rgba(15, 118, 110, 0.05)', 'rgba(15, 118, 110, 0.1)'] },
      },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: values,
            name: '系统指标',
            areaStyle: { color: 'rgba(15, 118, 110, 0.24)' },
            lineStyle: { color: '#0f766e' },
            itemStyle: { color: '#0f766e' },
          },
        ],
      },
    ],
  })

  bindResize(chart)
}

const initPieChart1 = (data = []) => {
  if (!pieChart1Ref.value) return
  const chart = echarts.getInstanceByDom(pieChart1Ref.value) || echarts.init(pieChart1Ref.value)
  const chartData = data.length > 0 ? data : [{ value: 0, name: '暂无数据' }]
  const denseMode = chartData.length > 4

  chart.setOption({
    tooltip: { trigger: 'item' },
    legend: denseMode
      ? {
          // 分类较多时使用右侧纵向滚动图例，避免和圆环及标签线互相覆盖。
          type: 'scroll',
          orient: 'vertical',
          right: 0,
          top: 'middle',
          height: '78%',
          pageIconSize: 10,
          formatter: (name) => (name && name.length > 10 ? `${name.slice(0, 10)}...` : name),
        }
      : {
          type: 'scroll',
          bottom: 0,
          left: 'center',
          width: '88%',
          pageIconSize: 10,
        },
    series: [
      {
        type: 'pie',
        center: denseMode ? ['30%', '50%'] : ['50%', '38%'],
        radius: denseMode ? ['22%', '40%'] : ['34%', '56%'],
        avoidLabelOverlap: true,
        label: denseMode
          ? { show: false }
          : {
              formatter: ({ name }) => (name && name.length > 12 ? `${name.slice(0, 12)}...` : name),
            },
        labelLine: {
          show: !denseMode,
        },
        data: chartData,
      },
    ],
  })

  bindResize(chart)
}

const initPieChart2 = (data = []) => {
  if (!pieChart2Ref.value) return
  const chart = echarts.getInstanceByDom(pieChart2Ref.value) || echarts.init(pieChart2Ref.value)
  chart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: '0', left: 'center' },
    series: [{ type: 'pie', radius: '70%', data }],
  })

  bindResize(chart)
}

watch(trendTab, () => {
  initTrendChart(statsData.value.activity_trend, trendTab.value)
})

onMounted(async () => {
  await nextTick()
  initTrendChart()
  initRadarChart()
  initPieChart1()
  initPieChart2()
  refreshAll()
})
</script>

<style scoped>
.admin-dashboard {
  --admin-ink: #183642;
  --admin-subtle: #6c7f86;
  --admin-line: rgba(24, 54, 66, 0.1);
  --admin-card: rgba(255, 252, 247, 0.94);
  padding: 0;
}

.hero-card {
  background:
    radial-gradient(circle at top right, rgba(255, 255, 255, 0.16), transparent 28%),
    linear-gradient(135deg, #183642, #355566 58%, #4c7580);
  border-radius: 28px;
  padding: 24px 26px;
  color: #f8fafc;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  box-shadow: 0 24px 50px rgba(24, 54, 66, 0.18);
}

.hero-left h2 {
  margin: 0;
  font-size: 24px;
}

.hero-left p {
  margin: 8px 0 0;
  color: #cbd5e1;
}

.stats-row {
  margin-bottom: 16px;
  row-gap: 16px;
}

.health-card {
  margin-bottom: 16px;
  border-radius: 26px;
}

.health-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.health-title {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
}

.health-meta {
  font-size: 12px;
  color: #94a3b8;
  margin-left: auto;
  margin-right: 8px;
}

.health-items {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.health-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 20px;
  border: 1px solid var(--admin-line);
  background: rgba(255, 255, 255, 0.86);
}

.health-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #94a3b8;
  box-shadow: 0 0 0 3px rgba(148, 163, 184, 0.15);
  flex-shrink: 0;
}

.health-dot.ok {
  background: #22c55e;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.18);
}

.health-dot.bad {
  background: #ef4444;
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.18);
}

.health-dot.unknown {
  background: #94a3b8;
  box-shadow: 0 0 0 3px rgba(148, 163, 184, 0.18);
}

.health-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.health-name {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.health-desc {
  font-size: 12px;
  color: #94a3b8;
}

.health-status {
  margin-left: auto;
  text-align: right;
  font-size: 12px;
  color: #64748b;
}

.health-text {
  font-weight: 600;
  color: #1f2937;
}

.health-latency {
  color: #94a3b8;
}

.alerts-card {
  margin-bottom: 16px;
  border-radius: 26px;
}

.alerts-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.alerts-tip {
  font-size: 12px;
  color: #94a3b8;
}

.alerts-row {
  row-gap: 12px;
}

.alert-item {
  border-radius: 20px;
  padding: 14px;
  border: 1px solid transparent;
  background: #f8fafc;
}

.alert-item.warning {
  background: #fffbeb;
  border-color: #fcd34d;
}

.alert-item.danger {
  background: #fef2f2;
  border-color: #fca5a5;
}

.alert-item.normal {
  background: rgba(15, 118, 110, 0.08);
  border-color: rgba(15, 118, 110, 0.18);
}

.alert-item.highlight {
  box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.2);
}

.alert-label {
  font-size: 13px;
  color: #64748b;
}

.alert-value {
  margin-top: 6px;
  font-size: 24px;
  font-weight: 600;
  color: #0f172a;
}

.alert-desc {
  margin-top: 4px;
  font-size: 12px;
  color: #94a3b8;
}

.stat-card {
  transition: all 0.3s;
  border-radius: 24px;
}

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.stat-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #1d2129;
  margin-bottom: 8px;
}

.stat-label {
  font-size: 14px;
  color: #86909c;
  margin-bottom: 4px;
}

.stat-total {
  font-size: 12px;
  color: #c9cdd4;
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-icon.blue {
  background: linear-gradient(135deg, #0f766e 0%, #146c94 100%);
  color: white;
}

.stat-icon.orange {
  background: linear-gradient(135deg, #d97706 0%, #f59e0b 100%);
  color: white;
}

.stat-icon.purple {
  background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%);
  color: white;
}

.stat-icon.yellow {
  background: linear-gradient(135deg, #ffa751 0%, #ffe259 100%);
  color: white;
}

.stat-icon.green {
  background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
  color: white;
}

.stat-icon.slate {
  background: linear-gradient(135deg, #64748b 0%, #334155 100%);
  color: white;
}

.chart-row {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #1d2129;
}

.bottom-charts {
  margin-bottom: 16px;
}

@media (max-width: 1200px) {
  .health-items {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .health-items {
    grid-template-columns: 1fr;
  }
}

:deep(.el-card) {
  border-radius: 26px;
  border: 1px solid var(--admin-line);
  background: var(--admin-card);
  box-shadow: 0 18px 40px rgba(24, 54, 66, 0.08);
}

:deep(.el-card__header) {
  padding: 16px 20px;
  border-bottom: 1px solid var(--admin-line);
  background: rgba(255, 255, 255, 0.56);
}

:deep(.el-card__body) {
  padding: 20px;
}

:deep(.el-radio-button__inner) {
  padding: 8px 15px;
}

:deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background-color: #0f766e !important;
  border-color: #0f766e !important;
}

:deep(.el-button) {
  border-radius: 14px;
}
</style>

