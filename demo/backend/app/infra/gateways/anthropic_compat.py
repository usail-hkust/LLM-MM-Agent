"""
Helpers for Anthropic-compatible providers such as MiniMax.
"""
from typing import Any, Dict, List, Optional


def is_anthropic_compatible_base(base_url: Optional[str]) -> bool:
    if not base_url:
        return False
    lowered = base_url.lower()
    return "anthropic.com" in lowered or "/anthropic" in lowered


def normalize_anthropic_model(model: Optional[str]) -> str:
    if not model:
        return ""
    return model.removeprefix("anthropic/")


def anthropic_messages_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/messages"):
        return base
    if base.endswith("/v1"):
        return f"{base}/messages"
    return f"{base}/v1/messages"


def anthropic_base_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/messages"):
        base = base[: -len("/messages")]
    if base.endswith("/v1"):
        base = base[: -len("/v1")]
    return base


def anthropic_headers(api_key: str, base_url: Optional[str] = None) -> Dict[str, str]:
    headers = {
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    lowered = (base_url or "").lower()
    if "minimax" in lowered or "minimaxi" in lowered:
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        headers["x-api-key"] = api_key
    return headers


def anthropic_payload(
    messages: List[Dict[str, Any]],
    model: str,
    *,
    max_tokens: int = 4096,
    temperature: Optional[float] = None,
    stream: bool = False,
) -> Dict[str, Any]:
    system_parts: List[str] = []
    anthropic_messages: List[Dict[str, str]] = []

    for message in messages:
        role = str(message.get("role", "user"))
        content = message.get("content", "")
        if not isinstance(content, str):
            content = str(content)

        if role == "system":
            if content:
                system_parts.append(content)
            continue

        if role not in {"user", "assistant"}:
            role = "user"

        if anthropic_messages and anthropic_messages[-1]["role"] == role:
            anthropic_messages[-1]["content"] = (
                f"{anthropic_messages[-1]['content']}\n\n{content}"
            )
        else:
            anthropic_messages.append({"role": role, "content": content})

    if not anthropic_messages:
        anthropic_messages.append({"role": "user", "content": "Hi"})

    payload: Dict[str, Any] = {
        "model": normalize_anthropic_model(model),
        "max_tokens": max_tokens,
        "messages": anthropic_messages,
    }
    if stream:
        payload["stream"] = True
    if system_parts:
        payload["system"] = "\n\n".join(system_parts)
    if temperature is not None:
        payload["temperature"] = temperature
    return payload


def extract_anthropic_text(data: Dict[str, Any]) -> str:
    text_parts: List[str] = []
    thinking_parts: List[str] = []

    for block in data.get("content", []):
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "text":
            text_parts.append(block.get("text", ""))
        elif block_type == "thinking":
            thinking_parts.append(block.get("thinking", ""))

    text = "".join(text_parts).strip()
    if text:
        return text
    return "".join(thinking_parts).strip()
