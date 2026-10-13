# 医疗知识图谱 Schema

## 1. Schema 作用
Schema 约束实体类型、关系类型与命名规则，减少抽取结果中的重复和歧义，支持检索与图谱展示。

## 2. 适用的数据来源
本 Schema 主要适配以下医疗数据来源：  
1. 药品说明书（PDF、图片或扫描件）  
2. 诊疗指南、诊断规范  
3. 医疗知识类文章或科普材料（可作为补充）  

## 3. 目标与用途
1. 支持 RAG 检索时的结构化检索（实体、关系、路径）  
2. 让图谱具备可解释性（每条关系可追溯来源）  
3. 方便后续评价与可视化展示  

## 4. 设计原则
1. 只定义“能稳定抽取”的实体与关系  
2. 中文为主，专有名词保留原名  
3. “核心 + 扩展”结构，先保证核心，再允许扩展  
4. 关系必须能追溯到具体文本证据  
5. 命名统一，避免同义词重复  

## 5. 实体类型表（核心 + 扩展）
表头：实体类型 | 定义 | 例子 | 备注

| 实体类型 | 定义 | 例子 | 备注 |
|---|---|---|---|
| Disease | 疾病名称 | 高血压、糖尿病 | 核心 |
| Symptom | 症状表现 | 头痛、眩晕 | 核心 |
| Drug | 药物名称（通用名） | 阿司匹林 | 核心 |
| Ingredient | 药物成分 | 乙酰水杨酸 | 核心 |
| Indication | 适应症 | 缓解轻中度疼痛 | 核心 |
| Contraindication | 禁忌症 | 对阿司匹林过敏者 | 核心 |
| Interaction | 相互作用条目 | 与华法林合用风险 | 核心 |
| Dosage | 用法用量 | 0.3-0.6g/次 | 核心 |
| SideEffect | 不良反应 | 胃肠道不适 | 核心 |
| Test | 检查项目 | 血压监测 | 核心 |
| Treatment | 治疗方式 | 生活方式干预 | 核心 |
| Procedure | 手术/操作 | 冠脉搭桥术 | 核心 |
| Department | 科室 | 心内科 | 核心 |
| Population | 人群对象 | 孕妇、儿童 | 核心 |
| Pathogen | 病原体 | 流感病毒 | 核心 |
| Biomarker | 医学指标 | 血糖、CRP | 核心 |
| Guideline | 诊疗指南 | 高血压诊疗指南 | 核心 |
| Device | 器械 | 血糖仪 | 核心 |
| Document | 文档/说明书 | 阿司匹林说明书 | 核心 |
| Organization | 机构 | 国家卫健委 | 扩展 |
| Person | 人 | 专家姓名 | 扩展 |
| Location | 地点 | 中国 | 扩展 |
| Time | 时间 | 2024 年 | 扩展 |
| Data | 数据 | 发病率 10% | 扩展 |
| Other | 无法归类 | 自定义概念 | 扩展 |

## 6. 关系类型表（标准化）
表头：关系 | 方向 | 说明 | 例子

| 关系 | 方向 | 说明 | 例子 |
|---|---|---|---|
| TREATS | Drug → Disease | 药物治疗疾病 | 阿司匹林 TREATS 高血压 |
| HAS_SYMPTOM | Disease → Symptom | 疾病表现症状 | 高血压 HAS_SYMPTOM 头痛 |
| HAS_SIDE_EFFECT | Drug → SideEffect | 药物不良反应 | 阿司匹林 HAS_SIDE_EFFECT 胃痛 |
| HAS_INGREDIENT | Drug → Ingredient | 药物包含成分 | 阿司匹林 HAS_INGREDIENT 乙酰水杨酸 |
| INDICATED_FOR | Drug → Indication | 药物适应症 | 阿司匹林 INDICATED_FOR 退热镇痛 |
| CONTRAINDICATED_FOR | Drug → Contraindication | 药物禁忌 | 阿司匹林 CONTRAINDICATED_FOR 过敏人群 |
| INTERACTS_WITH | Drug ↔ Drug | 药物相互作用 | 阿司匹林 INTERACTS_WITH 华法林 |
| REQUIRES_TEST | Disease → Test | 诊断需检查 | 高血压 REQUIRES_TEST 血压监测 |
| HAS_DOSAGE | Drug → Dosage | 药物用法用量 | 阿司匹林 HAS_DOSAGE 0.3-0.6g/次 |
| RELATED_TO | Entity ↔ Entity | 泛化关联 | 疾病 RELATED_TO 指标 |
| PART_OF | Entity → Entity | 组成或归属关系 | 心内科 PART_OF 医院 |
| CAUSES | Pathogen → Disease | 病原体导致疾病 | 流感病毒 CAUSES 流感 |

## 7. 属性规范（必填与可选）
1. `entity_name`：实体名称，必须统一命名  
2. `entity_type`：实体类型，必须在 Schema 内  
3. `description`：描述必须来自原文，禁止编造  
4. `source_id`：对应文本块或段落 ID  
5. `file_path`：来源文件路径  

## 8. 与 LightRAG 对齐（重要）
LightRAG 默认实体类型较通用，不够医疗领域使用。  
通过环境变量配置 Schema 实体类型，使抽取结果保持一致。

示例（写入 `.env` 的 `ENTITY_TYPES`）：  
```bash
ENTITY_TYPES=["Disease","Symptom","Drug","Ingredient","Indication","Contraindication","Interaction","Dosage","SideEffect","Test","Treatment","Procedure","Department","Population","Pathogen","Biomarker","Guideline","Device","Document","Organization","Person","Location","Time","Data","Other"]
```

未配置时会使用默认实体类型，需结合医疗领域数据验证抽取效果。
