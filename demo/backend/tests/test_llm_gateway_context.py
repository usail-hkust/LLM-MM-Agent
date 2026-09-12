import unittest
from unittest.mock import AsyncMock

from app.infra.gateways.llm import LLMGateway
from app.api.schemas import ModelConfig, RuntimeConfig
from app.domain.unified_io import CopilotStreamChunk
from app.utils.context_compressor import calculate_input_budget, get_compressor


class LLMGatewayContextTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.messages = [
            {
                "role": "system",
                "content": "SYSTEM-BEGIN\n" + ("workflow history\n" * 20_000) + "SYSTEM-END",
            },
            {"role": "user", "content": "run the current result node"},
        ]

    async def test_anthropic_generation_is_compacted_before_provider_dispatch(self):
        gateway = LLMGateway()
        gateway._generate_anthropic_raw = AsyncMock(return_value="ok")
        runtime = RuntimeConfig(
            llm_api_key="test-key",
            llm_base_url="https://api.deepseek.com/anthropic",
            llm_model_name="deepseek-test",
            llm_context_window_tokens=8_192,
        )

        result = await gateway.generate_raw(self.messages, runtime=runtime)

        self.assertEqual(result, "ok")
        dispatched = gateway._generate_anthropic_raw.await_args.args[0]
        budget, _, _ = calculate_input_budget(8_192, 4_096, 8_192)
        self.assertLessEqual(get_compressor().count_tokens(dispatched)["total"], budget)
        self.assertEqual(dispatched[-1]["content"], "run the current result node")

    async def test_anthropic_stream_is_compacted_before_provider_dispatch(self):
        gateway = LLMGateway()
        captured = {}

        async def fake_stream(messages, *args, **kwargs):
            captured["messages"] = messages
            yield CopilotStreamChunk(content="ok")

        gateway._stream_anthropic_chat = fake_stream
        model_config = ModelConfig(
            apiKey="test-key",
            baseUrl="https://api.deepseek.com/anthropic",
            modelName="deepseek-test",
            contextWindowTokens=8_192,
        )

        chunks = [
            chunk
            async for chunk in gateway.stream_chat(
                self.messages,
                model_config=model_config,
            )
        ]

        self.assertEqual(chunks[0].content, "ok")
        budget, _, _ = calculate_input_budget(8_192, 4_096, 8_192)
        self.assertLessEqual(
            get_compressor().count_tokens(captured["messages"])["total"], budget
        )
        self.assertEqual(
            captured["messages"][-1]["content"], "run the current result node"
        )


if __name__ == "__main__":
    unittest.main()
