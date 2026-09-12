import unittest

from app.utils.context_compressor import (
    ContextCompressor,
    TRUNCATION_MARKER,
    calculate_input_budget,
    estimate_tokens,
)


class ContextCompressorTests(unittest.TestCase):
    def setUp(self):
        self.compressor = ContextCompressor()

    def test_large_single_system_message_is_actually_bounded(self):
        original = "SYSTEM-BEGIN\n" + ("large project history\n" * 20_000) + "FINAL-INSTRUCTIONS"
        messages = [{"role": "system", "content": original}]

        result = self.compressor.compress(messages, max_tokens=2_000)

        self.assertEqual(len(result), 1)
        self.assertLessEqual(self.compressor.count_tokens(result)["total"], 2_000)
        self.assertTrue(result[0]["content"].startswith("SYSTEM-BEGIN"))
        self.assertTrue(result[0]["content"].endswith("FINAL-INSTRUCTIONS"))
        self.assertIn(TRUNCATION_MARKER.strip(), result[0]["content"])
        self.assertEqual(messages[0]["content"], original)

    def test_recent_user_message_and_system_anchors_survive(self):
        messages = [
            {
                "role": "system",
                "content": "SYSTEM-BEGIN\n" + ("history\n" * 10_000) + "SYSTEM-END",
            },
            {"role": "user", "content": "CURRENT USER REQUEST"},
        ]

        result = self.compressor.compress(messages, max_tokens=1_000)

        self.assertLessEqual(self.compressor.count_tokens(result)["total"], 1_000)
        self.assertEqual([message["role"] for message in result], ["system", "user"])
        self.assertIn("SYSTEM-BEGIN", result[0]["content"])
        self.assertIn("SYSTEM-END", result[0]["content"])
        self.assertEqual(result[-1]["content"], "CURRENT USER REQUEST")

    def test_recent_conversation_is_preferred_to_old_turns(self):
        messages = [{"role": "system", "content": "short system prompt"}]
        for index in range(20):
            messages.append(
                {"role": "user", "content": f"user-{index} " + ("x" * 300)}
            )
            messages.append(
                {"role": "assistant", "content": f"assistant-{index} " + ("y" * 300)}
            )

        result = self.compressor.compress(messages, max_tokens=600)
        joined = "\n".join(message["content"] for message in result)

        self.assertLessEqual(self.compressor.count_tokens(result)["total"], 600)
        self.assertIn("assistant-19", joined)
        self.assertNotIn("user-0 ", joined)
        self.assertEqual(result[0]["role"], "system")

    def test_zero_budget_returns_no_messages(self):
        self.assertEqual(
            self.compressor.compress([{"role": "user", "content": "hello"}], 0),
            [],
        )

    def test_cjk_estimate_is_conservative(self):
        text = "上下文管理" * 100
        self.assertGreaterEqual(estimate_tokens(text), len(text))

    def test_input_budget_reserves_output_and_safety_tokens(self):
        budget, output_reserve, safety_reserve = calculate_input_budget(
            1_048_576, 4_096, 8_192
        )
        self.assertEqual(budget, 1_036_288)
        self.assertEqual(output_reserve, 4_096)
        self.assertEqual(safety_reserve, 8_192)

    def test_compact_text_keeps_head_and_recent_tail(self):
        original = "FIRST-DECISION\n" + ("middle\n" * 5_000) + "LATEST-STATE"
        result = self.compressor.compact_text(original, 500)

        self.assertLessEqual(estimate_tokens(result), 500)
        self.assertTrue(result.startswith("FIRST-DECISION"))
        self.assertTrue(result.endswith("LATEST-STATE"))
        self.assertIn(TRUNCATION_MARKER.strip(), result)


if __name__ == "__main__":
    unittest.main()
