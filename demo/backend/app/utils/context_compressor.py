"""Token-budgeted context management for every LLM provider.

The database remains the source of truth for complete workflow/chat history. This
module only builds a bounded working set for an individual model request.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MESSAGE_OVERHEAD_TOKENS = 4
TRUNCATION_MARKER = (
    "\n\n... [middle context omitted by the local context manager] ...\n\n"
)


def estimate_tokens(text: str) -> int:
    """Return a conservative tokenizer-independent token estimate."""
    if not text:
        return 0

    if not isinstance(text, str):
        text = str(text)

    byte_estimate = math.ceil(len(text.encode("utf-8")) / 2)
    word_estimate = math.ceil(len(re.findall(r"\S+", text)) * 1.3)
    return max(1, byte_estimate, word_estimate)


def estimate_message_tokens(message: Dict[str, Any]) -> int:
    """Estimate content plus a small amount of chat-format overhead."""
    return MESSAGE_OVERHEAD_TOKENS + estimate_tokens(message.get("content", ""))


def calculate_input_budget(
    context_window_tokens: int,
    max_output_tokens: int,
    safety_tokens: int,
    *,
    minimum_input_tokens: int = 256,
) -> Tuple[int, int, int]:
    """Return input budget, output reserve, and effective safety reserve."""
    context_window = max(minimum_input_tokens + 1, int(context_window_tokens))
    output_reserve = min(
        max(1, int(max_output_tokens)), max(1, context_window // 2)
    )
    safety_reserve = min(
        max(0, int(safety_tokens)),
        max(0, context_window - output_reserve - minimum_input_tokens),
    )
    input_budget = max(
        minimum_input_tokens,
        context_window - output_reserve - safety_reserve,
    )
    return input_budget, output_reserve, safety_reserve


@dataclass
class CompressionConfig:
    """Defaults used when a caller does not provide a request-specific budget."""

    max_total_tokens: int = 120_000
    keep_recent_messages: int = 10
    recent_message_share: float = 0.5


class ContextCompressor:
    """Create a bounded working context without mutating persisted history.

    When compression is required, the most recent conversation messages receive
    up to half of the budget. System messages receive the remaining budget, and
    any unused space is filled with older conversation messages. Oversized
    individual messages retain both their beginning and end because workflow
    prompts keep identity near the beginning and current instructions near the
    end.
    """

    def __init__(self, config: Optional[CompressionConfig] = None):
        self.config = config or CompressionConfig()

    def compress(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
        preserve_system: bool = True,
    ) -> List[Dict[str, Any]]:
        """Fit messages within ``max_tokens`` while preserving useful recency."""
        if not messages:
            return []

        max_total = int(
            self.config.max_total_tokens if max_tokens is None else max_tokens
        )
        if max_total <= MESSAGE_OVERHEAD_TOKENS:
            return []

        normalized = [self._normalize_message(message) for message in messages]
        current_tokens = sum(estimate_message_tokens(message) for message in normalized)
        if current_tokens <= max_total:
            return normalized

        indexed = list(enumerate(normalized))
        system = [item for item in indexed if item[1].get("role") == "system"]
        conversation = [item for item in indexed if item[1].get("role") != "system"]
        selected: Dict[int, Dict[str, Any]] = {}

        # Protect recent turns, but never let one huge user message evict the
        # workflow/system instructions entirely.
        if conversation and system and preserve_system:
            recent_budget = max(
                MESSAGE_OVERHEAD_TOKENS + 1,
                int(max_total * self.config.recent_message_share),
            )
        elif conversation:
            recent_budget = max_total
        else:
            recent_budget = 0

        recent_candidates = conversation[-self.config.keep_recent_messages :]
        selected.update(self._fit_recent_group(recent_candidates, recent_budget))

        used = self._selected_tokens(selected)
        remaining = max(0, max_total - used)

        if system and preserve_system and remaining > MESSAGE_OVERHEAD_TOKENS:
            selected.update(self._fit_recent_group(system, remaining))

        # Use space left by short system prompts to recover additional older
        # turns, newest first.
        used = self._selected_tokens(selected)
        remaining = max(0, max_total - used)
        older_candidates = [item for item in conversation if item[0] not in selected]
        if older_candidates and remaining > MESSAGE_OVERHEAD_TOKENS:
            selected.update(self._fit_recent_group(older_candidates, remaining))

        result = [selected[index] for index in sorted(selected)]
        final_tokens = sum(estimate_message_tokens(message) for message in result)
        if final_tokens > max_total:
            result = self._emergency_truncate(result, max_total)
            final_tokens = sum(estimate_message_tokens(message) for message in result)

        logger.info(
            "Context working set compressed: %s -> %s estimated tokens (%s -> %s messages)",
            current_tokens,
            final_tokens,
            len(messages),
            len(result),
        )
        return result

    def compress_for_node(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        node_context: str,
        max_context_tokens: int = 120_000,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """Bound both node context and conversation history for legacy callers."""
        reserved = estimate_tokens(system_prompt) + 1_000
        context_budget = max(0, max_context_tokens - reserved)
        bounded_context = self._truncate_text(node_context, context_budget)
        history_budget = max(
            0,
            max_context_tokens
            - estimate_tokens(system_prompt)
            - estimate_tokens(bounded_context)
            - 1_000,
        )
        history = [message for message in messages if message.get("role") != "system"]
        return self.compress(history, max_tokens=history_budget), bounded_context

    def compact_text(self, text: str, max_tokens: int) -> str:
        """Build a bounded text view while leaving the durable source untouched."""
        return self._truncate_text(text, max_tokens)

    def _fit_recent_group(
        self,
        indexed_messages: List[Tuple[int, Dict[str, Any]]],
        budget: int,
    ) -> Dict[int, Dict[str, Any]]:
        """Keep newest entries first and truncate the boundary entry if needed."""
        selected: Dict[int, Dict[str, Any]] = {}
        remaining = budget

        for index, message in reversed(indexed_messages):
            if remaining <= MESSAGE_OVERHEAD_TOKENS:
                break

            message_tokens = estimate_message_tokens(message)
            if message_tokens <= remaining:
                selected[index] = message
                remaining -= message_tokens
                continue

            fitted = self._fit_message(message, remaining)
            if fitted:
                selected[index] = fitted
            break

        return selected

    def _fit_message(
        self, message: Dict[str, Any], token_budget: int
    ) -> Optional[Dict[str, Any]]:
        content_budget = token_budget - MESSAGE_OVERHEAD_TOKENS
        if content_budget <= 0:
            return None

        fitted = dict(message)
        fitted["content"] = self._truncate_text(fitted.get("content", ""), content_budget)
        if not fitted["content"]:
            return None
        return fitted

    def _truncate_text(self, text: str, max_tokens: int) -> str:
        """Keep the head and tail of text and always honor the token budget."""
        if not text or max_tokens <= 0:
            return ""
        if not isinstance(text, str):
            text = str(text)
        if estimate_tokens(text) <= max_tokens:
            return text

        marker = TRUNCATION_MARKER
        if estimate_tokens(marker) >= max_tokens:
            return self._prefix_within_budget(marker.strip(), max_tokens)

        # Bias toward the tail, where current instructions and recent history
        # normally live in this application.
        low, high = 0, len(text)
        best = marker
        while low <= high:
            retained = (low + high) // 2
            head_chars = int(retained * 0.35)
            tail_chars = retained - head_chars
            tail = text[-tail_chars:] if tail_chars else ""
            candidate = f"{text[:head_chars]}{marker}{tail}"
            if estimate_tokens(candidate) <= max_tokens:
                best = candidate
                low = retained + 1
            else:
                high = retained - 1

        while best and estimate_tokens(best) > max_tokens:
            best = best[:-1]
        return best

    def _prefix_within_budget(self, text: str, max_tokens: int) -> str:
        low, high = 0, len(text)
        best = ""
        while low <= high:
            mid = (low + high) // 2
            candidate = text[:mid]
            if estimate_tokens(candidate) <= max_tokens:
                best = candidate
                low = mid + 1
            else:
                high = mid - 1
        return best

    def _emergency_truncate(
        self, messages: List[Dict[str, Any]], max_tokens: int
    ) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        remaining = max_tokens
        for message in reversed(messages):
            if remaining <= MESSAGE_OVERHEAD_TOKENS:
                break
            message_tokens = estimate_message_tokens(message)
            if message_tokens <= remaining:
                result.insert(0, message)
                remaining -= message_tokens
                continue
            fitted = self._fit_message(message, remaining)
            if fitted:
                result.insert(0, fitted)
            break
        return result

    @staticmethod
    def _normalize_message(message: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(message)
        normalized["role"] = str(normalized.get("role", "user"))
        content = normalized.get("content", "")
        normalized["content"] = content if isinstance(content, str) else str(content)
        return normalized

    @staticmethod
    def _selected_tokens(selected: Dict[int, Dict[str, Any]]) -> int:
        return sum(estimate_message_tokens(message) for message in selected.values())

    def count_tokens(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Return estimated token usage for logging and tests."""
        total = 0
        by_role: Dict[str, int] = {}
        for message in messages:
            role = str(message.get("role", "unknown"))
            tokens = estimate_message_tokens(message)
            total += tokens
            by_role[role] = by_role.get(role, 0) + tokens
        return {"total": total, "by_role": by_role, "message_count": len(messages)}


_context_compressor: Optional[ContextCompressor] = None


def get_compressor() -> ContextCompressor:
    """Return the process-wide stateless context compressor."""
    global _context_compressor
    if _context_compressor is None:
        _context_compressor = ContextCompressor()
    return _context_compressor


def compress_llm_context(
    messages: List[Dict[str, Any]], max_tokens: int = 120_000
) -> List[Dict[str, Any]]:
    """Compatibility helper for callers outside the gateway."""
    return get_compressor().compress(messages, max_tokens=max_tokens)
