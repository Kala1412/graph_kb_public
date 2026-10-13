# 医疗实体关系抽取规范

## 1. 这份规范的作用
抽取规范用于保证“不同人、不同文档、不同批次”抽取出来的结果是一致的。  
它明确了：  
1. 先如何处理文档  
2. 再如何识别实体  
3. 最后如何建立关系  

## 2. 基本工作流程（推荐顺序）
1. 文档预处理：把 PDF/图片转成结构清晰的 Markdown  
2. 章节识别：保留“适应症、禁忌、不良反应”等标题  
3. 实体抽取：根据 Schema 识别实体  
4. 关系抽取：根据章节语义映射关系  
5. 记录证据：每条关系必须能回溯原文  

## 3. 文档预处理规范
1. Markdown 必须保留章节标题  
2. 表格优先转成“句子化文本”  
3. 删除无用页眉页脚和页码  
4. 保留单位与数值（mg、mL、mmHg 等）  

## 4. 实体抽取规则
1. 识别明确名词短语，不抽取含糊代词  
2. 品牌名与通用名统一为通用名  
3. 专有名词保留原名，不强行翻译  
4. 单位与数值保持原文，不四舍五入  
5. 无法归类的实体使用 `Other`  

## 5. 关系抽取规则（按章节映射）
推荐的章节与关系映射如下：

| 章节或语义 | 关系类型 | 说明 |
|---|---|---|
| 适应症 | INDICATED_FOR | 药物适用于某疾病或症状 |
| 禁忌 | CONTRAINDICATED_FOR | 药物不适用于某人群或疾病 |
| 不良反应 | HAS_SIDE_EFFECT | 药物引起副作用 |
| 相互作用 | INTERACTS_WITH | 药物与药物之间的相互作用 |
| 用法用量 | HAS_DOSAGE | 药物用药剂量 |
| 检查/诊断 | REQUIRES_TEST | 疾病诊断需要的检查 |
| 治疗方案 | TREATS | 治疗方式或药物治疗疾病 |

## 6. 不确定或弱关联处理
1. 没有明确证据的关系不要建立  
2. 仅有弱提示时用 `RELATED_TO`  
3. 关系必须记录证据片段  

## 7. 记录证据（非常重要）
每条关系至少记录一条证据文本：  
1. 原文片段  
2. 来源文件名  
3. 对应文本块 ID  

## 8. 抽取示例

### 示例 1：药品说明书（适应症 + 禁忌 + 用法用量）
**原文片段：**  
“阿司匹林片适用于缓解轻至中度疼痛。对阿司匹林过敏者禁用。用法用量：成人一次 0.3-0.6g，每日 3 次。”

**抽取实体：**  
- Drug：阿司匹林  
- Indication：缓解轻至中度疼痛  
- Contraindication：对阿司匹林过敏者  
- Dosage：成人一次 0.3-0.6g，每日 3 次  

**抽取关系：**  
- 阿司匹林 INDICATED_FOR 缓解轻至中度疼痛  
- 阿司匹林 CONTRAINDICATED_FOR 对阿司匹林过敏者  
- 阿司匹林 HAS_DOSAGE 成人一次 0.3-0.6g，每日 3 次  

### 示例 2：疾病诊断（症状 + 检查）
**原文片段：**  
“高血压患者常出现头痛、眩晕等症状，诊断需进行血压监测。”

**抽取实体：**  
- Disease：高血压  
- Symptom：头痛  
- Symptom：眩晕  
- Test：血压监测  

**抽取关系：**  
- 高血压 HAS_SYMPTOM 头痛  
- 高血压 HAS_SYMPTOM 眩晕  
- 高血压 REQUIRES_TEST 血压监测  

### 示例 3：药物相互作用
**原文片段：**  
“华法林与阿司匹林合用会增加出血风险。”

**抽取实体：**  
- Drug：华法林  
- Drug：阿司匹林  
- Interaction：出血风险  

**抽取关系：**  
- 华法林 INTERACTS_WITH 阿司匹林  
- 阿司匹林 RELATED_TO 出血风险  

## 9. LightRAG 配置提示（可选）
建议在 `.env` 中写入你的实体类型列表，保证抽取与 Schema 一致：  
```bash
ENTITY_TYPES=["Disease","Symptom","Drug","Ingredient","Indication","Contraindication","Interaction","Dosage","SideEffect","Test","Treatment","Procedure","Department","Population","Pathogen","Biomarker","Guideline","Device","Document","Organization","Person","Location","Time","Data","Other"]
```
