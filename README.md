# Context Bucket (HaoChat)

Context Bucket 是一个基于 **LangGraph** 和 **LlamaIndex** 的高级上下文管理与增强生成 (RAG) 框架。它实现了“6类上下文体系”的精细化管理，支持基于 YAML 的灵活配置、多用户会话管理以及带有 Source URL 注入的文档检索功能。

## 核心特性

*   **6 类上下文体系**：将上下文解构为 System, Policies, Facts, Instructions, Examples, Procedure，精细控制 LLM 输入。
*   **Source URL 注入**：RAG 检索结果自动携带来源元数据（Source URL/文件路径），增强回答可信度。
*   **YAML 驱动配置**：通过 `configs/context.yaml` 定义角色、知识库、粘性文档和流程控制。
*   **模块化 RAG**：内置 `DocStore` (基于 LlamaIndex)，支持文件/目录加载、向量检索与自动分块。
*   **交互式 CLI**：提供开箱即用的命令行界面，支持实时查看上下文状态 (`/context`)。
*   **多用户会话**：内置 `SessionManager`，支持基于 `thread_id` 的会话隔离与持久化。

## 目录结构

```text
.
├── cli.py                  # 交互式命令行入口
├── configs/
│   └── context.yaml        # 核心配置文件
├── contextmgr/             # 上下文管理核心组件
│   ├── loader.py           # 上下文加载与组装逻辑
│   └── ...
├── src/                    # 运行时与 RAG 实现
│   ├── retrieval.py        # DocStore 实现 (LlamaIndex 封装)
│   ├── chat_state.py       # LangGraph 状态定义
│   └── ...
└── examples/               # 集成示例
```

## 快速开始

### 1. 安装依赖

本项目依赖 `langgraph`, `langchain`, `llama-index` 以及 `dashscope` (用于通义千问模型)。

```bash
pip install -r requirements.txt
# 或者手动安装核心库
pip install langgraph langchain langchain-community llama-index llama-index-core llama-index-embeddings-dashscope dashscope
```

### 2. 配置环境

确保已设置 DashScope API Key（用于 LLM 和 Embedding）：

**Windows PowerShell**:
```powershell
$env:DASHSCOPE_API_KEY = "your-api-key"
```

### 3. 运行 CLI

启动交互式对话：

```bash
python cli.py
```

在对话中：
- 直接输入问题进行对话。
- 输入 `/context` 查看当前完整的上下文状态（包含 System Prompt, RAG 检索到的 Facts 等）。
- 输入 `exit` 或 `quit` 退出。

## 配置说明 (`configs/context.yaml`)

```yaml
system: "你是智能助手..."
# 粘性文档（始终存在于上下文）
sticky_docs:
  - "重要规范：..."
# 知识库（RAG 检索源）
doc_files:
  - "path/to/document.txt"
doc_dirs:
  - "path/to/knowledge_base/"
# 上下文桶配置
context:
  policies: []
  facts: []
  priority: ["policies", "facts", "instructions", "examples"]
```

## RAG 与 Source URL 注入

系统会自动加载 `doc_files` 和 `doc_dirs` 中的文档。当用户提问触发检索时，检索到的文档片段将自动注入到 **Facts** 桶中，并附带来源信息：

```text
[Facts]:
  - Source: c:\work\docs\manual.pdf
    Content: ...文档相关内容...
```

## 许可证

[MIT License](LICENSE)
