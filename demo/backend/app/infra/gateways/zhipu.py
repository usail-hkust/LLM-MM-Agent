"""
智谱 (Zhipu) API 适配器
直接调用智谱 API，绕过 LiteLLM
"""
import os
import json
import logging
import httpx
from typing import List, Dict, AsyncGenerator, Optional

from app.core.config import settings
from app.core.exceptions import ExecutionError
from app.domain.unified_io import NodeOutput, CopilotStreamChunk
from app.api.schemas import ModelConfig, RuntimeConfig
from app.infra.output_parsers import StandardOutputParser
from app.utils.context_compressor import get_compressor

logger = logging.getLogger(__name__)

class ZhipuGateway:
    """
    智谱 API 专用适配器
    """
    
    def __init__(self):
        self.parser = StandardOutputParser()
    
    def _is_zhipu(self, base_url: str) -> bool:
        """检查是否是智谱 API"""
        if not base_url:
            return False
        return "bigmodel" in base_url.lower() or "zhipu" in base_url.lower()
    
    async def generate(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None, 
        runtime: Optional[RuntimeConfig] = None,
        **kwargs
    ) -> NodeOutput:
        """
        生成回复（非流式）
        """
        raw_content = await self.generate_raw(messages, model, runtime, **kwargs)
        return self.parser.parse(raw_content)
    
    async def generate_raw(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None, 
        runtime: Optional[RuntimeConfig] = None,
        **kwargs
    ) -> str:
        """
        生成原始文本（智谱专用）
        """
        # 1. 解析配置
        api_key = None
        base_url = None
        model_name = model or settings.MODEL_NAME
        
        if runtime:
            if runtime.llm_api_key:
                api_key = runtime.llm_api_key
            if runtime.llm_base_url:
                base_url = runtime.llm_base_url
            if runtime.llm_model_name:
                model_name = runtime.llm_model_name
        
        # 2. 检查是否是智谱
        if not self._is_zhipu(base_url):
            # 不是智谱，使用 LiteLLM
            from app.infra.gateways.llm import LLMGateway
            llm = LLMGateway()
            return await llm.generate_raw(messages, model, runtime, **kwargs)
        
        # 3. 智谱 API 调用
        if not api_key:
            raise ExecutionError("LLM", "智谱 API 需要 API Key，请在 Settings 中配置")
        
        # 4. 构建请求
        temperature = kwargs.get("temperature", 1.0)
        node_id = kwargs.get("node_id", "Unknown")
        
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature
        }
        
        logger.info(f"[Zhipu] 调用 API: {url}, model={model_name}")
        
        # 5. 发送请求
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                response = await client.post(url, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()

                content = result["choices"][0]["message"]["content"]
                logger.info(f"[Zhipu] 成功获取响应 ({len(content)} chars)")

                return content

        except httpx.HTTPStatusError as e:
            error_msg = f"智谱 API 错误 ({e.response.status_code}): {e.response.text[:300]}"
            logger.error(f"[Zhipu] {error_msg}")
            # [FIX] 不包装 ExecutionError，直接抛出原始异常让 tenacity 处理
            raise

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[Zhipu] 请求失败: {error_msg}")
            # [FIX] 不包装 ExecutionError，直接抛出原始异常让 tenacity 处理
            raise
    
    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model_config: Optional[ModelConfig] = None,
        runtime: Optional[RuntimeConfig] = None,
        **kwargs
    ) -> AsyncGenerator[CopilotStreamChunk, None]:
        """
        流式生成（智谱专用）
        """
        # 解析配置
        api_key = None
        base_url = None
        model_name = model_config.modelName if model_config else None
        
        if runtime:
            if runtime.llm_api_key:
                api_key = runtime.llm_api_key
            if runtime.llm_base_url:
                base_url = runtime.llm_base_url
            if runtime.llm_model_name:
                model_name = runtime.llm_model_name
        
        if model_config:
            if model_config.apiKey:
                api_key = model_config.apiKey
            if model_config.baseUrl:
                base_url = model_config.baseUrl
            if model_config.temperature is not None:
                temperature = model_config.temperature
        
        # 检查是否是智谱
        if not self._is_zhipu(base_url):
            # 不是智谱，使用 LiteLLM
            from app.infra.gateways.llm import LLMGateway
            llm = LLMGateway()
            async for chunk in llm.stream_chat(messages, model_config, runtime, **kwargs):
                yield chunk
            return
        
        # 智谱流式调用
        if not api_key:
            yield CopilotStreamChunk(content="\n\n**[智谱 API 错误]**\n\n请在 Settings 中配置 API Key")
            return
        
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": model_name or "glm-4",
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "stream": True
        }
        
        logger.debug(f"[Zhipu] 流式调用: {url}")
        
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                async with client.stream("POST", url, headers=headers, json=data) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                content = chunk["choices"][0]["delta"].get("content", "")
                                if content:
                                    yield CopilotStreamChunk(content=content)
                            except json.JSONDecodeError:
                                pass
                            
        except Exception as e:
            logger.error(f"[Zhipu] 流式调用失败: {e}")
            yield CopilotStreamChunk(content=f"\n\n**[智谱 API 错误]**\n\n{str(e)}")
