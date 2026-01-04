# ContextMgr: 可发布的上下文管理组件

独立的上下文管理组件，支持：
- YAML 配置加载（模型、system、sticky 文档、知识库目录/文件、流程开关/步骤）
- 多用户会话（按 `user_id` 映射到独立 `thread_id`）
- 与任意代理框架集成（示例：Agentscope）

## 安装与集成
- 依赖：`langgraph`, `langchain`, `langchain-community`, `dashscope`, `pyyaml`
- 加载：
```python
from contextmgr import load_context_app, SessionManager
# 模型配置从 YAML 剥离，作为入参传入（或使用默认）
app, seed, ds = load_context_app("configs/context.yaml", tools=[...], model="qwen-plus")
sm = SessionManager()
tid = sm.thread_for(user_id)
seed(tid)
```
- 发送消息与读取状态：
```python
from src.runtime import send_user_message, get_state
send_user_message(app, tid, "你好")
st = get_state(app, tid)
```

## YAML 字段

| 字段 | 类型/默认 | 作用 | 注入/触发 |
| --- | --- | --- | --- |
| `system` | `string` | 统一系统前言，设定角色与边界 | 每轮首条 `SystemMessage` |
| `sticky_docs` | `string[]` | 常驻规范文档，进入 DocStore 粘性集合 | 每次检索优先合并进 `context` |
| `doc_files` | `string[]` | 启动导入的知识库文件（自动分块） | 命中查询后将片段合并进 `context` |
| `doc_dirs` | `string[]` | 目录批量导入（支持 `.txt/.md/.mdx`） | 与 `doc_files` 同策略 |
| `context` | `object`/`string[]` | 初始上下文配置 | 支持多桶与优先级，见下 |
| `procedure_enabled` | `bool` | 开启流程提示模式 | 开启后每轮注入当前步骤指引 |
| `procedure_steps` | `string[]` | 流程步骤列表 | 结合 `procedure_enabled` 使用，可推进/重置 |

差异与注入时机速览

| 项目 | 是否检索参与 | 注入方式 | 备注 |
| --- | --- | --- | --- |
| `system` | 否 | 始终作为系统消息注入 | 固定前言 |
| `context` | 是（合并结果） | 合并为一条系统消息 | 多桶与优先级 |
| `sticky_docs` | 是 | 作为优先片段合并进 `context` | 适合“常驻规范” |
| `doc_files`/`doc_dirs` | 是（查询驱动） | 命中后片段合并进 `context` | 知识库来源 |
| `procedure_*` | 否 | 注入步骤提示 | 不影响事实检索 |

## 6 类上下文体系

本组件将 Agent 上下文划分为 6 个核心类别，分别对应不同的认知维度与配置字段。

| 上下文类别 | 核心用途 | `context.yaml` 对应字段 | 注入时机与逻辑 |
| :--- | :--- | :--- | :--- |
| **1. System** | **基调/身份**：全局身份设定，不参与排序。 | `system` | **最先注入**。始终作为 SystemMessage 的第一条。 |
| **2. Policies** | **策略/规范**：定义角色边界、安全红线。 | `context.policies`<br>`sticky_docs` (及 `persona.sticky`) | **多桶合并-高优先级**。`sticky_docs` 会自动追加到 policies 列表。 |
| **3. Facts** | **事实/知识**：静态知识与动态检索结果。 | `context.facts`<br>`context` (旧版列表)<br>`doc_files` / `doc_dirs` (检索命中后) | **多桶合并-中优先级**。检索到的文档片段 (`ds.retrieve`) 会自动追加到 facts 列表。 |
| **4. Instructions** | **指令/任务**：本轮具体任务与思维链要求。 | `context.instructions` | **多桶合并-中优先级**。定义本轮具体操作指令。 |
| **5. Examples** | **示例/样本**：Few-shot 问答对。 | `context.examples` | **多桶合并-低优先级**。提供输出格式参考。 |
| **6. Procedure** | **流程/SOP**：强制流程控制与步骤引导。 | `procedure_enabled`<br>`procedure_steps` (及 `procedure.steps`) | **最后注入**。若开启，在所有上下文后追加当前步骤提示。 |

## 压缩策略建议

在 6 类上下文中，通常采用以下压缩策略以平衡 Token 预算：

| 上下文类别 | 压缩建议 | 理由 |
| :--- | :--- | :--- |
| **1. System** | **不压缩** | 定义全局身份与安全边界，必须完整保留。 |
| **2. Policies** | **不压缩** (或仅去重) | 涉及合规与红线，任何删减可能导致越权。 |
| **3. Facts** | **高压缩** | 检索结果往往冗余，可进行摘要、提取关键句或去噪。 |
| **4. Instructions** | **不压缩** | 具体指令直接决定任务成败，需精确传递。 |
| **5. Examples** | **可压缩/截断** | 仅作为格式参考，超长时可减少样本数量或截断。 |
| **6. Procedure** | **不压缩** | 流程控制需严格按步骤执行，不可模糊。 |

## 注入文档 (RAG) 处理流程

系统通过 `DocStore` 接口处理文档，具体流程如下：

1.  **加载阶段 (`load_context_app`)**：
    *   读取 YAML 中的 `doc_files` 和 `doc_dirs`。
    *   调用 `ds.add_file(path)` 或 `ds.add_dir(path)`。
    *   **内部处理**：DocStore 会读取文件内容，按语义或字符长度进行**分块 (Chunking)**，并计算向量嵌入 (Embedding) 存入向量库。

2.  **检索阶段 (`prepare_ctx`)**：
    *   获取当前用户查询 (`state["messages"][-1].content`)。
    *   调用 `ds.retrieve(query)`。
    *   **内部匹配**：在向量库中查找与 query 相似度最高的 Top-K 文本块。

3.  **注入阶段**：
    *   将检索到的文本块列表追加到 **Facts** 桶中。
    *   `facts` 桶随后与其他桶合并，成为 SystemMessage 的一部分输入给 LLM。

**优化建议：注入源 URL**

当前实现仅注入了文档的文本内容 (Chunk)，丢失了来源信息。
**优化方案**：修改 `DocStore` 返回结构，使其包含元数据 (Metadata)，并在 `prepare_ctx` 中格式化注入。

*   **当前**：`facts = ["文本块内容...", "另一段内容..."]`
*   **优化后**：
    ```python
    # 假设 ds.retrieve 返回对象包含 metadata
    for doc in ds.retrieve(query):
        source = doc.metadata.get("source", "unknown")
        content = doc.page_content
        facts.append(f"Source: {source}\nContent: {content}")
    ```
这样 LLM 在回答时可以引用具体来源（如“根据 [文件A]...”），增强可信度。


## sticky_docs 与 doc_files/doc_dirs 的关系

| 项目 | 是否常驻 | 注入规则 | 适用场景 | 来源 |
| --- | --- | --- | --- | --- |
| `sticky_docs` | 是 | 每轮优先合并进 `context` | 行为规范、角色约束 | YAML/运行时文本 |
| `doc_files` | 否（查询驱动） | 命中后将片段合并进 `context` | 说明文档、参考资料 | 文件路径（自动分块） |
| `doc_dirs` | 否（查询驱动） | 命中后将片段合并进 `context` | 批量知识库导入 | 目录（`.txt/.md/.mdx`） |

合并顺序与策略：现有 `context`（初始/手动） + `sticky_docs` + 检索命中的 KB 片段 → 去重合并；合并后以“一条系统消息”注入模型，减少冗余、增强可控性。

## 多桶与优先级配置

| `context` 键 | 类型 | 说明 |
| --- | --- | --- |
| `policies` | `string[]` | 规范与边界（常驻），优先级高 |
| `facts` | `string[]` | 事实片段（初始 + 检索结果） |
| `instructions` | `string[]` | 本轮任务指令 |
| `examples` | `string[]` | few-shot 示例片段 |
| `priority` | `string[]` | 多桶合并顺序，默认 `["policies","facts","instructions","examples"]` |

配置示例（推荐）：
```yaml
system: 你是中文助理
persona:
  sticky:
    - 行为规范：不得输出敏感信息
kb:
  files: []
  dirs: []
context:
  policies:
    - 你是kk，是我的个人助手
  facts:
    - 项目约束：避免披露敏感信息
  instructions:
    - 本轮任务：回答用户问题并引用相关片段
  examples:
    - 问：示例问题；答：示例回答
  priority:
    - policies
    - facts
    - instructions
    - examples
procedure:
  enabled: false
  steps: []
```

兼容旧配置：
- 旧 `sticky_docs` 等同于 `persona.sticky`
- 旧 `doc_files/doc_dirs` 等同于 `kb.files/kb.dirs`
- 旧 `context` 列表等同于 `context.facts` 或 `context.add`
- 旧 `procedure_enabled/procedure_steps` 等同于 `procedure.enabled/procedure.steps`

## 模型配置
- 不在 YAML 中配置模型；在加载时通过入参传入：
  - `load_context_app("configs/context.yaml", tools=[...], model="qwen-plus")`
- 未指定时默认使用 `qwen-plus`

## Agentscope 示例
- 运行示例：`python examples/agentscope_demo.py`
- 未安装时提示：`python -m pip install agentscope`

## 发布到 GitHub
- 将 `contextmgr` 目录与 `configs/*`、`examples/*` 独立为仓库
- 添加 `pyproject.toml`/`setup.cfg` 以打包发布（可选）
- 在 README 中注明依赖与最小集成代码片段
