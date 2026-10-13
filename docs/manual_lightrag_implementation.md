# 向量与图谱检索实现说明

本文件记录检索管线的实现思路与数据结构约定，具体行为以当前代码为准：
1. 文档分块 + 向量化入库（Milvus）
2. 实体/关系抽取 + 图谱入库（Neo4j）
3. 多模式查询（naive/local/global/hybrid）+ 可选重排

## 1. 总体数据流

```
原始文件 -> Markdown -> 分块 -> 向量化 -> Milvus
                         -> 实体/关系抽取 -> Neo4j

用户问题 -> 向量检索 / 图谱检索 -> 结果融合 -> 返回
```

## 2. 数据结构约定

### 2.1 Chunk 结构
```json
{
  "chunk_id": "uuid",
  "file_id": 12,
  "doc_id": "kb_1_file_12",
  "content": "段落文本...",
  "metadata": {
    "kb_id": 1,
    "file_id": 12,
    "doc_id": "kb_1_file_12",
    "headers": {"Header 1": "药品说明书"}
  }
}
```

### 2.2 Entity 结构
```json
{
  "entity_name": "高血压",
  "entity_type": "Disease",
  "description": "一种慢性疾病",
  "source_chunk_id": "uuid",
  "file_id": 12,
  "doc_id": "kb_1_file_12"
}
```

### 2.3 Relation 结构
```json
{
  "head": "高血压",
  "relation": "HAS_SYMPTOM",
  "tail": "头痛",
  "evidence": "高血压患者常出现头痛",
  "source_chunk_id": "uuid",
  "file_id": 12,
  "doc_id": "kb_1_file_12"
}
```

## 3. 分块与向量化（Milvus）

### 3.1 分块流程
1. MarkdownHeaderTextSplitter：先按标题切分（保留章节结构）
2. RecursiveCharacterTextSplitter：再按长度切分

伪代码：
```python
header_splitter = MarkdownHeaderTextSplitter([("#","H1"),("##","H2")])
header_chunks = header_splitter.split_text(markdown)

splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=100)
chunks = splitter.split_documents(header_chunks)
```

### 3.2 向量化 & Milvus 入库
Milvus 集合：`kb_{kb_id}_chunks`
字段：
- `chunk_id` (VARCHAR)
- `file_id` (INT64)
- `doc_id` (VARCHAR)
- `content` (VARCHAR)
- `metadata` (VARCHAR JSON)
- `embedding` (FLOAT_VECTOR)

向量化规则：
1. 先调用 embedding 模型
2. 向量做 L2 归一化
3. 写入 Milvus

伪代码：
```python
embeddings = embed_texts([chunk.content for chunk in chunks])
embeddings = l2_normalize(embeddings)
collection.insert([chunk_ids, file_ids, doc_ids, contents, metadata_json, embeddings])
```

## 4. 实体/关系抽取（LLM）

### 4.1 抽取提示词模板（实体）
```
你是医学知识抽取器，从文本中抽取实体，输出 JSON 数组。
entity_type 必须来自以下类型列表：{ENTITY_TYPES}
字段：entity_name, entity_type, description
只输出 JSON，不要解释。
```

### 4.2 抽取提示词模板（关系）
```
你是医学关系抽取器，从文本中抽取关系，输出 JSON 数组。
relation 推荐使用：TREATS, HAS_SYMPTOM, ...
字段：head, relation, tail, evidence
只输出 JSON，不要解释。
```

### 4.3 错误恢复策略
1. LLM 输出非 JSON → 用正则提取 JSON 代码块
2. entity_type 不在 schema → 替换为 `Other`
3. relation 非标准 → 替换为 `RELATED_TO`

## 5. Neo4j 入库

### 5.1 节点写入
```
MERGE (e:kb_1:Disease {entity_id: "高血压"})
SET e.entity_name = "高血压",
    e.entity_type = "Disease",
    e.source_doc_ids = ["kb_1_file_12"]
```

### 5.2 关系写入
```
MERGE (h)-[r:HAS_SYMPTOM]->(t)
SET r.evidence = "高血压患者常出现头痛",
    r.source_chunk_id = "uuid"
```

### 5.3 全文索引（global 查询使用）
```
CREATE FULLTEXT INDEX kb_1_entity_fulltext IF NOT EXISTS
FOR (n:kb_1) ON EACH [n.entity_name, n.aliases]
```

## 6. 多模式查询策略

### 6.1 naive
只做向量检索（Milvus top_k）

### 6.2 local
向量检索 → 获取 top_k chunk_id → 查询同源实体/关系

### 6.3 global
全文索引查实体 → 扩展 1~2 hop 子图 → 返回实体/关系

### 6.4 hybrid
naive + global/local 合并结果，再去重与重排

## 7. 可选重排（Rerank）

当 `enable_rerank=True` 时：
1. 调用 `RERANK_BASE_URL` 指向的接口
2. 使用 `RERANK_MODEL`
3. 根据 `relevance_score` 重新排序 chunks

## 8. 关键配置（.env）
```
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIM=1024
ENTITY_TYPES=[...]
MILVUS_URI=http://localhost:19530
NEO4J_URI=bolt://localhost:7687
```

## 9. 最小可运行流程（Checklist）
1. 上传文件 → 生成 Markdown
2. 分块 → 向量入库
3. LLM 抽取 → Neo4j 入库
4. 查询模式：naive/local/global/hybrid
5. 删除文档 → Milvus & Neo4j 清理
