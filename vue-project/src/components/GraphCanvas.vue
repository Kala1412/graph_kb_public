<template>
  <div class="graph-canvas-wrapper" ref="wrapperRef">
    <div class="graph-canvas-container" ref="chartRef" v-loading="loading"></div>
    <div class="canvas-actions">
      <el-tooltip content="全屏查看" placement="top">
        <el-button 
          :icon="FullScreen" 
          circle 
          @click="toggleFullscreen"
          class="fullscreen-btn"
        />
      </el-tooltip>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { FullScreen } from '@element-plus/icons-vue' // 💡 引入图标

const props = defineProps({
  data: {
    type: Object,
    default: () => ({ nodes: [], edges: [] }),
  },
  loading: {
    type: Boolean,
    default: false,
  },
  keyword: {
    type: String,
    default: '',
  },
  visibleNodeTypes: {
    type: Array,
    default: () => [],
  },
  highlightNodes: {
    type: Array,
    default: () => [],
  },
  highlightEdges: {
    type: Array,
    default: () => [],
  },
})

const wrapperRef = ref(null)
const chartRef = ref(null)
let myChart = null

// 完整的中英文映射（匹配 Neo4j 实际返回的小写 entity_type）
const labelMap = {
  'disease': '疾病',
  'person': '人物',
  'organization': '机构',
  'concept': '概念',
  'method': '方法',
  'drug': '药物',
  'symptom': '症状',
  'ingredient': '成分',
  'indication': '适应症',
  'contraindication': '禁忌',
  'interaction': '相互作用',
  'dosage': '用法用量',
  'sideeffect': '不良反应',
  'test': '检查',
  'treatment': '治疗方式',
  'procedure': '手术/操作',
  'department': '科室',
  'population': '人群',
  'pathogen': '病原体',
  'biomarker': '指标',
  'guideline': '诊疗指南',
  'device': '器械',
  'document': '文档',
  'location': '地点',
  'time': '时间',
  'other': '其他',
  'enzyme': '酶',
  'hormone': '激素',
  'category': '分类',
  'data': '数据',
  'artifact': '文献/表格',
  'UNKNOWN': '未知类型',
  // 兼容大写开头
  'Disease': '疾病',
  'Person': '人物',
  'Organization': '机构',
  'Concept': '概念',
  'Method': '方法',
  'Drug': '药物',
  'Symptom': '症状',
  'Ingredient': '成分',
  'Indication': '适应症',
  'Contraindication': '禁忌',
  'Interaction': '相互作用',
  'Dosage': '用法用量',
  'SideEffect': '不良反应',
  'Test': '检查',
  'Treatment': '治疗方式',
  'Procedure': '手术/操作',
  'Department': '科室',
  'Population': '人群',
  'Pathogen': '病原体',
  'Biomarker': '指标',
  'Guideline': '诊疗指南',
  'Device': '器械',
  'Document': '文档',
  'Location': '地点',
  'Time': '时间',
  'Other': '其他',
  'Enzyme': '酶',
  'Hormone': '激素',
  'Category': '分类',
  'Data': '数据',
  'Artifact': '文献/表格',
  // 旧映射保留兼容
  'BodyPart': '身体部位',
  'Check': '检查项目',
  'Complication': '并发症',
  'RiskFactor': '危险因素',
  'Entity': '实体',
  'TREATS': '治疗',
  'HAS_SYMPTOM': '表现症状',
  'HAS_SIDE_EFFECT': '不良反应',
  'HAS_INGREDIENT': '包含成分',
  'INDICATED_FOR': '适应症',
  'CONTRAINDICATED_FOR': '禁忌',
  'INTERACTS_WITH': '相互作用',
  'REQUIRES_TEST': '需要检查',
  'HAS_DOSAGE': '用法用量',
  'PART_OF': '组成/归属',
  'CAUSES': '导致',
  // 兼容旧关系类型
  'AFFECTS': '影响/累及',
  'CAUSED_BY': '由...引起',
  'THERAPY': '治疗方法',
  'USE_DRUG': '使用药物',
  'NEED_CHECK': '需要检查',
  'LEADS_TO': '导致/引发',
  'BELONGS_TO': '属于科室',
  'RECORDED_IN': '记录于',
  'OCCUR_TIME': '发生时间',
  'RELATED_TO': '相关',
  'DIRECTED': '关联',
}

const translate = (key) => labelMap[key] || key

const normalizeName = (val) => String(val || '').trim().toLowerCase()

const buildNameIndex = (nodes) => {
  const index = new Map()
  nodes.forEach((node) => {
    const key = normalizeName(node?.name)
    if (!key) return
    if (!index.has(key)) {
      index.set(key, new Set())
    }
    index.get(key).add(String(node.id))
  })
  return index
}

const getCategories = (nodes) => {
  const types = new Set(nodes.map((n) => n.label))
  return Array.from(types).map((type) => ({ name: translate(type) }))
}

const renderChart = () => {
  if (!chartRef.value || !props.data.nodes?.length) {
    myChart?.clear()
    return
  }

  if (!myChart) {
    myChart = echarts.init(chartRef.value)
  }

  let typeFilteredNodes = props.data.nodes
  if (props.visibleNodeTypes.length > 0) {
    typeFilteredNodes = typeFilteredNodes.filter((n) => props.visibleNodeTypes.includes(n.label))
  }

  const nameIndex = buildNameIndex(typeFilteredNodes)
  const highlightIds = new Set()
  const highlightEdgeStrict = new Set()
  const highlightEdgeLoose = new Set()

  const addEdgeKey = (source, target, relation) => {
    if (!source || !target) return
    if (relation) {
      highlightEdgeStrict.add(`${source}|${target}|${relation}`)
    } else {
      highlightEdgeLoose.add(`${source}|${target}`)
    }
  }

  const highlightSource = props.highlightNodes || []
  highlightSource.forEach((name) => {
    const ids = nameIndex.get(normalizeName(name))
    if (!ids) return
    ids.forEach((id) => highlightIds.add(id))
  })

  ;(props.highlightEdges || []).forEach((edge) => {
    const sourceIds = nameIndex.get(normalizeName(edge?.source)) || new Set()
    const targetIds = nameIndex.get(normalizeName(edge?.target)) || new Set()
    const relation = edge?.relation ? String(edge.relation).toLowerCase() : ''
    sourceIds.forEach((sourceId) => {
      targetIds.forEach((targetId) => {
        highlightIds.add(sourceId)
        highlightIds.add(targetId)
        addEdgeKey(sourceId, targetId, relation)
        addEdgeKey(targetId, sourceId, relation)
      })
    })
  })

  let finalNodes = typeFilteredNodes
  if (props.keyword) {
    const kw = props.keyword.toLowerCase()

    const matchedNodes = typeFilteredNodes.filter(
      (n) => n.name && n.name.toLowerCase().includes(kw)
    )
    const matchedIds = new Set(matchedNodes.map((n) => String(n.id)))
    matchedIds.forEach((id) => highlightIds.add(id))

    if (matchedIds.size > 0) {
      // 搜索结果保留匹配节点的直接邻居。
      const neighborIds = new Set()
      const typeFilteredIds = new Set(typeFilteredNodes.map((n) => String(n.id)))

      ;(props.data.edges || []).forEach((edge) => {
        const src = String(edge.source)
        const tgt = String(edge.target)
        if (matchedIds.has(src) && typeFilteredIds.has(tgt)) {
          neighborIds.add(tgt)
        }
        if (matchedIds.has(tgt) && typeFilteredIds.has(src)) {
          neighborIds.add(src)
        }
      })

      const keepIds = new Set([...matchedIds, ...neighborIds])
      finalNodes = typeFilteredNodes.filter((n) => keepIds.has(String(n.id)))
    } else {
      finalNodes = []
    }
  }

  // 路径模式仅展示路径节点及其邻居。
  if (!props.keyword && highlightIds.size > 0) {
    const keepIds = new Set(highlightIds)
    ;(props.data.edges || []).forEach((edge) => {
      const src = String(edge.source)
      const tgt = String(edge.target)
      if (keepIds.has(src) || keepIds.has(tgt)) {
        keepIds.add(src)
        keepIds.add(tgt)
      }
    })
    finalNodes = typeFilteredNodes.filter((n) => keepIds.has(String(n.id)))
  }

  if (finalNodes.length === 0) {
    myChart.clear()
    return
  }

  const nodeIds = new Set(finalNodes.map((n) => String(n.id)))
  const categories = getCategories(finalNodes)
  const categoryNames = categories.map((c) => c.name)

  const option = {
    backgroundColor: '#ffffff',
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        if (params.dataType === 'node') {
          return `<div style="padding:5px">
                    <b>名称:</b> ${params.data.name}<br/>
                    <b>类型:</b> ${translate(params.data.label)}
                  </div>`
        }
        return `关系: ${params.data.name}`
      },
    },
    legend: {
      data: categoryNames,
      orient: 'horizontal',
      top: 10,
    },
    series: [
      {
        name: '知识图谱',
        type: 'graph',
        layout: 'force',
        data: finalNodes.map((node) => {
          const id = String(node.id)
          const isHighlight = highlightIds.has(id)
          return {
            ...node,
            id: id,
            symbolSize: isHighlight
              ? 45
              : ['Disease', 'disease'].includes(node.label)
              ? 40
              : ['Entity', 'entity', 'organization'].includes(node.label)
              ? 35
              : 25,
            category: categoryNames.indexOf(translate(node.label)),
            label: {
              show: true,
              position: 'inside',
              color: '#fff',
              fontSize: isHighlight ? 12 : 10,
              fontWeight: isHighlight ? 'bold' : 'normal',
              textBorderColor: 'auto', // 添加文字描边增强对比度
              textBorderWidth: 1
            },
            itemStyle: isHighlight
              ? {
                  borderColor: '#ff6600',
                  borderWidth: 3,
                  shadowBlur: 10,
                  shadowColor: 'rgba(255,102,0,0.5)',
                }
              : {},
          }
        }),
        links: (props.data.edges || [])
          .filter((edge) => nodeIds.has(String(edge.source)) && nodeIds.has(String(edge.target)))
          .map((edge) => {
            const source = String(edge.source)
            const target = String(edge.target)
            const relation = String(edge.type || '').toLowerCase()
            const isHighlight =
              highlightEdgeStrict.has(`${source}|${target}|${relation}`) ||
              highlightEdgeStrict.has(`${target}|${source}|${relation}`) ||
              highlightEdgeLoose.has(`${source}|${target}`) ||
              highlightEdgeLoose.has(`${target}|${source}`)
            return {
              source,
              target,
              relationName: translate(edge.type),
              label: {
                show: true,
                formatter: (params) => params.data.relationName,
                fontSize: isHighlight ? 11 : 10,
                fontWeight: isHighlight ? 'bold' : 'normal',
                color: isHighlight ? '#f97316' : '#333',
                textBorderColor: '#fff',
                textBorderWidth: 2,
              },
              lineStyle: isHighlight
                ? {
                    width: 5,
                    color: '#f97316',
                    opacity: 0.9,
                  }
                : undefined,
            }
          }),
        categories: categories,
        roam: true,
        draggable: true,
        force: {
          repulsion: 800,
          edgeLength: 150,
          gravity: 0.1,
          layoutAnimation: true,
        },
        lineStyle: {
          width: 2,
          color: '#aaa',
          curveness: 0.2,
          opacity: 0.7,
        },
        emphasis: {
          focus: 'adjacency',
          lineStyle: { width: 4 },
        },
      },
    ],
  }

  myChart.setOption(option, true)
}

const toggleFullscreen = () => {
  if (!document.fullscreenElement) {
    wrapperRef.value?.requestFullscreen().catch(err => {
      console.error(`全屏失败: ${err.message}`)
    })
  } else {
    document.exitFullscreen()
  }
}

const resetLayout = () => {
  myChart?.dispatchAction({ type: 'restore' })
}

defineExpose({ resetLayout })

const handleResize = () => {
  if (myChart) {
    myChart.resize()
  }
}

watch(
  () => [props.data, props.keyword, props.visibleNodeTypes, props.highlightNodes, props.highlightEdges],
  () => nextTick(renderChart),
  { deep: true }
)

onMounted(() => {
  renderChart()
  window.addEventListener('resize', handleResize)
  document.addEventListener('fullscreenchange', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  document.removeEventListener('fullscreenchange', handleResize) // 💡 移除监听
  myChart?.dispose()
  myChart = null
})
</script>

<style scoped>
.graph-canvas-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
  background: #fff;
}

.graph-canvas-container {
  width: 100%;
  height: 100%;
  min-height: 400px;
}

.canvas-actions {
  position: absolute;
  right: 20px;
  bottom: 20px;
  z-index: 10;
}

.fullscreen-btn {
  background: rgba(255, 255, 255, 0.8);
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.1);
}

.fullscreen-btn:hover {
  transform: scale(1.1);
  background: #fff;
}

/* 全屏状态下的容器高度 */
:fullscreen .graph-canvas-container {
  height: 100vh !important;
}
</style>
