import yaml
from typing import Any, Iterable
from langchain_community.chat_models import ChatTongyi
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage
from src.chat_state import ChatState
from src.retrieval import DocStore
from src.app import _invoke_tool

def _build_effective_messages(state: ChatState) -> list[BaseMessage]:
    msgs = []
    if state.get("system"):
        msgs.append(SystemMessage(content=state["system"]))
    # Multi-bucket aggregation into a single contextual SystemMessage (backward compatible with "上下文:")
    buckets = [
        ("policies", state.get("context_policies") or []),
        ("facts", state.get("context_facts") or []),
        ("instructions", state.get("context_instructions") or []),
        ("examples", state.get("context_examples") or []),
    ]
    # Priority order
    priority = state.get("context_priority") or ["policies", "facts", "instructions", "examples"]
    order = {name: i for i, name in enumerate(priority)}
    buckets.sort(key=lambda x: order.get(x[0], 999))
    has_any = any(len(lines) > 0 for _, lines in buckets)
    if has_any:
        parts: list[str] = ["上下文:"]
        for name, lines in buckets:
            if not lines:
                continue
            title = {"policies": "Policies", "facts": "Facts", "instructions": "Instructions", "examples": "Examples"}.get(name, name)
            parts.append(f"- {title}:")
            parts.extend([str(line) for line in lines])
        msgs.append(SystemMessage(content="\n".join(parts)))
    if state.get("procedure_enabled") and (state.get("procedure_steps") or []):
        steps = state.get("procedure_steps") or []
        idx = (state.get("procedure_step") or 0)
        cur = steps[idx] if idx < len(steps) else None
        guide = f"执行流程（共{len(steps)}步）：当前第{idx+1}步 -> {cur}. 必须按步骤输出。"
        msgs.append(SystemMessage(content=guide))
    msgs.extend(state.get("messages") or [])
    return msgs

def load_context_app(config_path: str, tools: Iterable[object] | None = None, model: str | None = None):
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # model configuration is decoupled from YAML; respect provided arg or fallback
    llm = ChatTongyi(model=model or "qwen-plus")
    if tools and hasattr(llm, "bind_tools"):
        llm = llm.bind_tools(list(tools))
    ds = DocStore()
    # sticky docs: support both new and legacy keys
    sticky_list = list(cfg.get("sticky_docs") or [])
    persona = cfg.get("persona") or {}
    sticky_list += list(persona.get("sticky") or [])
    for t in sticky_list or []:
        ds.add_sticky(str(t))
    # kb files/dirs: support both new and legacy keys
    kb = cfg.get("kb") or {}
    files_list = list(cfg.get("doc_files") or []) + list(kb.get("files") or [])
    dirs_list = list(cfg.get("doc_dirs") or []) + list(kb.get("dirs") or [])
    for p in files_list or []:
        ds.add_file(str(p))
    for d in dirs_list or []:
        ds.add_dir(str(d))
    initial_system = cfg.get("system")
    # multi-bucket context initialization: support legacy flat context and new buckets
    raw_ctx = cfg.get("context")
    ctx_dict = raw_ctx if isinstance(raw_ctx, dict) else {}
    # legacy: flat list or dict with "add"
    legacy_flat = raw_ctx if isinstance(raw_ctx, list) else (ctx_dict.get("add") or [])
    initial_policies = list(ctx_dict.get("policies") or [])
    initial_facts = list(ctx_dict.get("facts") or legacy_flat or [])
    initial_instructions = list(ctx_dict.get("instructions") or [])
    initial_examples = list(ctx_dict.get("examples") or [])
    initial_priority = list(ctx_dict.get("priority") or ["policies", "facts", "instructions", "examples"])
    # procedure: support legacy and new nested
    procedure_enabled = bool(cfg.get("procedure_enabled") or (cfg.get("procedure") or {}).get("enabled") or False)
    procedure_steps = (cfg.get("procedure") or {}).get("steps") or cfg.get("procedure_steps") or []

    def chat_llm(state: ChatState):
        effective = _build_effective_messages(state)
        ai = llm.invoke(effective)
        return {"messages": [ai]}

    def run_tools(state: ChatState):
        last = state["messages"][-1]
        calls = getattr(last, "tool_calls", None) or []
        results: list[ToolMessage] = []
        for call in calls:
            name = call.get("name")
            args = call.get("args") or {}
            if tools:
                for t in tools:
                    key = getattr(t, "name", None) or getattr(t, "__name__", None) or str(t)
                    if key == name:
                        out = _invoke_tool(t, args)
                        results.append(ToolMessage(content=str(out), tool_call_id=call.get("id") or ""))
                        break
        return {"messages": results}

    def prepare_ctx(state: ChatState):
        # existing buckets
        policies = list(state.get("context_policies") or [])
        facts = list(state.get("context_facts") or [])
        instructions = list(state.get("context_instructions") or [])
        examples = list(state.get("context_examples") or [])
        # retrieval
        last = state["messages"][-1]
        query = getattr(last, "content", "")
        # sticky -> policies; retrieval -> facts
        for d in ds.sticky():
            if d not in policies:
                policies.append(d)
        for d in ds.retrieve(str(query)):
            # Support Source URL Injection if DocStore returns objects with metadata
            if hasattr(d, "metadata") and hasattr(d, "page_content"):
                source = d.metadata.get("source", "unknown")
                content = d.page_content
                formatted = f"Source: {source}\nContent: {content}"
                if formatted not in facts:
                    facts.append(formatted)
            else:
                if d not in facts:
                    facts.append(d)
        # aggregate view "context" for backward compatibility, ordered by priority
        priority = state.get("context_priority") or ["policies", "facts", "instructions", "examples"]
        bucket_map = {"policies": policies, "facts": facts, "instructions": instructions, "examples": examples}
        merged: list[str] = []
        for name in priority:
            for d in bucket_map.get(name, []):
                if d not in merged:
                    merged.append(d)
        return {
            "context_policies": policies,
            "context_facts": facts,
            "context_instructions": instructions,
            "context_examples": examples,
            "context": merged,
        }

    builder = StateGraph(ChatState)
    builder.add_node("prepare_ctx", prepare_ctx)
    builder.add_node("chat_llm", chat_llm)
    builder.add_node("run_tools", run_tools)
    builder.add_edge("prepare_ctx", "chat_llm")
    builder.add_edge("run_tools", "chat_llm")
    builder.set_entry_point("prepare_ctx")
    builder.add_conditional_edges("chat_llm", lambda s: "run_tools" if getattr(s["messages"][-1], "tool_calls", None) else END)
    checkpointer = MemorySaver()
    app = builder.compile(checkpointer=checkpointer)

    # Seed initial state if provided
    def seed(thread_id: str):
        seed_values: dict[str, Any] = {}
        if initial_system:
            seed_values["system"] = initial_system
        # set multi-bucket
        if initial_policies:
            seed_values["context_policies"] = list(initial_policies)
        if initial_facts:
            seed_values["context_facts"] = list(initial_facts)
        if initial_instructions:
            seed_values["context_instructions"] = list(initial_instructions)
        if initial_examples:
            seed_values["context_examples"] = list(initial_examples)
        if initial_priority:
            seed_values["context_priority"] = list(initial_priority)
        if procedure_enabled:
            seed_values["procedure_enabled"] = True
            if procedure_steps:
                seed_values["procedure_steps"] = list(procedure_steps)
                seed_values["procedure_step"] = 0
        if seed_values:
            app.update_state({"configurable": {"thread_id": thread_id}}, seed_values)
    return app, seed, ds
