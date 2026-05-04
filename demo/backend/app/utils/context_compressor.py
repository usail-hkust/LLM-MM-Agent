"""
Context Compression Utility (v1.0).
Automatically compresses conversation context to stay within token limits.

Features:
- Token estimation
- Priority-based compression (system > user > assistant)
- Rolling window for history
- Configurable max tokens per message type
"""
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Rough token estimation (English: ~4 chars/token, Chinese: ~2 chars/token)
def estimate_tokens(text: str) -> int:
    """Estimate token count for a text string."""
    if not text:
        return 0
    # Count Chinese characters (roughly 2 chars/token)
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    # Count English words (roughly 4 chars/token)
    english_chars = len(text) - chinese_chars
    # Estimate words (split by whitespace)
    words = len(text.split())
    # Rough formula: chinese_chars/2 + english_chars/4 + words*1.3
    return max(1, int(chinese_chars / 2 + english_chars / 4 + words * 1.3))


def estimate_message_tokens(message: Dict[str, str]) -> int:
    """Estimate token count for a message dict."""
    role = len(message.get("role", ""))
    content = message.get("content", "")
    return role + estimate_tokens(content)


@dataclass
class CompressionConfig:
    """Configuration for context compression."""
    max_total_tokens: int = 120000  # Total budget for context
    max_system_tokens: int = 8000   # System prompt budget
    max_user_tokens: int = 60000    # User messages budget
    max_assistant_tokens: int = 40000  # Assistant responses budget
    keep_recent_messages: int = 10   # Always keep last N messages
    compression_ratio: float = 0.7   # Compress to 70% when truncating


class ContextCompressor:
    """
    Automatically compresses conversation context to fit within token limits.
    
    Priority Order (highest to lowest):
    1. System prompt (never compressed, just truncated if needed)
    2. Most recent user messages
    3. Assistant responses in between
    4. Older history (compressed or removed)
    """
    
    def __init__(self, config: Optional[CompressionConfig] = None):
        self.config = config or CompressionConfig()
    
    def compress(
        self, 
        messages: List[Dict[str, str]], 
        max_tokens: Optional[int] = None,
        preserve_system: bool = True
    ) -> List[Dict[str, str]]:
        """
        Compress messages to fit within token limit.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Override max total tokens (uses config default if None)
            preserve_system: Whether to always keep system messages
            
        Returns:
            Compressed messages list
        """
        if not messages:
            return []
        
        max_total = max_tokens or self.config.max_total_tokens
        
        # Calculate current token count
        current_tokens = sum(estimate_message_tokens(m) for m in messages)
        
        if current_tokens <= max_total:
            logger.debug(f"Context within limit: {current_tokens} <= {max_total}")
            return messages
        
        logger.info(f"Compressing context: {current_tokens} -> {max_total} tokens")
        
        # Categorize messages
        system_msgs = [m for m in messages if m.get("role") == "system"]
        user_msgs = [m for m in messages if m.get("role") == "user"]
        assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
        other_msgs = [m for m in messages if m.get("role") not in ("system", "user", "assistant")]
        
        # Calculate budgets
        system_budget = min(
            self.config.max_system_tokens,
            max_total // 3  # Max 1/3 for system
        )
        remaining_budget = max_total - estimate_tokens("".join(m["content"] for m in system_msgs[:1]))
        
        # Process system messages
        compressed = []
        for msg in system_msgs:
            content = msg.get("content", "")
            tokens = estimate_tokens(content)
            if preserve_system and tokens > system_budget:
                # Truncate system message
                content = self._truncate_text(content, system_budget)
                msg = msg.copy()
                msg["content"] = content
            compressed.append(msg)
        
        # Calculate remaining budget after system
        system_tokens = sum(estimate_message_tokens(m) for m in compressed)
        remaining_budget = max_total - system_tokens
        
        # Build compressed history
        result = compressed.copy()
        
        # Interleave user and assistant messages, keeping most recent
        all_convo = [m for m in messages if m.get("role") in ("user", "assistant")]
        
        # Calculate how many we can keep
        budget_per_pair = remaining_budget // max(1, len(all_convo) // 2)
        
        # Work backwards, keeping pairs
        kept_pairs = 0
        for i in range(len(all_convo) - 1, -1, -2):
            if i - 1 < 0:
                break
            
            user_msg = all_convo[i - 1]
            assistant_msg = all_convo[i]
            
            pair_tokens = estimate_message_tokens(user_msg) + estimate_message_tokens(assistant_msg)
            
            if pair_tokens <= budget_per_pair and kept_pairs < self.config.keep_recent_messages:
                # Keep this pair (insert at beginning to maintain order)
                result.insert(0, assistant_msg)
                result.insert(0, user_msg)
                kept_pairs += 1
            else:
                # Check if we should keep just the user message
                user_tokens = estimate_message_tokens(user_msg)
                if user_tokens <= budget_per_pair * 0.6:
                    result.insert(0, assistant_msg)
                    result.insert(0, user_msg)
        
        # If still over budget, apply final truncation
        final_tokens = sum(estimate_message_tokens(m) for m in result)
        if final_tokens > max_total:
            logger.warning(f"Final truncation needed: {final_tokens} -> {max_total}")
            result = self._emergency_truncate(result, max_total)
        
        logger.info(f"Compressed: {len(messages)} -> {len(result)} messages")
        return result
    
    def compress_for_node(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        node_context: str,
        max_context_tokens: int = 120000
    ) -> Tuple[List[Dict[str, str]], str]:
        """
        Compress messages specifically for a workflow node.
        
        Structure:
        - System prompt (full)
        - Node context (full)
        - Conversation history (compressed)
        """
        # Calculate budgets
        system_tokens = estimate_tokens(system_prompt)
        context_tokens = estimate_tokens(node_context)
        history_budget = max_context_tokens - system_tokens - context_tokens - 1000  # Buffer
        
        if history_budget < 5000:
            # Not enough budget for history
            logger.warning(f"Insufficient budget for history: {history_budget}")
            return [], node_context
        
        # Compress history
        history_msgs = [m for m in messages if m.get("role") != "system"]
        compressed_history = self.compress(history_msgs, max_tokens=history_budget)
        
        return compressed_history, node_context
    
    def _truncate_text(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token budget."""
        if not text:
            return ""
        
        current_tokens = estimate_tokens(text)
        if current_tokens <= max_tokens:
            return text
        
        # Binary search for truncation point
        left, right = 0, len(text)
        while left < right:
            mid = (left + right) // 2
            if estimate_tokens(text[:mid]) <= max_tokens:
                left = mid + 1
            else:
                right = mid
        
        # Find a good break point (end of sentence or paragraph)
        trunc_idx = text[:left].rfind("\n\n")
        if trunc_idx == -1:
            trunc_idx = text[:left].rfind(".\n")
        if trunc_idx == -1:
            trunc_idx = text[:left].rfind(". ")
        
        if trunc_idx > len(text) * 0.5:
            text = text[:trunc_idx + 2]
        
        # Add ellipsis if truncated
        if len(text) < len(original_text := text):
            text = text.rstrip() + "\n\n... [truncated for length]"
        
        return text
    
    def _emergency_truncate(
        self, 
        messages: List[Dict[str, str]], 
        max_tokens: int
    ) -> List[Dict[str, str]]:
        """Emergency truncation when all else fails."""
        result = []
        remaining = max_tokens
        
        for msg in reversed(messages):
            msg_tokens = estimate_message_tokens(msg)
            if msg_tokens <= remaining:
                result.insert(0, msg)
                remaining -= msg_tokens
            else:
                # Truncate this message
                truncated_content = self._truncate_text(msg.get("content", ""), remaining)
                if truncated_content:
                    result.insert(0, {
                        "role": msg.get("role", "user"),
                        "content": truncated_content
                    })
                break
        
        return result
    
    def count_tokens(self, messages: List[Dict[str, str]]) -> Dict[str, int]:
        """Get detailed token counts."""
        total = 0
        by_role = {}
        
        for msg in messages:
            role = msg.get("role", "unknown")
            tokens = estimate_message_tokens(msg)
            total += tokens
            by_role[role] = by_role.get(role, 0) + tokens
        
        return {
            "total": total,
            "by_role": by_role,
            "message_count": len(messages)
        }


# Global compressor instance
_context_compressor: Optional[ContextCompressor] = None


def get_compressor() -> ContextCompressor:
    """Get the global context compressor instance."""
    global _context_compressor
    if _context_compressor is None:
        _context_compressor = ContextCompressor()
    return _context_compressor


# Convenience function for LLM Gateway
def compress_llm_context(
    messages: List[Dict[str, str]],
    max_tokens: int = 120000
) -> List[Dict[str, str]]:
    """Quick compression for LLM calls."""
    return get_compressor().compress(messages, max_tokens=max_tokens)
