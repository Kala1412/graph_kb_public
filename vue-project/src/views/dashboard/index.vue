<template>
  <div class="dashboard-page">
    <section class="dashboard-hero">
      <div class="hero-copy">
        <span class="hero-kicker">Analytics Console</span>
        <h1>分析页</h1>
        <p>
          查看知识库活跃度、文件处理状态与问答使用情况，持续追踪知识积累与检索使用情况。
        </p>
        <div class="hero-tags">
          <span class="hero-tag">{{ roleLabel }}</span>
          <span class="hero-tag">最近 14 天活跃趋势</span>
          <span class="hero-tag accent">{{ statsLoading ? '数据同步中' : '数据已更新' }}</span>
        </div>
      </div>
      <div class="hero-side">
        <div class="signal-card">
          <span>知识库健康度</span>
          <strong>{{ indexedRate }}%</strong>
          <p>按可用文件数 / 总知识库规模做简要估算，用于首屏快速感知当前数据沉淀程度。</p>
        </div>
      </div>
    </section>

    <section class="stats-grid">
      <article v-for="card in overviewCards" :key="card.label" class="metric-card">
        <div class="metric-top">
          <div class="metric-icon" :class="card.tone">
            <el-icon><component :is="card.icon" /></el-icon>
          </div>
          <span class="metric-chip">{{ card.hint }}</span>
        </div>
        <strong>{{ card.value }}</strong>
        <h3>{{ card.label }}</h3>
        <p>{{ card.description }}</p>
      </article>
    </section>

    <el-row :gutter="20" class="dashboard-grid">
      <el-col :xs="24" :xl="16">
        <section class="panel chart-panel feature-panel">
          <div class="panel-header">
            <div>
              <span class="eyebrow">Trend</span>
              <h2>我的活跃趋势</h2>
            </div>
            <el-radio-group v-model="trendTab" size="large" class="trend-switch">
              <el-radio-button label="访问趋势" />
              <el-radio-button label="月访问量" />
            </el-radio-group>
          </div>
          <p class="panel-desc">
            同时展示新增会话与新增文件。切换“月访问量”后会把最近 14 天数据汇总成累计观察视角。
          </p>
          <div ref="trendChartRef" class="chart chart-lg"></div>
        </section>
      </el-col>

      <el-col :xs="24" :xl="8">
        <section class="panel side-panel">
          <div class="panel-header compact">
            <div>
              <span class="eyebrow">Snapshot</span>
              <h2>运行摘要</h2>
            </div>
          </div>

          <div class="snapshot-list">
            <div class="snapshot-item">
              <span>已索引文件</span>
              <strong>{{ statsData.cards.indexed_files }}</strong>
            </div>
            <div class="snapshot-item">
              <span>总会话数</span>
              <strong>{{ statsData.cards.total_sessions }}</strong>
            </div>
            <div class="snapshot-item">
              <span>总消息数</span>
              <strong>{{ statsData.cards.total_messages }}</strong>
            </div>
            <div class="snapshot-item">
              <span>近 7 天提问</span>
              <strong>{{ statsData.cards.questions_7d }}</strong>
            </div>
          </div>

          <div class="mini-note">
            <span class="mini-note-title">展示建议</span>
            <p>
              结合问答次数、文件索引规模与图谱覆盖情况，了解知识库的使用趋势与待完善内容。
            </p>
          </div>
        </section>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="dashboard-grid secondary">
      <el-col :xs="24" :lg="8">
        <section class="panel chart-panel">
          <div class="panel-header compact">
            <div>
              <span class="eyebrow">Radar</span>
              <h2>核心指标画像</h2>
            </div>
          </div>
          <div ref="radarChartRef" class="chart chart-md"></div>
        </section>
      </el-col>

      <el-col :xs="24" :lg="8">
        <section class="panel chart-panel">
          <div class="panel-header compact">
            <div>
              <span class="eyebrow">Knowledge</span>
              <h2>知识库文件分布</h2>
            </div>
          </div>
          <div ref="pieChart1Ref" class="chart chart-md"></div>
        </section>
      </el-col>

      <el-col :xs="24" :lg="8">
        <section class="panel chart-panel">
          <div class="panel-header compact">
            <div>
              <span class="eyebrow">Status</span>
              <h2>文件状态分布</h2>
            </div>
          </div>
          <div ref="pieChart2Ref" class="chart chart-md"></div>
        </section>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { ChatDotRound, Collection, DataAnalysis, Files, Message } from '@element-plus/icons-vue'
import { getDashboardStats } from '@/api/index'

const trendTab = ref('访问趋势')
const trendChartRef = ref(null)
const radarChartRef = ref(null)
const pieChart1Ref = ref(null)
const pieChart2Ref = ref(null)
const chartInstances = []
const statsLoading = ref(false)

const statsData = ref({
  cards: {
    total_users: 0,
    total_kb: 0,
    total_files: 0,
    total_sessions: 0,
    total_messages: 0,
    storage_mb: 0,
    questions_7d: 0,
    indexed_files: 0
  },
  kb_file_distribution: [],
  status_distribution: [],
  activity_trend: []
})

const roleLabel = computed(() =>
  localStorage.getItem('role') === 'admin' ? '管理员视角' : '个人视角'
)

const indexedRate = computed(() => {
  const totalBase = Math.max(statsData.value.cards.total_kb || 0, 1)
  return Math.min(100, Math.round(((statsData.value.cards.indexed_files || 0) / totalBase) * 100))
})

const overviewCards = computed(() => [
  {
    label: '近 7 天提问',
    value: statsData.value.cards.questions_7d,
    hint: '互动热度',
    description: '衡量近期问答活跃度，适合展示系统真实使用频率。',
    icon: DataAnalysis,
    tone: 'tone-ocean'
  },
  {
    label: '知识库总数',
    value: statsData.value.cards.total_kb,
    hint: '数据沉淀',
    description: '反映用户当前沉淀下来的知识库规模与资料组织能力。',
    icon: Collection,
    tone: 'tone-gold'
  },
  {
    label: '会话总数',
    value: statsData.value.cards.total_sessions,
    hint: '交互规模',
    description: '显示历史问答轮次沉淀，说明系统已经具备连续使用场景。',
    icon: ChatDotRound,
    tone: 'tone-mint'
  },
  {
    label: '消息总数',
    value: statsData.value.cards.total_messages,
    hint: '对话记录',
    description: '代表用户与 Agent 的总交互量，是展示系统可用性的直观指标。',
    icon: Message,
    tone: 'tone-rose'
  },
  {
    label: '文件总量',
    value: statsData.value.cards.total_files,
    hint: '资料规模',
    description: '用于展示知识库背后的基础文档规模和数据来源丰富度。',
    icon: Files,
    tone: 'tone-slate'
  }
])

const bindResize = (chart) => {
  if (!chart || chart.__resizeBound) return
  chart.__resizeBound = true
  const resizeHandler = () => chart.resize()
  chart.__resizeHandler = resizeHandler
  window.addEventListener('resize', resizeHandler)
  chartInstances.push(chart)
}

const refreshCharts = () => {
  initTrendChart(statsData.value.activity_trend)
  initPieChart1(statsData.value.kb_file_distribution)
  initPieChart2(statsData.value.status_distribution)
  initRadarChart(statsData.value.cards)
}

const fetchStats = async () => {
  statsLoading.value = true
  try {
    const response = await getDashboardStats()
    statsData.value = {
      ...statsData.value,
      ...response.data,
      cards: {
        ...statsData.value.cards,
        ...response.data?.cards
      }
    }
    refreshCharts()
  } catch (error) {
    console.error('数据加载失败:', error)
  } finally {
    statsLoading.value = false
  }
}

const cumulative = (items) => {
  let sum = 0
  return items.map((value) => {
    sum += value
    return sum
  })
}

const initTrendChart = (data = []) => {
  if (!trendChartRef.value) return
  const chart = echarts.getInstanceByDom(trendChartRef.value) || echarts.init(trendChartRef.value)
  const days = data.map((item) => item.date.split('-').slice(1).join('/'))
  const messageData = data.map((item) => item.messages || 0)
  const fileData = data.map((item) => item.files || 0)
  const line1 = trendTab.value === '月访问量' ? cumulative(messageData) : messageData
  const line2 = trendTab.value === '月访问量' ? cumulative(fileData) : fileData

  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(16, 30, 34, 0.88)',
      borderWidth: 0,
      textStyle: { color: '#f8fafc' }
    },
    legend: {
      data: ['新增对话', '新增文件'],
      bottom: 0,
      textStyle: { color: '#627178' }
    },
    grid: { left: 18, right: 18, top: 24, bottom: 42, containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: days,
      axisTick: { show: false },
      axisLine: { lineStyle: { color: 'rgba(21, 49, 59, 0.12)' } },
      axisLabel: { color: '#6b7f86' }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#6b7f86' },
      splitLine: { lineStyle: { color: 'rgba(21, 49, 59, 0.08)', type: 'dashed' } }
    },
    series: [
      {
        name: '新增对话',
        type: 'line',
        smooth: true,
        symbolSize: 7,
        itemStyle: { color: '#0f766e' },
        lineStyle: { width: 3, color: '#0f766e' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(15, 118, 110, 0.28)' },
            { offset: 1, color: 'rgba(15, 118, 110, 0.02)' }
          ])
        },
        data: line1
      },
      {
        name: '新增文件',
        type: 'line',
        smooth: true,
        symbolSize: 7,
        itemStyle: { color: '#d97706' },
        lineStyle: { width: 3, color: '#d97706' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(217, 119, 6, 0.24)' },
            { offset: 1, color: 'rgba(217, 119, 6, 0.02)' }
          ])
        },
        data: line2
      }
    ]
  })

  bindResize(chart)
}

const getRadarMax = (value) => Math.max(1, Math.ceil((value || 0) * 1.2))

const initRadarChart = (cards = statsData.value.cards) => {
  if (!radarChartRef.value) return
  const chart = echarts.getInstanceByDom(radarChartRef.value) || echarts.init(radarChartRef.value)

  const values = [
    cards.questions_7d || 0,
    cards.total_kb || 0,
    cards.indexed_files || 0,
    cards.total_sessions || 0,
    cards.total_messages || 0
  ]

  chart.setOption({
    backgroundColor: 'transparent',
    radar: {
      indicator: [
        { name: '近7天提问', max: getRadarMax(cards.questions_7d) },
        { name: '知识库数', max: getRadarMax(cards.total_kb) },
        { name: '可用文件数', max: getRadarMax(cards.indexed_files) },
        { name: '会话数', max: getRadarMax(cards.total_sessions) },
        { name: '消息数', max: getRadarMax(cards.total_messages) }
      ],
      radius: '62%',
      axisName: { color: '#627178' },
      splitLine: { lineStyle: { color: 'rgba(21, 49, 59, 0.12)' } },
      splitArea: {
        areaStyle: {
          color: ['rgba(15, 118, 110, 0.03)', 'rgba(15, 118, 110, 0.08)']
        }
      }
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: values,
            name: '指标画像',
            areaStyle: { color: 'rgba(15, 118, 110, 0.24)' },
            lineStyle: { color: '#0f766e', width: 2 },
            itemStyle: { color: '#0f766e' }
          }
        ]
      }
    ]
  })

  bindResize(chart)
}

const initPieChart1 = (data = []) => {
  if (!pieChart1Ref.value) return
  const chart = echarts.getInstanceByDom(pieChart1Ref.value) || echarts.init(pieChart1Ref.value)
  const chartData = data.length > 0 ? data : [{ value: 0, name: '暂无数据' }]
  const denseMode = chartData.length > 4

  chart.setOption({
    color: ['#0f766e', '#d97706', '#146c94', '#be185d', '#64748b', '#16a34a'],
    tooltip: { trigger: 'item' },
    legend: denseMode
      ? {
          type: 'scroll',
          orient: 'vertical',
          right: 0,
          top: 'middle',
          height: '76%',
          textStyle: { color: '#6b7f86' }
        }
      : {
          type: 'scroll',
          bottom: 0,
          left: 'center',
          textStyle: { color: '#6b7f86' }
        },
    series: [
      {
        type: 'pie',
        center: denseMode ? ['30%', '50%'] : ['50%', '42%'],
        radius: denseMode ? ['24%', '42%'] : ['38%', '58%'],
        avoidLabelOverlap: true,
        label: denseMode
          ? { show: false }
          : {
              color: '#627178',
              formatter: ({ name }) => (name && name.length > 12 ? `${name.slice(0, 12)}...` : name)
            },
        labelLine: { show: !denseMode },
        data: chartData
      }
    ]
  })

  bindResize(chart)
}

const initPieChart2 = (data = []) => {
  if (!pieChart2Ref.value) return
  const chart = echarts.getInstanceByDom(pieChart2Ref.value) || echarts.init(pieChart2Ref.value)
  chart.setOption({
    color: ['#0f766e', '#146c94', '#d97706', '#be185d', '#64748b'],
    tooltip: { trigger: 'item' },
    legend: {
      bottom: 0,
      left: 'center',
      textStyle: { color: '#6b7f86' }
    },
    series: [
      {
        type: 'pie',
        radius: ['40%', '68%'],
        data: data.length > 0 ? data : [{ value: 0, name: '暂无数据' }],
        label: { color: '#627178' }
      }
    ]
  })

  bindResize(chart)
}

onMounted(async () => {
  await nextTick()
  initTrendChart()
  initRadarChart()
  initPieChart1()
  initPieChart2()
  fetchStats()
})

onBeforeUnmount(() => {
  chartInstances.forEach((chart) => {
    if (chart?.__resizeHandler) {
      window.removeEventListener('resize', chart.__resizeHandler)
    }
    chart?.dispose?.()
  })
})
</script>

<style scoped>
.dashboard-page {
  --dash-ink: #15313b;
  --dash-subtle: #6b7f86;
  --dash-line: rgba(21, 49, 59, 0.1);
  --dash-card: rgba(255, 252, 247, 0.94);
  --dash-accent: #0f766e;
  --dash-bg: linear-gradient(180deg, #f5f0e8 0%, #f6faf8 36%, #f7f8f4 100%);
  min-height: 100%;
  padding: 4px 0 24px;
  color: var(--dash-ink);
}

.dashboard-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 20px;
  padding: 28px;
  margin-bottom: 20px;
  border: 1px solid var(--dash-line);
  border-radius: 30px;
  background:
    radial-gradient(circle at top right, rgba(15, 118, 110, 0.16), transparent 30%),
    var(--dash-bg);
  box-shadow: 0 24px 48px rgba(33, 52, 61, 0.08);
}

.hero-kicker,
.eyebrow {
  display: inline-block;
  margin-bottom: 10px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--dash-accent);
}

.dashboard-hero h1,
.panel-header h2,
.metric-card h3,
.signal-card strong {
  margin: 0;
  font-family: Georgia, 'Times New Roman', serif;
}

.dashboard-hero h1 {
  font-size: clamp(30px, 4vw, 46px);
  line-height: 1.05;
}

.dashboard-hero p {
  max-width: 720px;
  margin: 12px 0 0;
  line-height: 1.8;
  color: var(--dash-subtle);
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
  color: var(--dash-accent);
  background: rgba(15, 118, 110, 0.12);
  border-color: transparent;
}

.hero-side {
  display: flex;
  align-items: stretch;
}

.signal-card {
  width: 100%;
  padding: 20px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.68);
  border: 1px solid rgba(21, 49, 59, 0.08);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
}

.signal-card span {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--dash-subtle);
}

.signal-card strong {
  display: block;
  margin-top: 10px;
  font-size: 50px;
  line-height: 1;
  color: var(--dash-accent);
}

.signal-card p {
  margin: 12px 0 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--dash-subtle);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.metric-card,
.panel {
  border: 1px solid var(--dash-line);
  border-radius: 26px;
  background: var(--dash-card);
  box-shadow: 0 18px 40px rgba(31, 49, 58, 0.06);
}

.metric-card {
  padding: 18px;
}

.metric-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;
}

.metric-icon {
  display: grid;
  place-items: center;
  width: 50px;
  height: 50px;
  border-radius: 18px;
  font-size: 22px;
}

.tone-ocean {
  color: #0f766e;
  background: rgba(15, 118, 110, 0.12);
}

.tone-gold {
  color: #b45309;
  background: rgba(245, 158, 11, 0.14);
}

.tone-mint {
  color: #16a34a;
  background: rgba(34, 197, 94, 0.12);
}

.tone-rose {
  color: #be185d;
  background: rgba(244, 114, 182, 0.14);
}

.tone-slate {
  color: #334155;
  background: rgba(148, 163, 184, 0.18);
}

.metric-chip {
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(21, 49, 59, 0.06);
  font-size: 12px;
  color: var(--dash-subtle);
}

.metric-card strong {
  display: block;
  font-size: 34px;
  line-height: 1;
}

.metric-card h3 {
  margin-top: 14px;
  font-size: 22px;
}

.metric-card p,
.panel-desc,
.mini-note p {
  margin: 10px 0 0;
  color: var(--dash-subtle);
  line-height: 1.7;
  font-size: 13px;
}

.dashboard-grid {
  margin-bottom: 20px;
}

.panel {
  height: 100%;
  padding: 24px;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.panel-header.compact {
  margin-bottom: 6px;
}

.panel-header h2 {
  font-size: 30px;
}

.feature-panel {
  min-height: 520px;
}

.trend-switch {
  flex-shrink: 0;
}

.chart {
  width: 100%;
}

.chart-lg {
  height: 390px;
}

.chart-md {
  height: 300px;
}

.snapshot-list {
  display: grid;
  gap: 12px;
  margin-top: 18px;
}

.snapshot-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.74);
  border: 1px solid rgba(21, 49, 59, 0.08);
}

.snapshot-item span {
  color: var(--dash-subtle);
}

.snapshot-item strong {
  font-size: 24px;
  font-family: Georgia, 'Times New Roman', serif;
}

.mini-note {
  margin-top: 18px;
  padding: 16px 18px;
  border-radius: 20px;
  background: rgba(15, 118, 110, 0.08);
}

.mini-note-title {
  display: inline-block;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--dash-accent);
}

:deep(.el-radio-group) {
  flex-wrap: wrap;
}

:deep(.el-radio-button__inner) {
  min-height: 40px;
  padding: 0 16px;
  border-radius: 999px !important;
  border: 1px solid rgba(21, 49, 59, 0.08);
  background: rgba(255, 255, 255, 0.7);
  box-shadow: none;
}

:deep(.el-radio-button:first-child .el-radio-button__inner),
:deep(.el-radio-button:last-child .el-radio-button__inner) {
  border-radius: 999px;
}

:deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background: #0f766e !important;
  border-color: #0f766e !important;
  box-shadow: none;
}

@media (max-width: 1400px) {
  .stats-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1024px) {
  .dashboard-hero {
    grid-template-columns: 1fr;
  }

  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .dashboard-hero,
  .panel,
  .metric-card {
    border-radius: 22px;
  }

  .panel-header {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 600px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }

  .dashboard-hero {
    padding: 24px 20px;
  }
}
</style>
