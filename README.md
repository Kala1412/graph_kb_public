# 医疗知识库与智能问答

这是一个持续迭代的个人项目，围绕医疗资料管理、RAG 问答和知识图谱展开。项目把文档解析、向量召回、图谱检索与多轮对话接到同一条链路中，用于探索混合检索和 Agent 工作流在知识管理场景中的应用。

## 功能

- 知识库管理，文件上传、解析、索引及失败重试。
- 将 PDF、Office 文档、图片和文本转换为 Markdown，保留来源和资源文件。
- 基于 Milvus 与 Neo4j 的向量、图谱混合检索，支持 naive、local、global、hybrid 模式及可选重排。
- 使用 LangGraph 编排意图判断、澄清、查询改写、检索、生成与记忆处理。
- SSE 流式问答、多轮会话、图片理解与引用展示。
- 知识图谱浏览、个人医疗档案、讨论区及管理员治理。
- 用户权限控制、审计日志与系统统计。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 后端 | FastAPI、SQLAlchemy、SQLite |
| 前端 | Vue 3、Vite、Element Plus、Pinia |
| 检索 | Milvus、Neo4j、Embedding、Rerank |
| 工作流 | LangGraph |
| 文件存储 | MinIO |
| 文档解析 | Docling、DeepSeek OCR、MinerU |

## 核心链路

文档入库：原始文件 → MinIO → Markdown → 分块与清洗 → 向量化及实体关系抽取 → Milvus / Neo4j。

检索问答：用户问题 → 意图判断与澄清 → 查询改写 → 向量 / 图谱召回 → 融合与重排 → 基于证据生成 → 流式返回答案和引用。

医疗档案以结构化记录保存，回答前聚合为长期画像摘要；会话附件独立存储，保留用户输入文本。

## 目录

| 路径 | 用途 |
| --- | --- |
| `main.py` | 服务入口、生命周期及启动期兼容处理 |
| `routers/` | 认证、用户、知识库、问答、论坛与管理接口 |
| `agents/` | Agent 基类及 LangGraph 问答流程 |
| `utils/rag_utils/` | 分块、抽取、向量与图谱存储、查询理解和检索融合 |
| `vue-project/` | 用户界面与管理界面 |
| `docs/` | 图谱 Schema、抽取规范与提示词 |
| `AGENTS.md` | 开发协作约定 |

## 本地运行

后端需要 Python 环境及对应依赖，前端使用 Node.js。模型接口、Embedding、Rerank、OCR 等配置通过根目录 `.env` 提供；主要配置项见 [AGENTS.md](AGENTS.md)。当前仓库未提供统一的后端依赖清单，启动前需准备代码引用的依赖。

启动存储服务：

```powershell
docker compose up -d
```

启动后端，默认监听 `127.0.0.1:8000`：

```powershell
python main.py
```

启动前端：

```powershell
cd vue-project
npm install
npm run dev
```

前端构建：

```powershell
cd vue-project
npm run build
```

后端启动时会自动建表、补齐旧 SQLite 字段、迁移旧医疗画像及初始化论坛分类。运行数据保存在本地数据库、对象存储、向量库与图数据库中。

## 开发说明

项目使用 AI 辅助开发，逐步围绕实际功能迭代。实现与运行配置以当前代码为准，检索效果需要结合具体文档和问答样本验证。
