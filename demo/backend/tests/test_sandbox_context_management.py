import unittest
import json

from app.api.schemas import RuntimeConfig
from app.infra.gateways.sandbox import SandboxGateway


class SandboxContextManagementTests(unittest.TestCase):
    def test_agent_cli_uses_routed_model_window_for_early_compaction(self):
        runtime = RuntimeConfig(llm_context_window_tokens=1_048_576)

        env = SandboxGateway._agent_context_management_env(runtime)

        self.assertEqual(env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"], "1048576")
        self.assertEqual(env["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"], "70")
        self.assertEqual(env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"], "4096")

    def test_output_reserve_is_safe_for_small_windows(self):
        runtime = RuntimeConfig(llm_context_window_tokens=1_024)

        env = SandboxGateway._agent_context_management_env(runtime)

        self.assertEqual(env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"], "1024")
        self.assertEqual(env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"], "512")


class _CommandResult:
    exit_code = 0
    stdout = '{"result.txt": "known-result-hash"}'


class _FakeCommands:
    async def run(self, *args, **kwargs):
        return _CommandResult()


class _FakeFiles:
    def __init__(self):
        self.writes = {}

    async def read(self, *args, **kwargs):
        raise AssertionError("unchanged files should not be downloaded")

    async def write(self, path, content, **kwargs):
        self.writes[path] = content


class _FakeSandbox:
    def __init__(self):
        self.commands = _FakeCommands()
        self.files = _FakeFiles()


class SandboxHarvestMemoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_internal_memory_stays_in_sidecar_but_not_user_artifacts(self):
        sandbox = _FakeSandbox()
        gateway = SandboxGateway(asset_manager=object())
        known = {
            ".mm_agent/memory/project_history.md": "memory-hash",
            ".claude/rules/mm_agent_memory.md": "rule-hash",
            "result.txt": "known-result-hash",
        }

        new_files, returned_manifest = await gateway.harvest_artifacts_diff(
            sandbox, known
        )

        self.assertEqual(new_files, {})
        self.assertEqual(returned_manifest, {"result.txt": "known-result-hash"})
        sidecar = next(iter(sandbox.files.writes.values()))
        sidecar_manifest = json.loads(sidecar)
        self.assertEqual(sidecar_manifest, known)


if __name__ == "__main__":
    unittest.main()
