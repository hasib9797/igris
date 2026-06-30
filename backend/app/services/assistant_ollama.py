from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from backend.app.config import AppConfig
from backend.app.security.ai_gateway import build_gateway_headers


DISPLAY_MODEL = "shadow-core"


def _context_digest(context: dict[str, Any]) -> str:
    explain = context.get("explain", {})
    apps = context.get("apps", [])[:8]
    incidents = [item for item in context.get("incidents", []) if item.get("status") == "open"][:8]
    ports = context.get("ports", [])[:16]
    firewall = context.get("firewall", "")
    payload = {
        "summary": explain.get("summary", ""),
        "recommendations": explain.get("recommendations", [])[:8],
        "apps": [
            {
                "name": item.get("name"),
                "type": item.get("app_type"),
                "runtime": item.get("runtime"),
                "status": item.get("status"),
                "ports": item.get("ports", []),
                "service": item.get("service_name"),
                "public_domain": item.get("public_domain"),
            }
            for item in apps
        ],
        "incidents": [
            {
                "title": item.get("title"),
                "severity": item.get("severity"),
                "resource_key": item.get("resource_key"),
                "suggested_fix": item.get("suggested_fix"),
            }
            for item in incidents
        ],
        "ports": ports,
        "firewall": firewall[:1200],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _extract_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    raise ValueError("Ollama response did not contain valid JSON")


def ollama_chat(config: AppConfig, *, system_prompt: str, user_prompt: str) -> str:
    model_name = config.assistant.ollama_model.strip() or DISPLAY_MODEL
    payload = {
        "model": model_name,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "options": {"temperature": 0.2},
    }
    if config.assistant.gateway_url.strip():
        target_url = f"{config.assistant.gateway_url.rstrip('/')}/api/chat"
        if not config.assistant.gateway_shared_secret.strip():
            raise RuntimeError("AI gateway secret is not configured on this server")
        headers = build_gateway_headers(config, payload)
    else:
        target_url = f"{config.assistant.ollama_url.rstrip('/')}/api/chat"
        headers = {"Content-Type": "application/json"}
    request = urllib.request.Request(
        target_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.assistant.ollama_timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Ollama request failed with status {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Ollama request failed: {exc.reason}") from exc

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Ollama returned invalid JSON") from exc
    message = data.get("message", {})
    content = message.get("content", "")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Ollama returned an empty response")
    return content


def generate_assistant_payload(config: AppConfig, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
    system_prompt = (
        "You are Igris AI Root Assistant, a cautious Linux server operations copilot. "
        "You help with Ubuntu and Debian servers. Only recommend commands that are useful, realistic, and concise. "
        "Never hallucinate server facts. If unsure, say so. "
        "Return strict JSON with keys summary, reasoning, suggestions. "
        "summary is a short paragraph. reasoning is an array of 2 to 5 short strings. "
        "suggestions is an array of objects with keys label, reason, command, risk, requires_confirmation. "
        "Risk must be low, medium, or high. Use read-only commands whenever possible first."
    )
    user_prompt = (
        f"Server context:\n{_context_digest(context)}\n\n"
        f"Operator request:\n{prompt}\n\n"
        "Answer with JSON only."
    )
    return _extract_json_object(ollama_chat(config, system_prompt=system_prompt, user_prompt=user_prompt))


def generate_server_pulse(config: AppConfig, *, context: dict[str, Any]) -> dict[str, Any]:
    system_prompt = (
        "You are generating a server pulse for Igris. Return strict JSON with keys heading, summary, actions. "
        "heading is a short title. summary is 2 or 3 sentences. actions is an array of 3 short action strings. "
        "Keep it practical for a server operator."
    )
    user_prompt = f"Server context:\n{_context_digest(context)}\n\nReturn JSON only."
    return _extract_json_object(ollama_chat(config, system_prompt=system_prompt, user_prompt=user_prompt))


def generate_command_explanation(config: AppConfig, *, command: str, base: dict[str, Any]) -> dict[str, Any]:
    system_prompt = (
        "You explain Linux shell commands for Igris. Return strict JSON with keys summary, dangerous, safer_command, next_steps. "
        "dangerous is true or false. safer_command is a safer alternative when appropriate. "
        "next_steps is an array of 3 short operator tips."
    )
    user_prompt = (
        f"Command: {command}\n"
        f"Current local analysis: {json.dumps(base, sort_keys=True)}\n"
        "Improve the explanation while staying realistic. Return JSON only."
    )
    payload = _extract_json_object(ollama_chat(config, system_prompt=system_prompt, user_prompt=user_prompt))
    payload["command"] = command
    return payload
