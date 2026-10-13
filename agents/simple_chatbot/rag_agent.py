import os
from typing import TypedDict, Annotated, Sequence
import re

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage, RemoveMessage
from langgraph.graph import StateGraph, END, START, add_messages
from typing import Optional
from agents.common.base import BaseAgent
from database import AsyncSessionLocal
from models import UserMedicalProfileRecord, UserMedicalProfile
from utils.rag_utils.lightrag_engine import lightrag_engine
from utils.rag_utils.query_clarifier import clarify_query as run_query_clarify
from utils.rag_utils.query_rewriter import rewrite_query as run_query_rewrite
from utils.retrieval_utils import parse_lightrag_context
from utils.llm_client import llm_client
from utils.medical_profile_utils import aggregate_medical_profile_records
from sqlalchemy import select



class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]  # 使用 add_messages 替代 operator.add，支持消息的追加和删除
    context: str
    intent: str
    kb_id: int
    top_k: Optional[int]
    mode: Optional[str]
    enable_rerank: Optional[bool]

    retrieval: dict
    references: list
    graph_path: list

    user_id: Optional[int]
    # 从长期病状档案聚合出来的“用户长期医疗画像”文本。
    # 它不是前端那种结构化 records，而是给大模型提示词使用的摘要串。
    user_profile: str
    summary: str
    original_query: str
    retrieval_query: str
    rewrite_applied: bool
    rewrite_reason: str
    rewrite_confidence: float
    clarification_needed: bool
    clarification_question: str
    clarification_reason: str
    clarification_confidence: float
    pending_query: str

class MedicalAgent(BaseAgent):
    """
    医疗问答智能体
    功能：根据用户意图，自动决定是否查阅知识库，回答医疗问题。
    """
    name = "医疗问答助手"
    description = "基于 RAG 的医疗知识问答智能体，支持意图识别和知识库检索"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.system_prompt_search = """你是一个严谨的医疗助手。请严格基于以下【参考资料】和【患者画像】回答用户问题。
        如果参考资料中没有相关信息，请直接说明“资料不足”。
        
        【患者画像 (长期记忆)】:
        {user_profile}

        【之前对话摘要 (短期记忆)】:
        {summary}
        
        参考资料：
        {context}
        """
        self.system_prompt_chat = """你是一个友好的医疗助手。正在与用户进行日常对话。
        【重要设定】
        系统已从数据库加载了当前用户的【患者画像】（长期记忆）。请注意：这些信息是用户在之前的对话中明确告知过的真实病史。
        【患者画像（当前用户长期记忆信息）】: {user_profile}
        【之前对话摘要】: {summary}
        
        请基于上述信息，以亲切、专业的口吻与用户进行对话。
        """

    def _message_content_to_text(self, content) -> str:
        """
        统一消息文本提取：
        - 兼容 string / list / dict 等多种 content 形态（为后续多模态输入留兼容）
        - 节点内一律拿“可检索文本”，避免直接 str(dict) 触发路由/检索偏差
        """
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    texts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if isinstance(text, str) and text.strip():
                        texts.append(text.strip())
            return "\n".join([t for t in texts if t]).strip()
        if isinstance(content, dict):
            text = content.get("text") or content.get("content")
            if isinstance(text, str):
                return text
        return str(content or "")

    def _latest_user_query_text(self, messages: Sequence[BaseMessage]) -> str:
        if not messages:
            return ""
        return self._message_content_to_text(getattr(messages[-1], "content", "")).strip()

    async def _node_analyze_intent(self,state: AgentState):
        """节点：分析意图"""
        kb_id = state.get("kb_id")
        # 如果没有 kb_id，直接判定为 chat，不调用 LLM
        if kb_id is None:
            print("💬 [Router] 无 kb_id，跳过意图分析，直接判定为 chat")
            return {"intent": "chat"}

        messages = state["messages"]
        # 统一走文本提取 helper，避免后续多模态 content 结构影响意图路由。
        last_user_message = self._latest_user_query_text(messages)

        print(f"[Agent] analyze intent: {last_user_message}")

        router_prompt = f"""你是一个意图分类器。
            用户输入: "{last_user_message}"

            任务：
            1. 如果用户是在问具体的医疗知识、事实性问题、或者需要查阅资料，请回复 "SEARCH"
            2. 如果用户只是打招呼(你好)、感谢(谢了)、问你是谁，或者闲聊，请回复 "CHAT"

            只回复单词 "SEARCH" 或 "CHAT"，不要加其他符号。
            """

        response = await llm_client.chat_model.ainvoke([HumanMessage(content=router_prompt)])
        intent = response.content.strip().upper()
        if "SEARCH" in intent:
            intent = "search"
        else:
            intent = "chat"

        print(f"🧭 [Router] 判定意图为: {intent}")

        return {"intent": intent}

    async def _node_load_ltm(self, state: AgentState):
        """节点：从数据库加载该用户的长期医疗画像"""
        user_id = state.get("user_id")
        user_profile = "无特殊已知病史"
        if user_id:
            async with AsyncSessionLocal() as db:
                stmt = select(UserMedicalProfile).where(UserMedicalProfile.user_id == user_id)
                profile = (await db.execute(stmt)).scalar_one_or_none()
                if profile and profile.medical_facts:
                    user_profile = profile.medical_facts
                    print(f"📋 [LTM] 加载用户 {user_id} 的长期记忆医疗画像: {user_profile}")
                else:
                    print(f"📋 [LTM] 用户 {user_id} 没有医疗画像，使用默认值")
        return {"user_profile": user_profile}

    async def _node_rewrite_query(self, state: AgentState):
        intent = state.get("intent", "chat")
        messages = state.get("messages", [])
        # 统一走 helper：rewrite 只处理文本 query，不直接依赖消息底层结构。
        last_user_message = self._latest_user_query_text(messages)
        original_query = str(state.get("original_query") or last_user_message).strip()

        if intent != "search" or not state.get("kb_id"):
            return {
                "original_query": original_query,
                "retrieval_query": original_query,
                "rewrite_applied": False,
                "rewrite_reason": "skip_non_search",
                "rewrite_confidence": 0.0,
            }

        # clarify 分支已经在图路由上拦截，这里保留防御式回退，避免异常状态误入。
        if state.get("clarification_needed"):
            return {
                "original_query": original_query,
                "retrieval_query": original_query,
                "rewrite_applied": False,
                "rewrite_reason": "skip_due_to_clarification",
                "rewrite_confidence": 0.0,
            }

        try:
            rounds = max(1, int(os.getenv("QUERY_REWRITE_HISTORY_ROUNDS", "3")))
        except Exception:
            rounds = 3

        summary = state.get("summary", "")
        rewrite = await run_query_rewrite(
            messages=messages,
            summary=summary,
            query=original_query,
            rounds=rounds,
        )

        print(
            f"[Rewrite] applied={rewrite.rewrite_applied}, "
            f"reason={rewrite.reason}, "
            f"original='{rewrite.original_query}', "
            f"rewritten='{rewrite.rewritten_query}'"
        )

        return {
            "original_query": rewrite.original_query,
            "retrieval_query": rewrite.rewritten_query,
            "rewrite_applied": rewrite.rewrite_applied,
            "rewrite_reason": rewrite.reason,
            "rewrite_confidence": rewrite.confidence,
        }

    async def _node_clarify_gate(self, state: AgentState):
        """
        节点：检索前澄清判断
        - 只对 search 意图生效
        - 若问题信息不足：进入 clarify_generate 反问用户
        - 若信息足够：放行到 rewrite_query
        """
        intent = state.get("intent", "chat")
        messages = state.get("messages", [])
        # 统一走 helper：clarify 依赖“文本可判定内容”，与消息结构解耦。
        last_user_message = self._latest_user_query_text(messages)

        # 初始值统一写回，便于后续节点/接口稳定读取。
        base_payload = {
            "clarification_needed": False,
            "clarification_question": "",
            "clarification_reason": "skip_non_search",
            "clarification_confidence": 0.0,
            "pending_query": "",
            "original_query": last_user_message,
            "retrieval_query": last_user_message,
            "rewrite_applied": False,
            "rewrite_reason": "rewrite_not_run",
            "rewrite_confidence": 0.0,
            # 澄清节点可能提前结束检索链，务必清空检索相关字段，避免复用旧状态。
            "context": "",
            "retrieval": {"chunks": [], "entities": [], "relationships": [], "context": ""},
            "references": [],
            "graph_path": [],
        }

        if intent != "search" or not state.get("kb_id"):
            return base_payload

        try:
            rounds = max(1, int(os.getenv("QUERY_CLARIFY_HISTORY_ROUNDS", "3")))
        except Exception:
            rounds = 3

        summary = state.get("summary", "")
        pending_query = str(state.get("pending_query") or "")
        clarify = await run_query_clarify(
            messages=messages,
            summary=summary,
            query=last_user_message,
            pending_query=pending_query,
            rounds=rounds,
        )

        print(
            f"[Clarify] needed={clarify.need_clarification}, "
            f"reason={clarify.reason}, "
            f"question='{clarify.clarification_question}', "
            f"normalized='{clarify.normalized_query}'"
        )

        normalized_query = str(clarify.normalized_query or last_user_message).strip()
        return {
            "clarification_needed": clarify.need_clarification,
            "clarification_question": clarify.clarification_question,
            "clarification_reason": clarify.reason,
            "clarification_confidence": clarify.confidence,
            "pending_query": clarify.pending_query,
            # 澄清阶段可能已做“短回答合并”，因此 original_query 以 normalized_query 为准。
            "original_query": normalized_query,
            "retrieval_query": normalized_query,
            "rewrite_applied": False,
            "rewrite_reason": "rewrite_not_run",
            "rewrite_confidence": 0.0,
            # 进入澄清时明确清空检索结果，避免 metadata 出现历史脏数据。
            "context": "",
            "retrieval": {"chunks": [], "entities": [], "relationships": [], "context": ""},
            "references": [],
            "graph_path": [],
        }

    async def _node_generate_clarification(self, state: AgentState):
        """节点：生成澄清追问，不进入检索。"""
        question = str(state.get("clarification_question") or "").strip()
        if not question:
            question = "为了更准确回答，请补充更具体的信息（如对象、症状、时间或背景）。"
        print(f"[Clarify] ask user: {question}")
        return {"messages": [AIMessage(content=question)]}

    async def _node_retrieve(self, state: AgentState):
        """节点：检索知识库相关内容context  - 只有 intent='search' 才会来这里"""
        messages = state["messages"]
        # 统一走文本提取 helper，避免后续多模态 content 结构影响意图路由。
        last_user_message = self._latest_user_query_text(messages)
        original_query = str(state.get("original_query") or last_user_message)
        retrieval_query = str(state.get("retrieval_query") or last_user_message)
        kb_id = state.get("kb_id",1)
        top_k = state.get("top_k", 3)
        enable_rerank = state.get("enable_rerank")
        mode = state.get("mode", "hybrid")

        print(f"[Agent] retrieve KB_ID={kb_id}, top_k={top_k}, mode={mode}, query={retrieval_query}")

        try:
            context_result = await lightrag_engine.query(
                question=retrieval_query,
                kb_id=kb_id,
                top_k=top_k,
                mode=mode,
                only_context=True,
                enable_rerank=enable_rerank
            )

            retrieval = {
                "chunks": [],
                "entities": [],
                "relationships": [],
                "context": "",
            }

            if isinstance(context_result, dict):
                retrieval["chunks"] = context_result.get("chunks", [])
                retrieval["entities"] = context_result.get("entities", [])
                retrieval["relationships"] = context_result.get("relationships", []) or context_result.get("relations", [])
                retrieval["context"] = context_result.get("context", "") or ""

                # 兼容 only_context 场景：返回 dict 但 chunks 只在 context 字符串里
                if retrieval["context"] and not retrieval["chunks"]:
                    parsed = parse_lightrag_context(retrieval["context"])
                    retrieval["chunks"] = parsed.get("chunks", [])
                    if not retrieval["entities"]:
                        retrieval["entities"] = parsed.get("entities", [])
                    if not retrieval["relationships"]:
                        retrieval["relationships"] = parsed.get("relations", [])
            else:
                raw_text = str(context_result)
                parsed = parse_lightrag_context(raw_text)
                retrieval["chunks"] = parsed.get("chunks", [])
                retrieval["entities"] = parsed.get("entities", [])
                retrieval["relationships"] = parsed.get("relations", [])
                retrieval["context"] = raw_text

            context_str = retrieval["context"]
            if not context_str and retrieval["chunks"]:
                context_str = "\n\n".join([
                    str(item.get("content") or item.get("text") or "")
                    for item in retrieval["chunks"]
                    if item
                ])

            def parse_file_id_from_doc_id(doc_id: str | None):
                if not doc_id:
                    return None
                match = re.search(r"kb_\d+_file_(\d+)", doc_id)
                return match.group(1) if match else None

            def build_references(chunks: list) -> list:
                refs = []
                for chunk in chunks:
                    if not isinstance(chunk, dict):
                        continue
                    metadata = chunk.get("metadata") or {}
                    content = chunk.get("content") or chunk.get("text") or chunk.get("chunk") or ""
                    file_id = metadata.get("file_id") or metadata.get("fileId") or chunk.get("file_id")
                    if not file_id:
                        file_id = parse_file_id_from_doc_id(metadata.get("doc_id") or chunk.get("doc_id"))
                    source_file = metadata.get("source") or chunk.get("source") or metadata.get("source_file")
                    similarity_score = chunk.get("similarity_score") or chunk.get("score") or metadata.get("score")
                    anchor = content[:60] if content else ""
                    refs.append({
                        "file_id": str(file_id) if file_id is not None else None,
                        "source_file": source_file,
                        "content": content,
                        "anchor": anchor,
                        "similarity_score": similarity_score,
                    })
                return refs

            references = build_references(retrieval["chunks"])

            # 如果 references 没有任何可定位信息，尝试再取一次结构化结果
            has_locator = any(ref.get("file_id") or ref.get("source_file") for ref in references)
            if not has_locator:
                try:
                    structured_result = await lightrag_engine.query(
                        question=retrieval_query,
                        kb_id=kb_id,
                        top_k=top_k,
                        mode=mode,
                        only_context=False,
                        enable_rerank=enable_rerank
                    )
                    if isinstance(structured_result, dict):
                        structured_chunks = structured_result.get("chunks", []) or []
                        if structured_chunks:
                            retrieval["chunks"] = structured_chunks
                            if structured_result.get("context"):
                                retrieval["context"] = structured_result.get("context")
                            references = build_references(structured_chunks)
                except Exception as exc:
                    print(f"⚠️ 结构化检索补偿失败: {exc}")

            graph_path = []
            for rel in retrieval["relationships"] or []:
                if not isinstance(rel, dict):
                    continue
                source = rel.get("head") or rel.get("entity1") or rel.get("source") or rel.get("from")
                target = rel.get("tail") or rel.get("entity2") or rel.get("target") or rel.get("to")
                relation = rel.get("relation") or rel.get("type") or rel.get("edge") or rel.get("predicate")
                if source and target:
                    graph_path.append({
                        "source": source,
                        "relation": relation,
                        "target": target,
                    })

        except Exception as e:
            context_str = ""
            retrieval = {"chunks": [], "entities": [], "relationships": [], "context": ""}
            references = []
            graph_path = []
            print(f"⚠️ 检索失败: {e}")

        return {
            "context": context_str,
            "retrieval": retrieval,
            "references": references,
            "graph_path": graph_path,
            "original_query": original_query,
            "retrieval_query": retrieval_query,
            "rewrite_applied": bool(state.get("rewrite_applied", False)),
            "rewrite_reason": str(state.get("rewrite_reason") or ""),
            "rewrite_confidence": float(state.get("rewrite_confidence") or 0.0),
        }

    async def _node_generate_rag(self,state: AgentState):
        """节点：RAG生成答案 - 只有 intent='search' 才会来这里"""
        """ 支持流式输出 """
        messages = state["messages"]
        context = state.get("context", "")
        summary = state.get("summary", "无")
        user_profile = state.get("user_profile", "无")

        full_system_prompt = self.system_prompt_search.format(
            context=context,
            summary=summary,
            user_profile=user_profile
        )

        # 过滤历史记录，提取最近几轮，避免 token 溢出
        final_messages = [SystemMessage(content=full_system_prompt)] + list(messages)

        print("🤖 [RAG] 正在生成回答...")
        full_response = ""
        async for chunk in llm_client.chat_model.astream(final_messages):
            full_response += chunk.content


        return {"messages": [AIMessage(content=full_response)]}

    async def _node_generate_chat(self,state: AgentState):
        """节点：闲聊生成（非知识库内容）"""
        messages = state["messages"]

        summary = state.get("summary", "无")
        user_profile = state.get("user_profile", "无")

        formatted_system_prompt = self.system_prompt_chat.format(
            summary=summary,
            user_profile=user_profile
        )

        print(f"🐛 [Debug Prompt] System Prompt 内容片段: \n{formatted_system_prompt}...")

        final_messages = [SystemMessage(content=formatted_system_prompt)] + list(messages)

        print("💬 [Chat] 正在进行纯对话...")
        full_content = ""
        async for chunk in llm_client.chat_model.astream(final_messages):
            # 这里的 chunk 会被 LangGraph 的 stream_messages 捕获
            full_content += chunk.content
        return {"messages": [AIMessage(content=full_content)]}

    async def _node_summarize_memory(self, state: AgentState):
        """节点：短期记忆压缩（滑动窗口机制）"""
        messages = state["messages"]
        summary = state.get("summary", "")

        current_len = len(messages)
        print(f"\n🔍 [STM观测] 当前消息列表长度: {current_len}")
        print(f"🔍 [STM观测] 当前摘要内容: {summary}...")

        # 超过三轮对话时压缩旧消息，保留当前轮的两条消息。
        THRESHOLD = 6
        if len(messages) <= THRESHOLD:
            print(f"🟢 [STM观测] 未达到阈值 ({THRESHOLD})，跳过压缩")
            return {}

        print("🧠 [STM] 记忆超过阈值，正在压缩短期记忆...")
        # 提取需要压缩的旧消息 (排除最新的 2 条：也就是刚问的问题和刚生成的回答)
        messages_to_compress = messages[:-2]
        remaining_messages = messages[-2:]

        print(f"   - 待删除消息数: {len(messages_to_compress)}")
        print(f"   - 待删除消息ID示例: {[m.id for m in messages_to_compress]}")
        print(f"   - 保留消息数: {len(remaining_messages)}")

        summary_prompt = f"""请将以下对话总结为简短的摘要。如果已有旧摘要，请合并。
                【旧摘要】：{summary}
                【需压缩的对话】：{[self._message_content_to_text(m.content) for m in messages_to_compress]}
                """
        response = await llm_client.chat_model.ainvoke([HumanMessage(content=summary_prompt)])
        new_summary = response.content
        print(f"📝 [STM观测] 生成新摘要: {new_summary}")

        # 总结完之后要在 LangGraph 删除这些旧消息
        delete_messages = [RemoveMessage(id=m.id) for m in messages_to_compress]

        return {"summary": new_summary, "messages": delete_messages}


    def route_decision(self,state: AgentState):
        """条件路由：根据意图决定下一个节点"""
        intent = state.get("intent", "chat")
        return "clarify_gate" if intent == "search" else "pure_chat"

    def route_after_clarify(self, state: AgentState):
        """澄清分流：需要澄清则追问，否则进入 query 重写。"""
        return "clarify_generate" if state.get("clarification_needed") else "rewrite_query"

    async def get_graph(self):
        """构建并编译图"""
        if self.graph:
            return self.graph

        workflow = StateGraph(AgentState)

        workflow.add_node("load_ltm", self._node_load_ltm)
        workflow.add_node("intent_router", self._node_analyze_intent)
        workflow.add_node("clarify_gate", self._node_clarify_gate)
        workflow.add_node("clarify_generate", self._node_generate_clarification)
        workflow.add_node("rewrite_query", self._node_rewrite_query)
        workflow.add_node("retrieve", self._node_retrieve)
        workflow.add_node("rag_generate", self._node_generate_rag)
        workflow.add_node("pure_chat", self._node_generate_chat)
        workflow.add_node("summarize", self._node_summarize_memory)

        workflow.add_edge(START, "load_ltm")
        workflow.add_edge("load_ltm", "intent_router")

        workflow.add_conditional_edges(
            "intent_router",
            self.route_decision,
            {
                "clarify_gate": "clarify_gate",
                "pure_chat": "pure_chat",
            },
        )
        workflow.add_conditional_edges(
            "clarify_gate",
            self.route_after_clarify,
            {
                "clarify_generate": "clarify_generate",
                "rewrite_query": "rewrite_query",
            },
        )

        workflow.add_edge("rewrite_query", "retrieve")
        workflow.add_edge("retrieve", "rag_generate")

        workflow.add_edge("clarify_generate", "summarize")

        workflow.add_edge("rag_generate", "summarize")

        workflow.add_edge("pure_chat", "summarize")

        workflow.add_edge("summarize", END)

        checkpointer = await self._get_checkpointer()
        self.graph = workflow.compile(checkpointer=checkpointer)
        return self.graph

# 覆盖长期记忆加载节点，从结构化记录聚合医疗画像，兼容旧表实现。
async def _patched_node_load_ltm(self, state: AgentState):
    user_id = state.get("user_id")
    user_profile = "无特殊已知病史"
    if user_id:
        async with AsyncSessionLocal() as db:
            stmt = (
                select(UserMedicalProfileRecord)
                .where(UserMedicalProfileRecord.user_id == user_id)
                .order_by(UserMedicalProfileRecord.updated_at.desc(), UserMedicalProfileRecord.id.desc())
            )
            records = (await db.execute(stmt)).scalars().all()
            # 按分类聚合事实，供 system prompt 使用。
            aggregated_profile = aggregate_medical_profile_records(records)
            if aggregated_profile:
                user_profile = aggregated_profile
                print(f"📋 [LTM] 加载用户 {user_id} 的长期记忆医疗画像: {user_profile}")
            else:
                print(f"📋 [LTM] 用户 {user_id} 没有医疗画像，使用默认值")
    return {"user_profile": user_profile}


MedicalAgent._node_load_ltm = _patched_node_load_ltm
medical_agent = MedicalAgent()
