"""
LLM Gateway - LiteLLM Adapter.

Provides access to LiteLLM for generation and streaming.
Uses the output parser to structure results.
[OPTIMIZED v1.1] Added automatic context compression.
[OPTIMIZED v1.2] Integrated global ContextCompressor for all LLM calls.
[OPTIMIZED v1.3] Added Zhipu/ChatGLM support via direct API calls.
[OPTIMIZED v1.4] Removed tenacity retry to avoid conflicts with LiteLLM built-in retry.
"""
import logging
import json
from typing import List, Dict, AsyncGenerator, Optional
import httpx
import litellm

from app.core.config import settings
from app.core.exceptions import ExecutionError
from app.domain.unified_io import NodeOutput, CopilotStreamChunk
from app.api.schemas import ModelConfig, RuntimeConfig
from app.infra.output_parsers import StandardOutputParser
from app.infra.gateways.anthropic_compat import (
    anthropic_headers,
    anthropic_messages_url,
    anthropic_payload,
    extract_anthropic_text,
    is_anthropic_compatible_base,
    normalize_anthropic_model,
)
from app.utils.context_compressor import get_compressor, compress_llm_context

logger = logging.getLogger(__name__)

# [REFACTOR] Removed global litellm.api_key and litellm.api_base assignments.
# Configuration is now resolved per-request via RuntimeConfig.

class LLMGateway:
    """
    Adapter for Large Language Model interactions.
    """
    def __init__(self):
        self.parser = StandardOutputParser()
        self.default_model = settings.MODEL_NAME
        self._zhipu_gateway = None  # Lazy initialization
    
    def _get_zhipu_gateway(self):
        """获取智谱专用适配器（延迟初始化）"""
        if self._zhipu_gateway is None:
            from app.infra.gateways.zhipu import ZhipuGateway
            self._zhipu_gateway = ZhipuGateway()
        return self._zhipu_gateway
    
    def _is_zhipu(self, base_url: str) -> bool:
        """检查是否是智谱 API"""
        if not base_url:
            return False
        return "bigmodel" in base_url.lower() or "zhipu" in base_url.lower()

    def _is_anthropic_compatible(self, base_url: str) -> bool:
        return is_anthropic_compatible_base(base_url)

    def _resolve_config(self, runtime: Optional[RuntimeConfig], model_override: Optional[str] = None):
        """Helper: Resolve final config (Runtime > Settings)"""
        # 1. Base Defaults (Server Env)
        base_url = settings.BASE_URL
        model = model_override or self.default_model

        # 2. Runtime Overrides (Headers) with env fallback
        api_key = settings.API_KEY or settings.OPENAI_API_KEY or None
        if runtime and runtime.llm_api_key:
            api_key = runtime.llm_api_key
            if runtime.llm_base_url:
                base_url = runtime.llm_base_url
            if runtime.llm_model_name:
                model = runtime.llm_model_name
        elif runtime:
            if runtime.llm_base_url:
                base_url = runtime.llm_base_url
            if runtime.llm_model_name:
                model = runtime.llm_model_name
        else:
            base_url = base_url or "https://api.openai.com/v1"
        
        if not api_key:
            logger.warning(
                "No API Key provided - using placeholder. "
                "LLM calls will fail with a clear error message. "
                "Please configure your API key in Settings or in .env."
            )
            api_key = "placeholder_api_key_for_fallback"
            base_url = base_url or "https://api.openai.com/v1"
        
        # 3. Normalize URL/Model for LiteLLM
        # For Zhipu, we'll use custom_llm_provider instead of model prefix
        is_zhipu = base_url and ("bigmodel" in base_url.lower() or "zhipu" in base_url.lower())
        
        if is_zhipu:
            # 智谱/ChatGLM - 保持原始 model name，使用 custom_llm_provider
            logger.info(f"Using Zhipu API with model: {model}")
        elif self._is_anthropic_compatible(base_url):
            model = normalize_anthropic_model(model)
        elif base_url and not model.startswith(("openai/", "azure/", "anthropic/", "zhipu/")):
            # 其他兼容 OpenAI 的 API
            model = f"openai/{model}"
        
        # [BYOK] Log resolved config for debugging (mask key for security)
        key_prefix = api_key[:8] + "..." if api_key and len(api_key) > 8 else "N/A"
        logger.info(f"Using Model: {model} | Base URL: {base_url} | Key: {key_prefix}")
            
        return api_key, base_url, model

    async def generate(self, messages: List[Dict[str, str]], model: Optional[str] = None, runtime: Optional[RuntimeConfig] = None, **kwargs) -> NodeOutput:
        """
        Non-streaming generation with automatic parsing.

        Uses stream=True internally to avoid connection timeouts on long generations,
        but accumulates chunks and returns complete content to maintain non-streaming API.

        [FIX v1.4] 移除 tenacity 重试，统一使用 generate_raw
        """
        raw_content = await self.generate_raw(messages, model, runtime, **kwargs)
        return self.parser.parse(raw_content)

    async def generate_raw(self, messages: List[Dict[str, str]], model: Optional[str] = None, runtime: Optional[RuntimeConfig] = None, **kwargs) -> str:
        """
        [NEW] Generate raw text without parsing.
        Returns the raw LLM response text for batch parsing.
        [OPTIMIZED v1.1] Automatic context compression.

        [FIX v1.4] 移除 tenacity 重试，让各 LLM Gateway 自己处理重试：
        - LiteLLM 已有内置重试机制
        - ZhipuGateway 应该自己处理重试
        - 避免双重重试和异步返回值问题
        """
        base_url = runtime.llm_base_url if runtime else None

        # [FIX] 智谱检测 - 使用专用适配器
        if self._is_zhipu(base_url):
            zhipu = self._get_zhipu_gateway()
            return await zhipu.generate_raw(messages, model, runtime, **kwargs)

        # [优化] 其他 LLM 调用流程
        node_id = kwargs.pop("node_id", "Unknown")

        # [BYOK] Resolve Config
        api_key, base_url, active_model = self._resolve_config(runtime, model)

        if self._is_anthropic_compatible(base_url):
            return await self._generate_anthropic_raw(
                messages,
                active_model,
                api_key,
                base_url,
                node_id=node_id,
                **kwargs,
            )

        # [v1.3] 智谱检测 - 使用 OpenAI 兼容模式
        is_zhipu = self._is_zhipu(base_url)

        # [OPTIMIZED v1.1] Auto-compress context if too large
        compressor = get_compressor()
        token_info = compressor.count_tokens(messages)
        max_tokens = 120000  # Default max for most models

        if token_info["total"] > max_tokens * 0.8:  # Compress if at 80% capacity
            logger.info(f"Compressing context: {token_info['total']} tokens")
            messages = compressor.compress(messages, max_tokens=max_tokens)
            new_info = compressor.count_tokens(messages)
            logger.info(f"Compressed to: {new_info['total']} tokens ({len(messages)} messages)")

        try:
            # Use stream=True to avoid connection timeouts on long generations
            stream = await litellm.acompletion(
                model=active_model,
                messages=messages,
                temperature=kwargs.get("temperature", 1.0),
                stream=True,  # Stream internally to avoid idle timeout
                api_key=api_key,
                api_base=base_url if base_url else None,
                custom_llm_provider="openai" if is_zhipu else None,  # [v1.3] 智谱使用 OpenAI 兼容模式
                timeout=600,
                num_retries=2,  # [FIX] 配置 LiteLLM 重试次数，避免无限重试
                **{k: v for k, v in kwargs.items() if k not in ["temperature", "max_tokens", "api_key"]}
            )

            # Accumulate all chunks to reconstruct full content
            raw_content = ""
            async for chunk in stream:
                delta = chunk.choices[0].delta
                content_delta = delta.content or ""
                raw_content += content_delta

            # Extract content after <think> tag for workflow processing nodes
            # This handles LLM outputs that include thinking tags (e.g., Claude)
            if "<think>" in raw_content:
                think_end_index = raw_content.find("</think>")
                if think_end_index != -1:
                    # Extract content after </think> tag (including the tag itself)
                    raw_content = raw_content[think_end_index + len("</think>"):].strip()

            print(f"\n[DEBUG] LLM Output for Node: {node_id}\n{raw_content}\n{'-'*50}")

            return raw_content

        except Exception as e:
            error_msg = str(e)
            logger.error(f"LLM Generation Failed: {error_msg}")

            # [容错机制] 当 API Key 错误或缺失时，返回友好的错误信息而不是崩溃
            if "api_key" in error_msg.lower() or "authentication" in error_msg.lower() or "401" in error_msg:
                friendly_error = (
                    f"**[LLM Configuration Error]**\n\n"
                    f"The LLM API call failed. This is usually due to:\n"
                    f"1. Missing or invalid API key in Settings\n"
                    f"2. Incorrect model name\n"
                    f"3. API quota exhausted\n\n"
                    f"**Solution:** Click the gear icon (⚙️) in the top-right corner and configure your API key.\n\n"
                    f"Original error: {error_msg[:200]}"
                )
                raise ExecutionError("LLM", friendly_error)
            else:
                # 其他错误也返回友好消息
                friendly_error = f"**[LLM Error]**\n\nFailed to generate response.\n\nOriginal error: {error_msg[:300]}"
                raise ExecutionError("LLM", friendly_error)
        """
        [NEW] Generate raw text without parsing.
        Returns the raw LLM response text for batch parsing.
        [OPTIMIZED v1.1] Automatic context compression.
        """
        # [v1.3] 智谱检测 - 使用专用适配器
        base_url = runtime.llm_base_url if runtime else None
        if self._is_zhipu(base_url):
            zhipu = self._get_zhipu_gateway()
            return await zhipu.generate_raw(messages, model, runtime, **kwargs)
        
        node_id = kwargs.pop("node_id", "Unknown")
        
        # [BYOK] Resolve Config
        api_key, base_url, active_model = self._resolve_config(runtime, model)
        
        # [v1.3] 智谱检测 - 使用 OpenAI 兼容模式
        is_zhipu = self._is_zhipu(base_url)
        
        # [OPTIMIZED v1.1] Auto-compress context if too large
        compressor = get_compressor()
        token_info = compressor.count_tokens(messages)
        max_tokens = 120000  # Default max for most models
        
        if token_info["total"] > max_tokens * 0.8:  # Compress if at 80% capacity
            logger.info(f"Compressing context: {token_info['total']} tokens")
            messages = compressor.compress(messages, max_tokens=max_tokens)
            new_info = compressor.count_tokens(messages)
            logger.info(f"Compressed to: {new_info['total']} tokens ({len(messages)} messages)")
        
        try:
            # Use stream=True to avoid connection timeouts on long generations
            stream = await litellm.acompletion(
                model=active_model,
                messages=messages,
                temperature=kwargs.get("temperature", 1.0),
                stream=True,  # Stream internally to avoid idle timeout
                api_key=api_key,
                api_base=base_url if base_url else None,
                custom_llm_provider="openai" if is_zhipu else None,  # [v1.3] 智谱使用 OpenAI 兼容模式
                timeout=600,
                **{k: v for k, v in kwargs.items() if k not in ["temperature", "max_tokens", "api_key"]}
            )
            
            # Accumulate all chunks to reconstruct full content
            raw_content = ""
            async for chunk in stream:
                delta = chunk.choices[0].delta
                content_delta = delta.content or ""
                raw_content += content_delta
            
            # Extract content after </think> tag for workflow processing nodes
            # This handles LLM outputs that include thinking tags (e.g., Claude)
            if "</think>" in raw_content:
                think_end_index = raw_content.find("</think>")
                if think_end_index != -1:
                    # Extract content after </think> tag (including the tag itself)
                    raw_content = raw_content[think_end_index + len("</think>"):].strip()
            
            print(f"\n[DEBUG] LLM Output for Node: {node_id}\n{raw_content}\n{'-'*50}")
            
            return raw_content

        except Exception as e:
            error_msg = str(e)
            logger.error(f"LLM Generation Failed: {error_msg}")
            
            # [容错机制] 当 API Key 错误或缺失时，返回友好的错误信息而不是崩溃
            if "api_key" in error_msg.lower() or "authentication" in error_msg.lower() or "401" in error_msg:
                friendly_error = (
                    f"**[LLM Configuration Error]**\n\n"
                    f"The LLM API call failed. This is usually due to:\n"
                    f"1. Missing or invalid API key in Settings\n"
                    f"2. Incorrect model name\n"
                    f"3. API quota exhausted\n\n"
                    f"**Solution:** Click the gear icon (⚙️) in the top-right corner and configure your API key.\n\n"
                    f"Original error: {error_msg[:200]}"
                )
                raise ExecutionError("LLM", friendly_error)
            else:
                # 其他错误也返回友好消息
                friendly_error = f"**[LLM Error]**\n\nFailed to generate response.\n\nOriginal error: {error_msg[:300]}"
                raise ExecutionError("LLM", friendly_error)

    async def _generate_anthropic_raw(
        self,
        messages: List[Dict[str, str]],
        model: str,
        api_key: str,
        base_url: str,
        *,
        node_id: str = "Unknown",
        **kwargs
    ) -> str:
        max_tokens = int(kwargs.get("max_tokens") or 4096)
        temperature = kwargs.get("temperature", 1.0)
        payload = anthropic_payload(
            messages,
            model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                response = await client.post(
                    anthropic_messages_url(base_url),
                    headers=anthropic_headers(api_key, base_url),
                    json=payload,
                )

            if response.status_code != 200:
                raise ExecutionError(
                    "LLM",
                    f"Anthropic-compatible API error ({response.status_code}): {response.text[:300]}",
                )

            raw_content = extract_anthropic_text(response.json())
            print(f"\n[DEBUG] LLM Output for Node: {node_id}\n{raw_content}\n{'-'*50}")
            return raw_content
        except ExecutionError:
            raise
        except Exception as e:
            raise ExecutionError(
                "LLM",
                f"Anthropic-compatible generation failed: {str(e)[:300]}",
            )

    async def _stream_anthropic_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        api_key: str,
        base_url: str,
        temperature: float,
        **kwargs
    ) -> AsyncGenerator[CopilotStreamChunk, None]:
        max_tokens = int(kwargs.get("max_tokens") or 4096)
        payload = anthropic_payload(
            messages,
            model,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )

        async with httpx.AsyncClient(timeout=600.0) as client:
            async with client.stream(
                "POST",
                anthropic_messages_url(base_url),
                headers=anthropic_headers(api_key, base_url),
                json=payload,
            ) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    raise ExecutionError(
                        "LLM",
                        f"Anthropic-compatible API error ({response.status_code}): {body[:300].decode('utf-8', errors='replace')}",
                    )

                finish_reason = None
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data_text = line.removeprefix("data:").strip()
                    if not data_text or data_text == "[DONE]":
                        continue

                    try:
                        data = json.loads(data_text)
                    except json.JSONDecodeError:
                        continue

                    event_type = data.get("type")
                    if event_type == "error":
                        error = data.get("error", {})
                        raise ExecutionError("LLM", error.get("message", str(error)))

                    if event_type == "message_delta":
                        delta = data.get("delta", {})
                        finish_reason = delta.get("stop_reason") or finish_reason
                        continue

                    if event_type != "content_block_delta":
                        continue

                    delta = data.get("delta", {})
                    delta_type = delta.get("type")
                    content_delta = ""
                    thought_delta = ""

                    if delta_type == "text_delta":
                        content_delta = delta.get("text", "")
                    elif delta_type == "thinking_delta":
                        thought_delta = delta.get("thinking", "")

                    if content_delta or thought_delta:
                        yield CopilotStreamChunk(
                            content=content_delta,
                            thought=thought_delta,
                            finish_reason=finish_reason,
                        )

    async def stream_chat(
        self, 
        messages: List[Dict[str, str]], 
        model_config: Optional[ModelConfig] = None,
        runtime: Optional[RuntimeConfig] = None,
        **kwargs
    ) -> AsyncGenerator[CopilotStreamChunk, None]:
        """
        Yields structured chunks (Content + Thought) for Copilot streaming.
        Compatible with OpenAI standard and DeepSeek reasoning extensions.
        """
        # [v1.3] 智谱检测 - 使用专用适配器
        base_url = model_config.baseUrl if model_config else (runtime.llm_base_url if runtime else None)
        if self._is_zhipu(base_url):
            zhipu = self._get_zhipu_gateway()
            async for chunk in zhipu.stream_chat(messages, model_config, runtime, **kwargs):
                yield chunk
            return
        
        # Priority: Frontend Chat Settings > Global Runtime Header > Server Env
        req_model = model_config.modelName if model_config else None
        api_key, base_url, active_model = self._resolve_config(runtime, req_model)
        temperature = kwargs.get("temperature", 0.7)

        # Override if specific model config provided in body (e.g. legacy copilot request)
        if model_config:
            if model_config.apiKey: api_key = model_config.apiKey
            if model_config.baseUrl: base_url = model_config.baseUrl
            if model_config.modelName: active_model = model_config.modelName
            if model_config.temperature is not None:
                temperature = model_config.temperature

        if self._is_anthropic_compatible(base_url):
            try:
                stream_kwargs = {k: v for k, v in kwargs.items() if k != "temperature"}
                async for chunk in self._stream_anthropic_chat(
                    messages,
                    normalize_anthropic_model(active_model),
                    api_key,
                    base_url,
                    temperature,
                    **stream_kwargs,
                ):
                    yield chunk
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Anthropic-compatible stream failed: {error_msg}")
                yield CopilotStreamChunk(content=f"\n\n**[LLM Error]**\n\nOriginal error: {error_msg[:200]}")
            return

        # [v1.3] 智谱检测 - 使用 OpenAI 兼容模式
        is_zhipu = self._is_zhipu(base_url)
        
        # Force "openai/" prefix for custom providers unless explicitly set.
        if base_url and not is_zhipu:
            if not active_model.startswith(("openai/", "azure/", "anthropic/")):
                active_model = f"openai/{active_model}"
        elif is_zhipu:
            # 智谱: 不加 openai/ 前缀，直接使用 model 名称
            logger.info(f"[Zhipu] 使用模型: {active_model}")

        # Stream-time <think> tag splitter for models that embed reasoning in content.
        think_open = "<think>"
        think_close = "</think>"
        in_think = False
        pending = ""

        def _suffix_partial_tag(text: str) -> int:
            max_keep = 0
            for tag in (think_open, think_close):
                max_len = min(len(tag) - 1, len(text))
                for k in range(1, max_len + 1):
                    if text.endswith(tag[:k]) and k > max_keep:
                        max_keep = k
            return max_keep

        def _split_think(text: str) -> tuple[str, str]:
            nonlocal in_think, pending
            if not text and not pending:
                return "", ""

            text = pending + text
            pending = ""
            out_content: List[str] = []
            out_thought: List[str] = []
            i = 0

            while i < len(text):
                if in_think:
                    close_idx = text.find(think_close, i)
                    if close_idx == -1:
                        remainder = text[i:]
                        keep = _suffix_partial_tag(remainder)
                        if keep:
                            out_thought.append(remainder[:-keep])
                            pending = remainder[-keep:]
                        else:
                            out_thought.append(remainder)
                        i = len(text)
                    else:
                        out_thought.append(text[i:close_idx])
                        i = close_idx + len(think_close)
                        in_think = False
                else:
                    open_idx = text.find(think_open, i)
                    if open_idx == -1:
                        remainder = text[i:]
                        keep = _suffix_partial_tag(remainder)
                        if keep:
                            out_content.append(remainder[:-keep])
                            pending = remainder[-keep:]
                        else:
                            out_content.append(remainder)
                        i = len(text)
                    else:
                        out_content.append(text[i:open_idx])
                        i = open_idx + len(think_open)
                        in_think = True

            return "".join(out_content), "".join(out_thought)

        try:
            logger.debug(f"Streaming chat with model: {active_model} (Base: {base_url})")
            
            # [v1.3] 智谱使用 OpenAI 兼容模式
            is_zhipu = self._is_zhipu(base_url)
            
            stream = await litellm.acompletion(
                model=active_model,
                messages=messages,
                temperature=temperature,
                stream=True,
                api_key=api_key,
                api_base=base_url if base_url else None,
                custom_llm_provider="openai" if is_zhipu else None,  # [v1.3] 智谱使用 OpenAI 兼容模式
                **{k: v for k, v in kwargs.items() if k not in ["temperature", "api_key"]}
            )

            async for chunk in stream:
                delta = chunk.choices[0].delta
                
                # [FIX] Structure Extraction
                # 1. Standard Content
                content_delta = delta.content or ""
                
                # 2. Reasoning Content (DeepSeek / CoT models)
                # LiteLLM/OpenAI standardizes reasoning in 'reasoning_content' or sometimes 'reasoning'
                thought_delta = getattr(delta, "reasoning_content", "") or \
                                getattr(delta, "reasoning", "") or ""

                if content_delta:
                    parsed_content, parsed_thought = _split_think(content_delta)
                    content_delta = parsed_content
                    if parsed_thought:
                        thought_delta = f"{thought_delta}{parsed_thought}"

                if content_delta or thought_delta:
                    yield CopilotStreamChunk(
                        content=content_delta,
                        thought=thought_delta,
                        finish_reason=chunk.choices[0].finish_reason
                    )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"LLM Stream Failed: {error_msg}")
            
            # [容错机制] 返回友好的错误消息
            if "api_key" in error_msg.lower() or "authentication" in error_msg.lower() or "401" in error_msg:
                friendly_error = (
                    f"**[LLM Configuration Error]**\n\n"
                    f"Please configure your API key in Settings (click the gear icon ⚙️).\n\n"
                    f"Original error: {error_msg[:150]}"
                )
            else:
                friendly_error = f"**[LLM Error]**\n\nOriginal error: {error_msg[:200]}"
            
            # Yield error as a special chunk so frontend handles it gracefully
            yield CopilotStreamChunk(content=f"\n\n{friendly_error}")
