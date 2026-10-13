import asyncio
import os
from typing import Annotated

from dotenv import load_dotenv
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from langchain_openai import ChatOpenAI

load_dotenv()

llm = ChatOpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL"),
    model=os.getenv("LLM_MODEL_ID"),
    temperature=0.7
    )

class State(TypedDict):
    messages: Annotated[list,add_messages]

def chatbot_node(state: State):
    response = llm.invoke(state["messages"])

    return {
        "messages": [response]
    }

workflow = StateGraph(State)

workflow.add_node("chatbot", chatbot_node)

workflow.add_edge(START, "chatbot")
workflow.add_edge("chatbot", END)

memory = MemorySaver()

app = workflow.compile(checkpointer=memory)

print("✅ 简单 LangGraph 机器人已构建完成")


async def main():
    thread_1_config = {"configurable": {"thread_id": "user_001"}}

    print("🔴 场景测试 1: 第一轮对话 (user_001)")

    input_msg = HumanMessage(content="你好，我的名字叫李思文。")

    output = await app.ainvoke({"messages": [input_msg]}, config=thread_1_config)

    print(f"🤖 AI 回复: {output['messages'][-1].content}")

    print("\n" + "=" * 50 + "\n")

    print("🔴 场景测试 2: 第二轮对话 (user_001)")

    input_msg_2 = HumanMessage(content="我刚才说我叫什么？")

    output_2 = await app.ainvoke({"messages": [input_msg_2]}, config=thread_1_config)

    print(f"🤖 AI 回复: {output_2['messages'][-1].content}")

    print("\n" + "=" * 50 + "\n")

    print("🔵 场景测试 3: 另一个用户 (user_002)")
    thread_2_config = {"configurable": {"thread_id": "user_002"}}
    input_msg_3 = HumanMessage(content="我叫什么？")

    output_3 = await app.ainvoke({"messages": [input_msg_3]}, config=thread_2_config)

    print(f"🤖 AI 回复: {output_3['messages'][-1].content}")


if __name__ == "__main__":
    asyncio.run(main())































































