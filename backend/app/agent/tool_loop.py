from __future__ import annotations

import json
from typing import Any, Callable, Optional

from app.tools import ToolRegistry

LLMCaller = Callable[[list[dict[str, Any]], Optional[list[dict[str, Any]]]], dict[str, Any]]


class AgentToolLoop:
    """Bridge OpenAI-compatible tool calls to ToolRegistry."""

    MAX_TOOL_RESULT_LENGTH = 4000

    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._tools = tool_registry

    def run(self, agent: dict[str, Any], prompt: str, context: dict[str, Any], llm_caller: LLMCaller) -> dict[str, Any]:
        tool_defs = self._build_tool_defs(list(agent.get("tools_allowed") or []))
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._build_system_prompt(agent, tool_defs, context)},
            {"role": "user", "content": prompt},
        ]
        tool_calls_log: list[dict[str, Any]] = []
        max_turns = int(agent.get("max_turns") or 8)

        for turn in range(max_turns):
            response = llm_caller(messages, tool_defs or None)
            choice = (response.get("choices") or [{}])[0]
            message = dict(choice.get("message") or {})
            finish_reason = str(choice.get("finish_reason") or "")
            tool_calls = list(message.get("tool_calls") or [])

            if finish_reason == "tool_calls" or tool_calls:
                messages.append(message)
                for tc in tool_calls:
                    function = tc.get("function") or {}
                    name = str(function.get("name") or "")
                    try:
                        args = json.loads(function.get("arguments") or "{}")
                    except json.JSONDecodeError as exc:
                        args = {}
                        result_dict = {"status": "error", "error": f"invalid tool arguments: {exc}"}
                    else:
                        result = self._tools.invoke(name, args, source="agent", confirmed=True)
                        result_dict = result.model_dump(mode="json")
                    tool_calls_log.append({"turn": turn, "tool": name, "args": args, "result": result_dict})
                    content = json.dumps(result_dict, ensure_ascii=False, default=str)
                    if len(content) > self.MAX_TOOL_RESULT_LENGTH:
                        content = content[: self.MAX_TOOL_RESULT_LENGTH] + "..."
                    messages.append({"role": "tool", "tool_call_id": tc.get("id") or f"call_{turn}_{len(tool_calls_log)}", "content": content})
                continue

            content = message.get("content") or message.get("reasoning_content") or ""
            return {"text": str(content), "tool_calls": tool_calls_log, "finish_reason": finish_reason}

        return {"text": "已达到最大对话轮次，请简化你的需求。", "tool_calls": tool_calls_log, "finish_reason": "max_turns"}

    def _build_tool_defs(self, allowed_names: list[str]) -> list[dict[str, Any]]:
        all_tools = {tool.name: tool for tool in self._tools.list_definitions()}
        defs: list[dict[str, Any]] = []
        for name in allowed_names:
            tool = all_tools.get(name)
            if not tool:
                continue
            defs.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": _schema_to_openai(tool.input_schema),
                    },
                }
            )
        return defs

    def _build_system_prompt(self, agent: dict[str, Any], tool_defs: list[dict[str, Any]], context: dict[str, Any]) -> str:
        base = str(agent.get("system_prompt") or "")
        if context:
            base += "\n\n上下文:\n" + json.dumps(context, ensure_ascii=False, default=str)[:1500]
        if not tool_defs:
            return base
        tool_desc = "\n".join(f"- {tool['function']['name']}: {tool['function']['description']}" for tool in tool_defs)
        return (
            f"{base}\n\n"
            f"你可以调用以下系统工具:\n{tool_desc}\n\n"
            "当需要获取系统数据、运行分析、创建条件单、查询事件或执行工作流时，优先调用工具。"
            "工具返回后，用中文解释关键结论和下一步动作。"
        )


def _schema_to_openai(schema: dict[str, Any]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    for key, value in schema.items():
        if isinstance(value, dict):
            properties[key] = value
        else:
            properties[key] = {"type": _map_type(str(value))}
        required.append(key)
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


def _map_type(value: str) -> str:
    if value in {"number", "integer", "boolean", "array", "object", "string"}:
        return value
    if value.endswith("[]"):
        return "array"
    return "string"
