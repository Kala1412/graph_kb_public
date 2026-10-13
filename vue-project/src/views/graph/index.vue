<template>
  <div class="graph-page">
    <section class="graph-hero">
      <div class="hero-copy">
        <span class="hero-kicker">Knowledge Graph</span>
        <h1>知识图谱页</h1>
        <p>
          将向量检索背后的实体、关系与结构化推理结果可视化，帮助你更直观地展示系统“为什么能回答这个问题”。
        </p>
        <div class="hero-tags">
          <span class="hero-tag">{{ hasSelectedKb ? '已选择知识库' : '等待选择知识库' }}</span>
          <span class="hero-tag">{{ rawGraphData.nodes.length }} 个节点</span>
          <span class="hero-tag accent">{{ rawGraphData.edges.length }} 条关系</span>
        </div>
      </div>
      <div class="hero-note">
        <span>当前模式</span>
        <strong>{{ filterForm.kb_id === 'all' ? allKbLabel : selectedKbName }}</strong>
        <p>支持选择单个知识库或聚合查看全部图谱，浏览实体关系与知识关联。</p>
      </div>
    </section>

    <section class="filter-panel">
      <div class="panel-header">
        <div>
          <span class="eyebrow">Control</span>
          <h2>图谱筛选与操作</h2>
        </div>
        <div class="header-actions">
          <el-button class="ghost-btn" :icon="Position" @click="resetLayout">重置布局</el-button>
          <el-button class="ghost-btn" :icon="Link" @click="openNeo4j">Neo4j Browser</el-button>
          <el-button
            class="primary-btn"
            type="primary"
            :icon="Refresh"
            @click="fetchGraphData"
            :disabled="!hasSelectedKb"
          >
            刷新图谱
          </el-button>
        </div>
      </div>

      <el-form :model="filterForm" label-position="top" class="filter-form">
        <div class="filter-grid">
          <el-form-item label="选择知识库">
            <el-select
              v-model="filterForm.kb_id"
              placeholder="请选择知识库"
              filterable
              @change="fetchGraphData"
            >
              <el-option :label="allKbLabel" value="all" />
              <el-option
                v-for="item in kbList"
                :key="item.id"
                :label="item.name"
                :value="item.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="搜索节点">
            <el-input
              v-model="filterForm.keyword"
              placeholder="输入节点名称关键词"
              clearable
              @keyup.enter="handleSearch"
            >
              <template #append>
                <el-button :icon="Search" @click="handleSearch">搜索</el-button>
              </template>
            </el-input>
          </el-form-item>
        </div>

        <el-form-item label="显示数量限制">
          <div class="slider-row">
            <el-slider
              v-model="filterForm.limit"
              :min="10"
              :max="2000"
              :step="10"
              show-input
              @change="fetchGraphData"
            />
          </div>
        </el-form-item>

        <el-form-item v-if="availableNodeTypes.length > 0" label="节点类型过滤">
          <div class="type-list">
            <el-checkbox-group v-model="filterForm.visibleNodeTypes">
              <el-checkbox
                v-for="typeObj in availableNodeTypes"
                :key="typeObj.value"
                :value="typeObj.value"
                :label="typeObj.label"
              />
            </el-checkbox-group>
          </div>
        </el-form-item>
      </el-form>
    </section>

    <section class="graph-panel" v-loading="loading">
      <div v-if="!hasSelectedKb" class="empty-state">
        <el-empty description="请先在上方选择一个知识库以加载图谱" />
      </div>
      <div v-else class="canvas-shell">
        <GraphCanvas
          ref="graphCanvasRef"
          :data="rawGraphData"
          :keyword="filterForm.keyword"
          :visible-node-types="filterForm.visibleNodeTypes"
        />
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api, { getKnowledgeGraph } from '@/api'
import { Link, Position, Refresh, Search } from '@element-plus/icons-vue'
import GraphCanvas from '@/components/GraphCanvas.vue'

const labelMap = {
  disease: '疾病',
  person: '人物',
  organization: '机构',
  concept: '概念',
  method: '方法',
  drug: '药物',
  symptom: '症状',
  ingredient: '成分',
  indication: '适应症',
  contraindication: '禁忌',
  interaction: '相互作用',
  dosage: '用法用量',
  sideeffect: '不良反应',
  test: '检查',
  treatment: '治疗方式',
  procedure: '手术/操作',
  department: '科室',
  population: '人群',
  pathogen: '病原体',
  biomarker: '指标',
  guideline: '诊疗指南',
  device: '器械',
  document: '文档',
  location: '地点',
  time: '时间',
  other: '其他',
  enzyme: '酶',
  hormone: '激素',
  category: '分类',
  data: '数据',
  artifact: '文献/表格',
  UNKNOWN: '未知类型',
  Disease: '疾病',
  Person: '人物',
  Organization: '机构',
  Concept: '概念',
  Method: '方法',
  Drug: '药物',
  Symptom: '症状',
  Ingredient: '成分',
  Indication: '适应症',
  Contraindication: '禁忌',
  Interaction: '相互作用',
  Dosage: '用法用量',
  SideEffect: '不良反应',
  Test: '检查',
  Treatment: '治疗方式',
  Procedure: '手术/操作',
  Department: '科室',
  Population: '人群',
  Pathogen: '病原体',
  Biomarker: '指标',
  Guideline: '诊疗指南',
  Device: '器械',
  Document: '文档',
  Location: '地点',
  Time: '时间',
  Other: '其他',
  Enzyme: '酶',
  Hormone: '激素',
  Category: '分类',
  Data: '数据',
  Artifact: '文献/表格',
  BodyPart: '身体部位',
  Check: '检查项目',
  Complication: '并发症',
  RiskFactor: '危险因素',
  Entity: '实体'
}

const translate = (key) => labelMap[key] || key

const graphCanvasRef = ref(null)
const loading = ref(false)
const kbList = ref([])
const rawGraphData = ref({ nodes: [], edges: [] })
const isAdmin = ref(localStorage.getItem('role') === 'admin')
const allKbLabel = computed(() => (isAdmin.value ? '全部知识库' : '我的全部知识库'))

const filterForm = reactive({
  kb_id: null,
  keyword: '',
  limit: 100,
  visibleNodeTypes: [],
  layout: 'force'
})

const hasSelectedKb = computed(
  () => filterForm.kb_id !== null && filterForm.kb_id !== undefined && filterForm.kb_id !== ''
)

const selectedKbName = computed(() => {
  const item = kbList.value.find((kb) => kb.id === filterForm.kb_id)
  return item?.name || '未选择'
})

const availableNodeTypes = computed(() => {
  const types = new Set()
  rawGraphData.value.nodes.forEach((node) => {
    if (node.label) types.add(node.label)
  })
  return Array.from(types).map((type) => ({
    value: type,
    label: translate(type)
  }))
})

const fetchKbList = async () => {
  try {
    const res = await api.get('/knowledge/list')
    kbList.value = res.data
  } catch (err) {
    ElMessage.error('获取知识库列表失败')
    console.error(err)
  }
}

const fetchGraphData = async () => {
  if (!hasSelectedKb.value) return
  loading.value = true
  try {
    const kbIdParam = filterForm.kb_id === 'all' ? null : filterForm.kb_id
    const res = await getKnowledgeGraph(kbIdParam, filterForm.limit)
    if (res.status === 'success' && res.data) {
      rawGraphData.value = res.data
      filterForm.visibleNodeTypes = Array.from(new Set(res.data.nodes.map((n) => n.label)))
    } else {
      rawGraphData.value = { nodes: [], edges: [] }
    }
  } catch (err) {
    console.error(err)
    ElMessage.error('获取知识图谱失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {}

const resetLayout = () => {
  graphCanvasRef.value?.resetLayout?.()
}

const openNeo4j = () => {
  window.open('http://localhost:7474', '_blank')
}

onMounted(async () => {
  await fetchKbList()
})
</script>

<style scoped>
.graph-page {
  --graph-ink: #15313b;
  --graph-subtle: #6b7f86;
  --graph-line: rgba(21, 49, 59, 0.1);
  --graph-card: rgba(255, 252, 247, 0.94);
  --graph-accent: #0f766e;
  min-height: 100%;
  padding: 4px 0 24px;
  color: var(--graph-ink);
}

.graph-hero,
.filter-panel,
.graph-panel {
  border-radius: 28px;
  border: 1px solid var(--graph-line);
  background: var(--graph-card);
  box-shadow: 0 18px 40px rgba(31, 49, 58, 0.06);
}

.graph-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 20px;
  padding: 28px;
  margin-bottom: 20px;
  background:
    radial-gradient(circle at top right, rgba(15, 118, 110, 0.16), transparent 30%),
    linear-gradient(135deg, #fffaf2 0%, #f3ede2 52%, #edf7f5 100%);
}

.hero-kicker,
.eyebrow {
  display: inline-block;
  margin-bottom: 10px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--graph-accent);
}

.graph-hero h1,
.panel-header h2,
.hero-note strong {
  margin: 0;
  font-family: Georgia, 'Times New Roman', serif;
}

.graph-hero h1 {
  font-size: clamp(30px, 4vw, 44px);
  line-height: 1.05;
}

.graph-hero p,
.hero-note p {
  margin: 12px 0 0;
  line-height: 1.8;
  color: var(--graph-subtle);
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
  color: var(--graph-accent);
  background: rgba(15, 118, 110, 0.12);
  border-color: transparent;
}

.hero-note {
  padding: 20px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.68);
  border: 1px solid rgba(21, 49, 59, 0.08);
}

.hero-note span {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--graph-subtle);
}

.hero-note strong {
  display: block;
  margin-top: 10px;
  font-size: 28px;
}

.filter-panel {
  padding: 24px;
  margin-bottom: 20px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 18px;
}

.panel-header h2 {
  font-size: 30px;
}

.header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.filter-grid {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 18px;
}

.slider-row {
  padding: 6px 4px 0;
}

.type-list {
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(21, 49, 59, 0.08);
}

.graph-panel {
  min-height: 720px;
  overflow: hidden;
}

.canvas-shell {
  height: 720px;
  padding: 0;
  background:
    radial-gradient(circle at 20% 20%, rgba(15, 118, 110, 0.06), transparent 25%),
    linear-gradient(180deg, rgba(248, 249, 245, 0.92), rgba(241, 245, 243, 0.94));
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 520px;
}

.primary-btn {
  min-height: 42px;
  border-radius: 18px;
}

.primary-btn.is-disabled,
.primary-btn.is-disabled:hover,
.primary-btn.is-disabled:focus {
  background: rgba(15, 118, 110, 0.26) !important;
  border-color: rgba(15, 118, 110, 0.16) !important;
  color: rgba(255, 255, 255, 0.94) !important;
  box-shadow: none !important;
}

.ghost-btn {
  min-height: 42px;
  border-radius: 18px;
  border-color: rgba(21, 49, 59, 0.12);
  background: rgba(255, 255, 255, 0.72);
}

:deep(.el-input__wrapper),
:deep(.el-select__wrapper),
:deep(.el-textarea__inner) {
  border-radius: 20px;
  box-shadow: 0 0 0 1px rgba(21, 49, 59, 0.08) inset !important;
}

:deep(.el-form-item__label) {
  font-size: 13px;
  font-weight: 700;
  color: var(--graph-ink);
}

:deep(.el-button--primary) {
  --el-button-bg-color: #0f766e;
  --el-button-border-color: #0f766e;
  --el-button-hover-bg-color: #0d655e;
  --el-button-hover-border-color: #0d655e;
}

:deep(.el-checkbox-group) {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
}

@media (max-width: 1024px) {
  .graph-hero,
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .panel-header {
    flex-direction: column;
  }
}

@media (max-width: 700px) {
  .graph-hero,
  .filter-panel,
  .graph-panel {
    border-radius: 22px;
  }

  .canvas-shell {
    height: 620px;
  }
}
</style>
