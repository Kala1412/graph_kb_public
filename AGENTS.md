# AGENTS Guide - 医疗知识库与智能问答

本项目是工作之余持续迭代的个人 Vibe Coding 项目，探索医疗知识管理、向量与图谱混合检索以及 LangGraph 问答工作流。协作说明与实现不一致时，以代码为准并同步文档。

## 技术与目录

- 后端：FastAPI、SQLAlchemy、SQLite。
- 前端：Vue 3、Vite、Element Plus、Pinia。
- 检索与存储：Milvus、Neo4j、MinIO。
- 工作流与解析：LangGraph、Docling、DeepSeek OCR、MinerU。

| 入口 | 职责 |
| --- | --- |
| `main.py` | 应用入口、自动建表、启动期迁移、论坛分类与检索引擎初始化 |
| `database.py` | 异步数据库连接与会话 |
| `models.py` | ORM 模型、状态常量及约束 |
| `schemas_likes_dto.py` | 请求与响应 DTO / VO |
| `routers/auth.py`、`routers/users.py` | 登录、Token 刷新、个人资料与用户管理 |
| `routers/knowledge.py` | 知识库、文件、资源访问、重试、检索与图谱 |
| `routers/agent.py` | 问答、SSE、会话历史及图片输入 |
| `routers/medical_profiles.py` | 医疗档案增删改查 |
| `routers/forum.py` | 论坛分类、帖子、评论、点赞与治理 |
| `routers/dashboard.py`、`routers/audit.py` | 统计、健康检查与审计日志 |
| `agents/simple_chatbot/rag_agent.py` | LangGraph 问答节点与路由 |
| `agents/common/base.py` | Agent 基类、持久化与流式执行 |
| `utils/rag_utils/` | 分块、清洗、实体关系抽取、存储、改写、澄清与混合检索 |
| `utils/auth_midware.py`、`utils/security.py` | 身份、资源权限与 Token |
| `utils/audit_logger.py` | 写操作审计 |
| `utils/medical_profile_utils.py` | 医疗档案归一化、去重及摘要聚合 |
| `vue-project/src/api/index.js` | 前端 API、Token 刷新与 SSE 解析 |
| `vue-project/src/router/index.js` | 页面路由及权限守卫 |
| `vue-project/src/views/` | 用户页面；`admin/` 下为管理页面 |
| `vue-project/src/stores/`、`components/` | 状态管理及共享组件 |
| `docs/` | Schema、抽取规范与模型提示词 |

## 关键链路

### 文档入库

原始文件写入 MinIO，经 Docling / OCR / MinerU 转为 Markdown，再分块、清洗、向量化与实体关系抽取，写入 Milvus 和 Neo4j。

- 状态顺序：`uploaded → parsing → parsed → indexing → indexed`。
- 失败分别回写 `error_parsing` 或 `error_indexing`，重试必须保证幂等。
- 向量与图谱按知识库隔离，chunk、实体、关系保留来源关联。
- 修改分块或元数据时，同步检查写入、召回、图谱回填与前端引用。
- 修改实体或关系类型时，同步检查 Schema、提示词和图谱展示。
- 不调整 MinIO、Milvus、Neo4j 的写入或清理顺序，除非确认跨存储一致性。

### 检索与问答

意图判断 → 澄清 → 查询改写 → 召回与融合 → 生成 → 记忆处理。

- `naive` 主要走向量检索；`local` 关联向量结果与局部图谱；`global` 使用图谱全文索引与子图扩展；`hybrid` 融合向量与图谱。
- 修改节点输入输出时，检查上下游状态字段及历史会话兼容性。
- 召回、去重、图块回填、候选池与最终 `top_k` 的调整需要结合问答样本验证。
- SSE 事件保持 `start / token / metadata / done / error`，同时验证前端接收和中止行为。
- 图片先写入 MinIO，视觉线索构造 `effective_query`；用户原文和结构化附件独立保留。
- 答案基于检索证据组织，证据不足时说明不确定性，避免表述为诊断结论。
- 优先小步修改，新增节点前明确要解决的误差。

### 医疗档案与论坛

- 医疗档案按用户、分类、内容去重；结构化记录聚合为提示词摘要。
- 聊天后台抽取仅处理用户真实发言，不使用模型回复作为个人事实。
- 论坛为全站讨论区，不绑定知识库。
- 帖子与评论 `active` 对普通用户可见，`hidden` 仅管理员可见，`deleted` 为预留状态。
- 评论仅支持一层回复，限制在后端执行。
- 点赞唯一约束保证单用户单目标不重复计数；取消点赞保持幂等。
- 新增、隐藏、恢复评论时同步回刷 `comment_count`，只统计可见评论。

## 权限与审计

- 用户角色为 `admin / user`，账号状态为 `active / disabled`。
- 普通用户仅操作自己的资源或明确开放的公共资源；管理员拥有全局管理能力。
- 知识库归属由 `owner_id` 决定，文件权限继承知识库，访问必须经过权限校验。
- 会话历史、附件、医疗档案及统计接口需要检查资源归属。
- 修改关键写操作时复用审计 helper，记录成功和失败路径。
- 论坛治理同时考虑管理端和普通用户的可见性。
- 修改前端 API 前确认后端存在，保持参数、出参和 metadata 一致。

## 环境配置

配置来自根目录 `.env`，不要在代码、文档或日志中写入真实凭据。

| 范围 | 主要变量 |
| --- | --- |
| 生成模型 | `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL_ID` |
| 向量检索 | `MILVUS_URI`、`MILVUS_TOKEN`、`MILVUS_DB_NAME`、`EMBEDDING_*` |
| 重排 | `RERANK_BY_DEFAULT`、`MIN_RERANK_SCORE`、`RERANK_*` |
| 图数据库 | `NEO4J_URI`、`NEO4J_USERNAME`、`NEO4J_PASSWORD` |
| 对象存储 | `MINIO_ENDPOINT`、`MINIO_ACCESS_KEY`、`MINIO_SECRET_KEY`、`MINIO_SECURE` |
| 文档解析 | `OCR_API_KEY`、`OCR_BASE_URL`、`OCR_MODEL`、`MINERU_API`、`MINERU_BASE_URL` |
| 图片输入 | `CHAT_IMAGE_ENABLED`、`CHAT_IMAGE_MAX_COUNT`、`CHAT_IMAGE_MAX_SIZE_MB`、`CHAT_IMAGE_ALLOWED_MIME`、`CHAT_IMAGE_VISION_*` |
| 查询理解 | `QUERY_REWRITE_LLM_*`、`QUERY_REWRITE_*`、`QUERY_CLARIFY_*` |

更换 Embedding 模型后需评估重新向量化，避免混用不同语义空间。调整重排阈值、改写或澄清配置时使用一组代表性样本验证。

## 启动与验证

```powershell
# 根目录：启动依赖及后端
docker compose up -d
python main.py
# 或 uvicorn main:app --reload

# 前端目录
cd vue-project
npm install
npm run dev
npm run build
```

- 后端目前没有统一 pytest 体系；修改后至少检查语法、关键接口和已有可用回归脚本。
- 前端修改至少运行构建并检查关键交互；涉及规范时再运行 lint。
- `npm run lint` 和 `npm run format` 会修改文件，使用前确认影响范围。
- 查询改写与澄清改动需验证一组问答样本；SSE 改动需验证完整事件序列。
- 论坛改动需验证分类筛选、发帖、详情、点赞、评论、回复和管理端隐藏 / 恢复。
- 纯注释清理优先比较语法树，确保执行逻辑与提示词不变。

## 代码风格

- Python 使用 `snake_case`，路由按业务域拆分，优先异步数据库访问及已有 helper。
- 前端遵循 `vue-project/.editorconfig`：2 空格、LF、单引号、无分号。
- 注释说明权限、状态、幂等、兼容性与业务约束，避免逐行复述语法和过时变更标签。
- 保持用户区与管理员区的组件、按钮和标签风格一致。
- 提交说明写清行为变化、验证结果及接口、数据结构、环境变量或启动迁移的影响。

## 风险与技术债

- `main.py` 启动时自动建表、补充附件字段、迁移旧医疗档案、初始化论坛分类和检索引擎。修改模型及迁移逻辑需考虑旧库兼容。
- `saves/`、`minio_data/`、`milvus_data/`、`neo4j_data/` 及本地数据库是运行数据，避免手工改写。
- 清理或重置数据的脚本执行前必须确认环境，避免误删。
- `agents/common/base.py` 中存在重复的 `stream_messages` 定义。
- `routers/knowledge.py` 保留部分早期处理流程，改动前确认实际调用入口。
- 不同模块的 MinIO URL 生成策略存在差异。
- 前端构建可能出现较大 chunk 提示，需与功能错误区分。

修改模块前先阅读对应路由、模型、前端页面和权限 helper，保证检索链路、资源隔离、审计与接口一致。
