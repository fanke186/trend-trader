from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.models import (
    AgentRunRequest,
    ChatMessage,
    ChatMessageRequest,
    ChatSession,
    GenerateSkillRequest,
    ModelProfile,
    ModelProvider,
    ScheduleSpec,
    SkillSpec,
)
from app.services import TrendTraderService


DATA_DIR = Path(__file__).resolve().parents[1] / ".data"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trend-trader")
    sub = parser.add_subparsers(dest="area", required=True)

    chat = sub.add_parser("chat")
    chat.add_argument("message", nargs="*", help="Optional one-shot message. Empty starts stdin chat.")

    tool = sub.add_parser("tool")
    tool_sub = tool.add_subparsers(dest="action", required=True)
    tool_sub.add_parser("list")
    invoke = tool_sub.add_parser("invoke")
    invoke.add_argument("name")
    invoke.add_argument("arguments", nargs="?", default="{}")
    invoke.add_argument("--confirmed", action="store_true")

    ai = sub.add_parser("ai")
    ai_sub = ai.add_subparsers(dest="kind", required=True)
    _add_ai_provider(ai_sub)
    _add_ai_model(ai_sub)

    skill = sub.add_parser("skill")
    skill_sub = skill.add_subparsers(dest="action", required=True)
    skill_sub.add_parser("list")
    skill_create = skill_sub.add_parser("create")
    skill_create.add_argument("--name", required=True)
    skill_create.add_argument("--description", default="")
    skill_create.add_argument("--instructions", default="")
    skill_generate = skill_sub.add_parser("generate")
    skill_generate.add_argument("--name", required=True)
    skill_generate.add_argument("--description", required=True)
    skill_generate.add_argument("--prompt", required=True)
    skill_import = skill_sub.add_parser("import")
    skill_import.add_argument("path")

    agent = sub.add_parser("agent")
    agent_sub = agent.add_subparsers(dest="action", required=True)
    agent_sub.add_parser("list")
    agent_run = agent_sub.add_parser("run")
    agent_run.add_argument("id", type=int)
    agent_run.add_argument("prompt")

    team = sub.add_parser("team")
    team_sub = team.add_subparsers(dest="action", required=True)
    team_sub.add_parser("list")
    team_run = team_sub.add_parser("run")
    team_run.add_argument("id", type=int)
    team_run.add_argument("prompt")

    schedule = sub.add_parser("schedule")
    schedule_sub = schedule.add_subparsers(dest="action", required=True)
    schedule_sub.add_parser("list")
    schedule_run = schedule_sub.add_parser("run")
    schedule_run.add_argument("id", type=int)
    schedule_enable = schedule_sub.add_parser("enable")
    schedule_enable.add_argument("id", type=int)
    schedule_disable = schedule_sub.add_parser("disable")
    schedule_disable.add_argument("id", type=int)
    schedule_logs = schedule_sub.add_parser("logs")
    schedule_logs.add_argument("id", type=int)
    schedule_create = schedule_sub.add_parser("create")
    schedule_create.add_argument("json")

    worker = sub.add_parser("worker")
    worker_sub = worker.add_subparsers(dest="action", required=True)
    worker_sub.add_parser("start")

    mcp = sub.add_parser("mcp")
    mcp_sub = mcp.add_subparsers(dest="action", required=True)
    mcp_sub.add_parser("serve")

    args = parser.parse_args(argv)
    service = TrendTraderService(DATA_DIR)
    output = _dispatch(service, args)
    if output is not None:
        _print_json(output)
    return 0


def _add_ai_provider(parent: argparse._SubParsersAction) -> None:
    provider = parent.add_parser("provider")
    sub = provider.add_subparsers(dest="action", required=True)
    sub.add_parser("list")
    add = sub.add_parser("add")
    add.add_argument("--name", required=True)
    add.add_argument("--provider-type", default="openai_compatible")
    add.add_argument("--base-url", required=True)
    add.add_argument("--api-key-env", required=True)
    test = sub.add_parser("test")
    test.add_argument("id", type=int)


def _add_ai_model(parent: argparse._SubParsersAction) -> None:
    model = parent.add_parser("model")
    sub = model.add_subparsers(dest="action", required=True)
    sub.add_parser("list")
    add = sub.add_parser("add")
    add.add_argument("--name", required=True)
    add.add_argument("--provider-id", type=int, required=True)
    add.add_argument("--model", required=True)
    test = sub.add_parser("test")
    test.add_argument("id", type=int)


def _dispatch(service: TrendTraderService, args: argparse.Namespace) -> Any:
    if args.area == "chat":
        return _chat(service, " ".join(args.message).strip())
    if args.area == "tool":
        if args.action == "list":
            return [item.model_dump(mode="json") for item in service.tools.list_definitions()]
        arguments = _loads(args.arguments)
        return service.tools.invoke(args.name, arguments, source="cli", confirmed=args.confirmed).model_dump(mode="json")
    if args.area == "ai":
        return _dispatch_ai(service, args)
    if args.area == "skill":
        return _dispatch_skill(service, args)
    if args.area == "agent":
        if args.action == "list":
            return service.repository.list_generic("agents")
        return service.run_agent(args.id, args.prompt, {}).model_dump(mode="json")
    if args.area == "team":
        if args.action == "list":
            return service.repository.list_generic("agent_teams")
        return service.run_team(args.id, args.prompt, {}).model_dump(mode="json")
    if args.area == "schedule":
        return _dispatch_schedule(service, args)
    if args.area == "worker":
        from app.worker import start_worker

        start_worker(DATA_DIR)
        return None
    if args.area == "mcp":
        return _serve_mcp(service)
    raise ValueError(f"unknown area {args.area}")


def _dispatch_ai(service: TrendTraderService, args: argparse.Namespace) -> Any:
    if args.kind == "provider":
        if args.action == "list":
            return service.repository.list_generic("model_providers")
        if args.action == "add":
            provider = ModelProvider(
                name=args.name,
                provider_type=args.provider_type,
                base_url=args.base_url,
                api_key_env=args.api_key_env,
            )
            return service.repository.save_generic("model_providers", provider.model_dump(mode="json"))
        if args.action == "test":
            profiles = [item for item in service.repository.list_generic("model_profiles") if int(item["provider_id"]) == args.id]
            if not profiles:
                return {"ok": False, "message": "provider has no model profile to test"}
            return service.test_model_profile(int(profiles[0]["id"])).model_dump(mode="json")
    if args.kind == "model":
        if args.action == "list":
            return service.repository.list_generic("model_profiles")
        if args.action == "add":
            profile = ModelProfile(name=args.name, provider_id=args.provider_id, model=args.model)
            return service.repository.save_generic("model_profiles", profile.model_dump(mode="json"))
        if args.action == "test":
            return service.test_model_profile(args.id).model_dump(mode="json")
    raise ValueError("unknown ai command")


def _dispatch_skill(service: TrendTraderService, args: argparse.Namespace) -> Any:
    if args.action == "list":
        return service.repository.list_generic("skills")
    if args.action == "create":
        skill = SkillSpec(name=args.name, description=args.description, instructions=args.instructions)
        return service.repository.save_generic("skills", skill.model_dump(mode="json"))
    if args.action == "generate":
        skill = service.generate_skill(
            GenerateSkillRequest(name=args.name, description=args.description, source_prompt=args.prompt)
        )
        return service.repository.save_generic("skills", skill.model_dump(mode="json"))
    if args.action == "import":
        payload = _loads(Path(args.path).read_text(encoding="utf-8"))
        skill = SkillSpec(**payload)
        return service.repository.save_generic("skills", skill.model_dump(mode="json"))
    raise ValueError("unknown skill command")


def _dispatch_schedule(service: TrendTraderService, args: argparse.Namespace) -> Any:
    if args.action == "list":
        return service.repository.list_generic("schedules")
    if args.action == "run":
        return service.run_schedule(args.id)
    if args.action == "logs":
        return service.repository.list_schedule_runs(args.id)
    if args.action == "create":
        schedule = ScheduleSpec(**_loads(args.json))
        service.validate_workflow(schedule.workflow)
        return service.repository.save_generic("schedules", schedule.model_dump(mode="json"))
    if args.action in {"enable", "disable"}:
        payload = service.repository.get_generic("schedules", args.id)
        payload["enabled"] = args.action == "enable"
        payload["status"] = "enabled" if args.action == "enable" else "disabled"
        return service.repository.save_generic("schedules", payload)
    raise ValueError("unknown schedule command")


def _chat(service: TrendTraderService, one_shot: str) -> Any:
    session = service.repository.save_chat_session(ChatSession(title="CLI Chat"))
    if one_shot:
        return _send_cli_chat_message(service, int(session["id"]), one_shot)
    print(f"session {session['id']} ready. Ctrl-D to exit.", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        response = _send_cli_chat_message(service, int(session["id"]), line)
        print(response["assistant"]["content"])
    return {"session": session}


def _send_cli_chat_message(service: TrendTraderService, session_id: int, content: str) -> dict[str, Any]:
    service.repository.save_chat_message(
        ChatMessage(
            session_id=session_id,
            role="user",
            content=content,
            payload={},
        )
    )
    if content.strip().startswith("/tool "):
        body = content.strip()[len("/tool "):]
        name, _, raw = body.partition(" ")
        arguments = _loads(raw or "{}")
        result = service.tools.invoke(name, arguments, source="cli-chat", confirmed=bool(arguments.get("confirmed")))
        assistant_content = json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2)
        payload = result.model_dump(mode="json")
    else:
        assistant_content = "CLI chat ready. Use /tool <name> <json> to operate trend-trader."
        payload = {"mode": "local_help"}
    assistant = service.repository.save_chat_message(
        ChatMessage(session_id=session_id, role="assistant", content=assistant_content, payload=payload)
    )
    return {"assistant": assistant}


def _mcp_descriptor(service: TrendTraderService) -> dict[str, Any]:
    return {
        "name": "trend-trader",
        "transport": "stdio-placeholder",
        "tools": [item.model_dump(mode="json") for item in service.tools.list_definitions()],
        "note": "This first version exposes a machine-readable tool manifest. External Hermes/OpenClaw can call the REST /api/tools/invoke endpoint.",
    }


def _serve_mcp(service: TrendTraderService) -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = _handle_mcp_request(service, request)
        except Exception as exc:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(exc)}}
        print(json.dumps(response, ensure_ascii=False), flush=True)
    return None


def _handle_mcp_request(service: TrendTraderService, request: dict[str, Any]) -> dict[str, Any]:
    request_id = request.get("id")
    method = request.get("method")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "trend-trader", "version": "0.1.0"},
            },
        }
    if method == "tools/list":
        tools = []
        for tool in service.tools.list_definitions():
            tools.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": {
                        "type": "object",
                        "additionalProperties": True,
                        "properties": {},
                    },
                }
            )
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tools}}
    if method == "tools/call":
        params = request.get("params") or {}
        result = service.tools.invoke(
            str(params.get("name")),
            dict(params.get("arguments") or {}),
            source="mcp",
            confirmed=bool(params.get("arguments", {}).get("confirmed")),
        )
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(result.model_dump(mode="json"), ensure_ascii=False)}],
                "isError": result.status == "error",
            },
        }
    if method == "notifications/initialized":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"unknown method {method}"}}


def _loads(raw: str) -> dict[str, Any]:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    raise SystemExit(main())
