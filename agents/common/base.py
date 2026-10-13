from abc import abstractmethod, ABC
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver, aiosqlite

class BaseAgent(ABC):
    """所有 Agent 的基类"""

    # 子类需要定义的元数据
    name = "base_agent"
    description = "基础智能体"

    def __init__(self,workdir: str = "./saves/agents"):
        self.graph = None
        self.checkpointer = None

        # 为每个智能体创建独立的工作目录
        self.workdir = Path(workdir) / self.__class__.__name__
        self.workdir.mkdir(parents=True, exist_ok=True)

    @property
    def id(self) -> str:
        """获取智能体的唯一ID（类名）"""
        return self.__class__.__name__

    @abstractmethod
    async def get_graph(self) -> CompiledStateGraph:
        """
        子类需要实现这个方法，返回一个 StateGraph 实例
        注意：必须在编译时设置 checkpointer
        """
        pass

    async def _get_checkpointer(self):
        """创建 checkpointer记忆组件，优先使用 SQLite，失败则用内存"""
        try:
            conn = await aiosqlite.connect(str(self.workdir / "agent_history.db"))
            # 兼容缺少 is_alive() 的 aiosqlite Connection，供 AsyncSqliteSaver 检查连接。
            if not hasattr(conn, "is_alive"):
                conn.is_alive = lambda: True
                return AsyncSqliteSaver(conn)
        except Exception as e:
            print(f"⚠️ SQLite checkpointer 创建失败: {e}，使用内存存储")
            return MemorySaver()

    async def stream_messages(self,messages: list,thread_id: str = "default", **kwargs):
        """统一的调用入口，传入消息列表，返回回复（流式）"""

        graph = await self.get_graph()

        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }

        inputs = {
            "messages": messages,
                **kwargs
        }

        async for msg,metadata in graph.astream(
            inputs,
            config=config,
            stream_mode="messages"
        ):
            yield msg,metadata


    async def invoke_messages(self,messages: list,thread_id: str = "default", **kwargs):
        """统一的调用入口，传入消息列表，返回回复"""

        graph = await self.get_graph()

        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }

        inputs = {
            "messages": messages,
            **kwargs
        }

        result = await graph.ainvoke(inputs, config=config)

        return result

    def reload_graph(self):
        """重置 graph 缓存"""
        self.graph = None
        print(f"♻️ {self.name} graph 已重置")


    async def stream_messages(self, messages: list, thread_id: str = "default", **kwargs):
        """统一的调用入口，传入消息列表，返回回复（流式）"""

        graph = await self.get_graph()

        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }

        inputs = {
            "messages": messages,
            **kwargs
        }

        async for msg, metadata in graph.astream(
                inputs,
                config=config,
                stream_mode="messages"
        ):
            yield msg, metadata









































