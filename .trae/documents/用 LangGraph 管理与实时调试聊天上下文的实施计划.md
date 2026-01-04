## LangGraph 管理上下文（简述）
- 状态驱动：上下文以状态在节点间传递，节点返回增量更新。
- 类型与合并：键通过 Reducer 指定合并策略，`messages` 采用追加聚合。
- 消息结构：保留 `HumanMessage`/`AIMessage`/`ToolMessage` 与函数调用结构。
- 条件分支：按状态路由，检索/工具/直接生成可切换。
- 持久化记忆：`checkpointer` 按 `thread_id` 保存快照，支持恢复与回滚。
- 实时调试：事件流与 LangGraph Studio 查看/编辑状态；`get_state`/`update_state` 热修改。
- 窗口与摘要：在中间节点实现裁剪/摘要以控制上下文长度。

## 模型选型与接入（阿里 DashScope）
- 使用 `ChatTongyi` 接入通义千问，环境变量 `DASHSCOPE_API_KEY` 已配置。
- 推荐模型：`qwen-plus`（通用对话，支持函数调用与流式）。可按需切换为 `qwen-turbo`/`qwen-max`。
- 启用流式输出与工具绑定，符合 LangChain/ LangGraph 事件流。

## 实施步骤（Python）

### 1. 定义状态
- `ChatState`：`messages`（追加）、`system`（覆盖）、`metadata`（会话配置）。

### 2. 构建图与节点
- 节点 `chat_llm`：读取 `messages` 与 `system`，调用 `ChatTongyi`，返回 `AIMessage`。
- 可选节点：`route` 决策是否检索/工具；`summarize` 做窗口化或摘要。

### 3. 记忆持久化
- 使用 `SqliteSaver` 作为 `checkpointer`，按 `thread_id` 保存每步状态。
- 暴露 `get_state`、`get_state_history`、按 `checkpoint_id` 回滚。

### 4. 实时调试与热调
- 集成 `app.astream_events(...)` 展示逐步事件与 token 流。
- 提供 `update_state(thread_id, {...})` 接口，支持插入系统提示、重写消息、清理历史。
- 在 CLI 或 Web UI 中显示当前状态快照并可编辑。

### 5. 对话入口
- `send_user_message(thread_id, text)`：`update_state` 然后 `invoke/stream`。
- `set_system_prompt(thread_id, text)`、`edit_last_message(thread_id, new_text)`：热调上下文。

### 6. 工具与 RAG（可选）
- 工具：使用 `bind_tools` 将工具暴露给 `ChatTongyi`，工具结果以 `ToolMessage` 回写上下文。
- RAG：在 `route` 中加入检索节点，维护 `documents/context` 键并窗口化送入模型。

### 7. 代码骨架（示例）
```python
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint import SqliteSaver
from langchain_community.chat_models import ChatTongyi

class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    system: str | None
    metadata: dict | None

llm = ChatTongyi(model="qwen-plus")

builder = StateGraph(ChatState)

def chat_llm(state: ChatState):
    return {"messages": [llm.invoke(state["messages"]) ]}

builder.add_node("chat_llm", chat_llm)
builder.set_entry_point("chat_llm")

checkpointer = SqliteSaver("checkpoints.db")
app = builder.compile(checkpointer=checkpointer)

thread_id = "t1"
app.update_state(thread_id, {"messages": [("user", "你好")], "system": "你是助理"})
for chunk in app.stream({}, thread_id=thread_id):
    pass
state = app.get_state(thread_id)
```

### 8. 验证
- 事件流检查节点与模型输出；验证持久化与窗口化策略。
- 针对系统提示插入/消息重写/历史清理编写小测试。

确认后我将基于该方案落地实现，并接入通义千问与实时调试。