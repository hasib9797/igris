from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import get_config
from backend.app.models import AIActionRecord
from backend.app.services import applications, explain, incidents, system_map
from backend.app.services.command import run_command
from backend.app.services.modules import firewall as firewall_service
from backend.app.services.modules import logs as log_service
from backend.app.services.modules import network as network_service


SAFE_COMMANDS = [
    re.compile(r"^systemctl (status|restart|reload) [a-zA-Z0-9@._-]+$"),
    re.compile(r"^journalctl -u [a-zA-Z0-9@._-]+ -n \d+ --no-pager$"),
    re.compile(r"^nginx -t$"),
    re.compile(r"^ufw status$"),
    re.compile(r"^ss -tulpn$"),
    re.compile(r"^ls -la .+$"),
    re.compile(r"^tail -n \d+ .+$"),
    re.compile(r"^git -C .+ pull origin .+$"),
]


@dataclass
class AssistantSuggestion:
    label: str
    reason: str
    command: str
    risk: str
    requires_confirmation: bool = True


@dataclass
class AssistantAnswer:
    summary: str
    reasoning: list[str]
    suggestions: list[AssistantSuggestion]
    context: dict


class AssistantProvider(Protocol):
    def answer(self, db: Session, prompt: str) -> AssistantAnswer:
        ...


def build_server_context(db: Session) -> dict:
    return {
        "explain": explain.explain_server(db),
        "apps": applications.list_apps(db),
        "incidents": incidents.list_incidents(db),
        "ports": network_service.get_ports(),
        "firewall": firewall_service.ufw_status(),
        "system_map": system_map.build_system_map(db),
    }


class LocalHeuristicAssistant:
    def answer(self, db: Session, prompt: str) -> AssistantAnswer:
        context = build_server_context(db)
        lower = prompt.lower()
        reasoning: list[str] = []
        suggestions: list[AssistantSuggestion] = []

        if "nginx" in lower or "reverse proxy" in lower:
            nginx_logs = log_service.service_logs("nginx", lines=60)
            reasoning.append("Checked nginx-oriented context because the question mentions the reverse proxy path.")
            reasoning.append("Collected recent nginx logs and current open incidents to look for config or reload problems.")
            if "failed" in nginx_logs.lower() or "error" in nginx_logs.lower():
                suggestions.append(AssistantSuggestion("Validate nginx config", "nginx logs include errors or failures", "nginx -t", "medium"))
                suggestions.append(AssistantSuggestion("Reload nginx after fix", "reload is safe after a clean config test", "systemctl reload nginx", "medium"))
            summary = "Nginx is the first place to inspect here. Igris sees the reverse-proxy path as the likely source of the issue."
        elif "not reachable" in lower or "reachable" in lower or "port" in lower:
            reasoning.append("Compared listening ports, public apps, and firewall state because the prompt sounds like reachability troubleshooting.")
            suggestions.append(AssistantSuggestion("Inspect listening ports", "Confirm that the app is actually binding to the expected port", "ss -tulpn", "low", False))
            suggestions.append(AssistantSuggestion("Review firewall state", "Reachability often fails because UFW still blocks the path", "ufw status", "low", False))
            summary = "This looks like a reachability problem. The quickest path is to verify the process, port binding, and firewall state together."
        elif "deploy" in lower and "node" in lower:
            reasoning.append("Matched the request to an application deployment workflow and checked detected Node-based apps.")
            node_apps = [app for app in context["apps"] if app["runtime"] == "node"]
            if node_apps:
                first = node_apps[0]
                suggestions.append(AssistantSuggestion("Pull latest revision", "Update the source before rebuilding", f"git -C {first['path']} pull origin {first.get('branch') or 'main'}", "medium"))
                if first.get("service_name"):
                    suggestions.append(AssistantSuggestion("Restart service", "Bring the updated Node app back online", f"systemctl restart {first['service_name']}", "medium"))
            summary = "Igris found Node-oriented app context and can help with a safe pull/build/restart sequence."
        elif "what is running" in lower or "explain" in lower:
            reasoning.append("Built a full server summary because the request is about understanding the machine state.")
            summary = context["explain"]["summary"]
        else:
            reasoning.append("Used the current server overview, incidents, apps, ports, and firewall state to build a general operational answer.")
            summary = context["explain"]["summary"]
            if context["incidents"]:
                first = context["incidents"][0]
                if first["rule_key"] in {"failed-service", "crash-loop"}:
                    command = f"journalctl -u {first['resource_key']} -n 120 --no-pager"
                else:
                    command = "ufw status"
                suggestions.append(AssistantSuggestion("Inspect the top open issue", "There is already an open incident related to this server state", command, "low", first["rule_key"] in {"failed-service", "crash-loop"}))

        if not suggestions:
            suggestions.append(AssistantSuggestion("Explain open ports", "This is a safe, read-only visibility command", "ss -tulpn", "low", False))
        return AssistantAnswer(summary=summary, reasoning=reasoning, suggestions=suggestions, context=context)


def _provider() -> AssistantProvider:
    return LocalHeuristicAssistant()


def ask_assistant(db: Session, prompt: str, dry_run: bool = True) -> dict:
    if not get_config().assistant.enabled:
        raise PermissionError("AI assistant is disabled")
    answer = _provider().answer(db, prompt)
    record = AIActionRecord(
        prompt=prompt,
        summary=answer.summary,
        reasoning="\n".join(answer.reasoning),
        proposed_commands_json=json.dumps([item.__dict__ for item in answer.suggestions], sort_keys=True),
        executed_commands_json="[]",
        status="planned",
        dry_run=dry_run,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {
        "id": record.id,
        "summary": answer.summary,
        "reasoning": answer.reasoning,
        "suggestions": [item.__dict__ for item in answer.suggestions],
        "context": answer.context,
    }


def list_history(db: Session) -> list[dict]:
    items = db.scalars(select(AIActionRecord).order_by(AIActionRecord.created_at.desc())).all()
    output: list[dict] = []
    for item in items:
        try:
            proposed = json.loads(item.proposed_commands_json or "[]")
        except json.JSONDecodeError:
            proposed = []
        try:
            executed = json.loads(item.executed_commands_json or "[]")
        except json.JSONDecodeError:
            executed = []
        output.append(
            {
                "id": item.id,
                "prompt": item.prompt,
                "summary": item.summary,
                "reasoning": item.reasoning.splitlines() if item.reasoning else [],
                "suggestions": proposed,
                "executed_commands": executed,
                "status": item.status,
                "dry_run": item.dry_run,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
        )
    return output


def explain_command(command: str) -> dict:
    lower = command.lower().strip()
    dangerous = any(token in lower for token in ("rm -rf", "mkfs", "shutdown", "reboot", "iptables -f"))
    safer = command
    if "rm -rf" in lower:
        safer = command.replace("rm -rf", "rm -ri")
    return {
        "command": command,
        "dangerous": dangerous,
        "summary": "This command will execute directly on the server shell through Igris." if not dangerous else "This command can destroy data or sever access if used incorrectly.",
        "safer_command": safer,
        "next_steps": ["Check the current working directory", "Review the target service or file path", "Use dry-run or status commands first"],
    }


def execute_assistant_command(db: Session, prompt: str, command: str, dry_run: bool) -> dict:
    if not any(pattern.match(command) for pattern in SAFE_COMMANDS):
        raise PermissionError("This assistant action is outside the current safe-execution policy")
    result_payload = {"command": command, "dry_run": dry_run}
    if not dry_run:
        result = run_command(["/bin/bash", "-lc", command], timeout=120)
        result_payload |= {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
    record = AIActionRecord(
        prompt=prompt,
        summary="Assistant executed an approved action",
        reasoning="Execution was allowed because the command matched the safe action policy.",
        proposed_commands_json=json.dumps([{"command": command}], sort_keys=True),
        executed_commands_json=json.dumps([result_payload], sort_keys=True),
        status="executed" if not dry_run else "dry-run",
        dry_run=dry_run,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"record_id": record.id, **result_payload}
