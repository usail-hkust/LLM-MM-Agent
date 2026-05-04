"""
Sandbox Gateway (v3.0) - E2B Code Interpreter Adapter.
Supports both Agentic (Claude Code) and Direct execution modes.
[OPTIMIZED] Implemented Differential Context Sync & Extended Timeouts.
[OPTIMIZED v3.1] Session Pooling, Parallel Upload, Connection Caching.
"""
import logging
import asyncio
import json
import re
import os
import tempfile
from typing import Dict, Optional, AsyncIterator, Any, Tuple
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import threading

from app.core.config import settings
from app.core.exceptions import ExecutionError
from app.core.templates import jinja_env
from app.domain.unified_io import NodeOutput, ContentBlock, BlockType
from app.infra.asset_manager import AssetManager
from app.infra.gateways.anthropic_compat import (
    anthropic_base_url,
    is_anthropic_compatible_base,
    normalize_anthropic_model,
)
from app.utils.io_tarball import StreamingTarball
from app.api.schemas import RuntimeConfig

logger = logging.getLogger(__name__)

from e2b_code_interpreter import AsyncSandbox
from e2b import SandboxQuery, TimeoutException, SandboxException, Template


# --- Session Pool (v3.1 Optimization) ---
class SandboxPool:
    """
    L1 Lifecycle Pool: Manages active E2B sandbox connections.
    Reduces cold starts by reusing sessions.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._pool: Dict[str, Tuple[AsyncSandbox, datetime]] = {}
        self._pool_lock = asyncio.Lock()
        self._max_pool_size = 10  # Max concurrent sessions
        self._session_ttl = timedelta(minutes=30)  # Auto-cleanup after 30min
    
    async def get(self, project_id: str, api_key: str) -> Tuple[AsyncSandbox, bool]:
        """Get or create a session for the project."""
        async with self._pool_lock:
            # Check if we have a valid cached session
            now = datetime.now()
            if project_id in self._pool:
                sb, last_used = self._pool[project_id]
                if now - last_used < self._session_ttl:
                    # Update last used time
                    self._pool[project_id] = (sb, now)
                    return sb, False  # Reused existing session
            
            # Create new session
            try:
                sb = await self._create_session(project_id, api_key)
                self._cleanup_if_needed()
                self._pool[project_id] = (sb, now)
                return sb, True  # New session
            except Exception as e:
                logger.error(f"Failed to create session for {project_id}: {e}")
                raise
    
    async def _create_session(self, project_id: str, api_key: str) -> AsyncSandbox:
        """Create a new E2B sandbox session."""
        label_key = settings.E2B_PROJECT_LABEL_KEY
        meta_filter = {label_key: str(project_id)}
        
        # Try to find existing running sandbox
        try:
            paginator = AsyncSandbox.list(
                api_key=api_key,
                query=SandboxQuery(metadata=meta_filter)
            )
            found = []
            if hasattr(paginator, 'next_items'):
                while True:
                    batch = await paginator.next_items()
                    if not batch: break
                    found.extend(batch)
                    if not paginator.has_next: break
            else:
                found = paginator
            
            target = next((s for s in found if s.state == "running"), None)
            if target:
                logger.info(f"Resuming Sandbox {target.sandbox_id} for {project_id}")
                return await AsyncSandbox.connect(target.sandbox_id, api_key=api_key)
        except Exception as e:
            logger.warning(f"Sandbox discovery failed: {e}")
        
        # Create new sandbox
        logger.info(f"Creating NEW Sandbox for {project_id}")
        try:
            sb = await AsyncSandbox.create(
                template=settings.E2B_TEMPLATE_ALIAS,
                api_key=api_key,
                metadata=meta_filter,
                timeout=settings.SANDBOX_TIMEOUT
            )
        except SandboxException as e:
            if "template" in str(e).lower() and "not found" in str(e).lower():
                new_template_id = await SandboxTemplateManager.ensure_template_ready()
                sb = await AsyncSandbox.create(
                    template=new_template_id,
                    api_key=api_key,
                    metadata=meta_filter,
                    timeout=settings.SANDBOX_TIMEOUT
                )
            else:
                raise
        
        await sb.commands.run(f"mkdir -p {settings.SANDBOX_DATA_DIR}")
        return sb
    
    def _cleanup_if_needed(self):
        """Remove oldest sessions if pool is full."""
        if len(self._pool) > self._max_pool_size:
            # Remove oldest entries
            sorted_items = sorted(
                self._pool.items(), 
                key=lambda x: x[1][1]  # Sort by last_used
            )
            for remove_id, _ in sorted_items[:len(self._pool) - self._max_pool_size]:
                del self._pool[remove_id]
    
    async def close(self, project_id: str):
        """Close and remove a session from the pool."""
        async with self._pool_lock:
            if project_id in self._pool:
                sb, _ = self._pool[project_id]
                try:
                    await sb.kill()
                except Exception:
                    pass
                del self._pool[project_id]
    
    async def cleanup_all(self):
        """Close all pooled sessions."""
        async with self._pool_lock:
            for sb, _ in self._pool.values():
                try:
                    await sb.kill()
                except Exception:
                    pass
            self._pool.clear()


# Global pool instance
_sandbox_pool: Optional[SandboxPool] = None


def get_sandbox_pool() -> SandboxPool:
    global _sandbox_pool
    if _sandbox_pool is None:
        _sandbox_pool = SandboxPool()
    return _sandbox_pool


class SandboxTemplateManager:
    """
    Build System 2.0: Manages E2B Custom Template Lifecycle.
    """
    @staticmethod
    async def ensure_template_ready() -> str:
        target_alias = settings.E2B_TEMPLATE_ALIAS
        if not settings.E2B_API_KEY:
            return target_alias

        needs_build = settings.E2B_FORCE_REBUILD

        if not needs_build:
            try:
                # Lazy Check: Create a short lived sandbox to verify template exists
                sb = await AsyncSandbox.create(
                    template=target_alias,
                    api_key=settings.E2B_API_KEY,
                    timeout=300
                )
                await sb.kill()
                logger.info(f"✅ E2B Template '{target_alias}' is ready.")
                return target_alias  # [FIX] Return alias if ready
            except Exception as e:
                if "not found" in str(e).lower() or "template" in str(e).lower():
                    logger.info(f"Template '{target_alias}' not found. Building...")
                    needs_build = True
                else:
                    logger.warning(f"Template check warning ({e}). Assuming build needed.")
                    needs_build = True

        if needs_build:
            # [FIX] Return the specific NEW ID
            return await SandboxTemplateManager._build_template(target_alias)
        
        return target_alias

    @staticmethod
    async def _build_template(alias: str) -> str:
        logger.info(f"🔨 Building E2B Template: {alias}")
        loop = asyncio.get_running_loop()
        try:
            # [FIX] Return the result from executor
            new_id = await loop.run_in_executor(None, SandboxTemplateManager._run_build_sync, alias)
            logger.info(f"✅ Template Built: {alias} (ID: {new_id})")
            return new_id
        except Exception as e:
            logger.error(f"❌ Build Failed: {e}")
            raise e  # [FIX] Re-raise exception so the caller knows build failed

    @staticmethod
    def _run_build_sync(alias: str) -> str:
        t = Template().from_template(settings.E2B_BASE_TEMPLATE)

        def _run_cmd(command: str) -> None:
            if hasattr(t, "run_cmd"):
                t.run_cmd(command)
            elif hasattr(t, "run"):
                t.run(command)
            else:
                logger.warning("Template.run_cmd not available; skipping command.")

        if hasattr(settings, "E2B_APT_PACKAGES") and settings.E2B_APT_PACKAGES:
            if hasattr(t, "apt_install"):
                try:
                    t.apt_install(settings.E2B_APT_PACKAGES, no_install_recommends=True)
                except TypeError:
                    t.apt_install(settings.E2B_APT_PACKAGES)
            else:
                apt_install_cmd = (
                    "apt-get update && "
                    f"apt-get install -y --no-install-recommends {' '.join(settings.E2B_APT_PACKAGES)} && "
                    "rm -rf /var/lib/apt/lists/*"
                )
                _run_cmd(apt_install_cmd)
        if settings.E2B_PIP_PACKAGES:
            t.pip_install(settings.E2B_PIP_PACKAGES)
        if settings.E2B_NPM_PACKAGES:
            if hasattr(t, "npm_install"):
                _run_cmd(
                    "which npm || (apt-get update && apt-get install -y nodejs npm && rm -rf /var/lib/apt/lists/*)"
                )
                t.npm_install(settings.E2B_NPM_PACKAGES, g=True)
            else:
                _run_cmd(
                    "which npm || (apt-get update && apt-get install -y nodejs npm && rm -rf /var/lib/apt/lists/*)"
                )
                for pkg in settings.E2B_NPM_PACKAGES:
                    _run_cmd(f"npm install -g {pkg}")
        # [FIX] Capture the built template object and return its ID
        built_template = Template.build(t, alias=alias, api_key=settings.E2B_API_KEY, memory_mb=8192, cpu_count=8)
        # E2B SDK 通常返回 template 对象，包含 template_id 属性
        return built_template.template_id


class SandboxGateway:
    """
    Adapter for E2B Code Interpreter.
    Manages the Infrastructure (L1 Lifecycle) and I/O.
    """
    def __init__(self, asset_manager: AssetManager):
        self.assets = asset_manager
        self.manifest_file = ".lcp_manifest.json"

    # --- Agentic Mode Methods (Direct Connection) ---

    async def start_agentic_session(
        self,
        project_id: str,
        node_id: str,
        runtime: Optional[RuntimeConfig] = None,  # [BYOK]
        context_manifest: Optional[Dict[str, str]] = None,
        layout: Optional[Dict[str, str]] = None
    ) -> AsyncSandbox:
        """
        Bootstraps an Agent-Ready environment.
        [OPTIMIZED v3.1] Uses Session Pool for faster startup.
        [BYOK] Uses runtime.e2b_api_key if available.
        Args:
            layout: (Preferred) PhysicalPath -> Hash. Exact placement.
        """
        # 1. Resolve E2B Key
        e2b_key = runtime.e2b_api_key if (runtime and runtime.e2b_api_key) else settings.E2B_API_KEY
        if not e2b_key:
            raise ExecutionError("Infrastructure", "E2B API Key missing (Header/Env).")

        # [OPTIMIZED v3.1] Use pool instead of direct creation
        pool = get_sandbox_pool()
        sb, is_new = await pool.get(project_id, e2b_key)

        # Inject Context (Optimistic Sync)
        target_map = layout if layout is not None else context_manifest
        use_layout_keys = layout is not None
        if target_map:
            await self.sync_manifest(
                sb,
                target_map,
                is_new_session=is_new,
                use_layout_keys=use_layout_keys
            )

        return sb

    async def sync_manifest(
        self,
        sb: AsyncSandbox,
        local_manifest: Dict[str, str],
        is_new_session: bool = False,
        use_layout_keys: bool = False
    ):
        """
        Syncs files to sandbox using optimistic checks + Chunking.
        [OPTIMIZED v3.1] Parallel chunk upload for faster sync.
        """
        if not local_manifest:
            return

        remote_manifest = {}
        work_dir = settings.SANDBOX_DATA_DIR
        manifest_path = f"{work_dir}/{self.manifest_file}"

        # 1. Optimistic Check
        if not is_new_session:
            try:
                content = await sb.files.read(manifest_path)
                remote_manifest = json.loads(content)
            except Exception:
                try:
                    remote_manifest = await self._compute_delta_manifest(sb, local_manifest, only_manifest=True)
                except Exception:
                    remote_manifest = {}

        # 2. Compute Delta
        delta: Dict[str, str] = {}
        new_remote_manifest = remote_manifest.copy()

        for path_key, blob_hash in local_manifest.items():
            if use_layout_keys:
                arcname = path_key.lstrip("/")
            else:
                arcname = self._resolve_arcname(path_key)
            if remote_manifest.get(arcname) != blob_hash:
                delta[path_key] = blob_hash
            new_remote_manifest[arcname] = blob_hash

        if not delta:
            logger.debug("Optimistic Sync: Up to date.")
            return

        # 3. Chunked Upload with Parallel Processing (v3.1)
        CHUNK_SIZE_LIMIT = 50 * 1024 * 1024 
        
        chunks: list = []
        current_chunk = {}
        current_size = 0

        for path_key, blob_hash in delta.items():
            f_size = self.assets.get_blob_size(blob_hash)
            if current_size + f_size > CHUNK_SIZE_LIMIT and current_chunk:
                chunks.append(current_chunk)
                current_chunk = {}
                current_size = 0
            current_chunk[path_key] = blob_hash
            current_size += f_size
        
        if current_chunk:
            chunks.append(current_chunk)

        logger.info(f"Optimistic Sync: {len(delta)} files in {len(chunks)} chunks (parallel: 3)")

        # Helper to upload a chunk
        async def upload_chunk(chunk_data: Dict[str, str], idx: int) -> bool:
            if not chunk_data: return True
            
            try:
                tar_gen = StreamingTarball.create_stream(chunk_data, self.assets)
                estimated_size = sum(self.assets.get_blob_size(blob_hash) for blob_hash in chunk_data.values())
                estimated_mb = max(1, estimated_size / (1024*1024))
                upload_timeout = max(120, min(10 + int(estimated_mb * 15), 600))

                with tempfile.NamedTemporaryFile(delete=False) as tmp_tar:
                    async for tar_chunk in tar_gen:
                        tmp_tar.write(tar_chunk)
                    tmp_tar.flush()
                    tmp_tar.close()

                    remote_tar = f"/tmp/sync_delta_{idx}.tar.gz"
                    with open(tmp_tar.name, "rb") as f:
                        await sb.files.write(remote_tar, f, request_timeout=upload_timeout)

                    cmd = await sb.commands.run(
                        f"mkdir -p {work_dir} && tar -xzf {remote_tar} -C {work_dir}; rm -f {remote_tar}", 
                        timeout=300
                    )
                    if cmd.exit_code != 0:
                        raise ExecutionError("Infrastructure", f"Tar extraction failed for batch {idx}")
                    return True
            except Exception as e:
                logger.error(f"Upload chunk {idx} failed: {e}")
                return False
            finally:
                if 'tmp_tar' in locals() and os.path.exists(tmp_tar.name):
                    os.remove(tmp_tar.name)

        # 4. Parallel Upload (v3.1 Optimization)
        # Upload chunks in parallel batches of 3
        semaphore = asyncio.Semaphore(3)
        results = []
        
        async def upload_with_semaphore(chunk_data, idx):
            async with semaphore:
                success = await upload_chunk(chunk_data, idx)
                return success

        for i in range(0, len(chunks), 3):
            batch = chunks[i:i+3]
            tasks = [upload_with_semaphore(chunk, i + j) for j, chunk in enumerate(batch)]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            results.extend(batch_results)
        
        success_count = sum(1 for r in results if r is True)
        logger.info(f"Sync Complete: {success_count}/{len(chunks)} chunks uploaded successfully.")

        # 5. Atomic Update of Sidecar Manifest
        await sb.files.write(manifest_path, json.dumps(new_remote_manifest))

    async def _compute_delta_manifest(
        self,
        sb: AsyncSandbox,
        local_manifest: Dict[str, str],
        only_manifest: bool = False
    ) -> Dict[str, str]:
        """
        Calculates which files need to be uploaded by comparing SHA256 hashes.
        If only_manifest is True, returns the remote manifest map (arcname -> hash).
        """
        if not local_manifest:
            return {}

        work_dir = settings.SANDBOX_DATA_DIR

        # Python script to calculate hashes of existing files in the sandbox
        # Returns JSON: { "relative/path/to/file": "sha256_hash" }
        try:
            tmpl = jinja_env.get_template("infra/scripts/compute_hashes.py.j2")
            hash_script = tmpl.render(work_dir=work_dir)
        except Exception as e:
            logger.error(f"Failed to load hash script template: {e}")
            return {} if only_manifest else local_manifest

        # [FIX] Write script to file to avoid shell quoting issues with python -c
        hash_script_path = "/tmp/checksum.py"
        await sb.files.write(hash_script_path, hash_script)

        proc = await sb.commands.run(f"python3 {hash_script_path}", timeout=30)

        if proc.exit_code != 0:
            logger.warning(f"Remote hash calculation failed: {proc.stderr}")
            return {} if only_manifest else local_manifest

        try:
            remote_hashes = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return {} if only_manifest else local_manifest

        if only_manifest:
            return remote_hashes

        delta = {}
        for v_path, blob_hash in local_manifest.items():
            arcname = self._resolve_arcname(v_path)
            if arcname not in remote_hashes or remote_hashes[arcname] != blob_hash:
                delta[v_path] = blob_hash

        return delta

    def _resolve_arcname(self, v_path: str) -> str:
        """
        Resolves virtual path to sandbox-relative path.
        Must match logic in app/utils/io_tarball.py
        """
        parts = Path(v_path).parts
        if len(parts) > 2 and parts[0] == "history":
            # e.g. history/1.1/data.csv -> data.csv
            return str(Path(*parts[2:]))
        # e.g. img/plot.png -> img/plot.png
        return v_path.lstrip("/")

    async def _setup_router(self, sb: AsyncSandbox, runtime: Optional[RuntimeConfig] = None) -> str:
        """
        初始化 Claude Code Router。
        生成配置文件并后台启动路由服务，将 localhost:8080 映射到第三方 LLM。
        
        [FIX] 修复参数签名: 添加 runtime 以支持 BYOK 鉴权传递
        """
        if not settings.USE_LLM_ROUTER:
            return ""

        base = (runtime.llm_base_url if runtime else None) or settings.BASE_URL
        if is_anthropic_compatible_base(base):
            logger.info("Using Anthropic-compatible Claude Code endpoint directly; router disabled.")
            return ""

        try:
            await sb.commands.run("pgrep -f ccr")
            return "http://127.0.0.1:8080"
        except Exception:
            pass

        # [BYOK] Resolve config for Router Config File
        # 修复：确保 runtime 可用，避免 NameError
        key = (runtime.llm_api_key if runtime else None) or settings.OPENAI_API_KEY or settings.API_KEY
        base = (runtime.llm_base_url if runtime else None) or settings.BASE_URL
        model = (runtime.llm_model_name if runtime else None) or settings.AGENT_MODEL_NAME or settings.MODEL_NAME

        if base and "/chat/completions" not in base:
            base = base.rstrip("/") + "/chat/completions"

        provider_config = {
            "HOST": "127.0.0.1",
            "PORT": 8080,
            "Providers": [{
                "name": "custom_provider",
                "api_base_url": base,
                "api_key": key,
                "models": [model]
            }],
            "Router": {
                "default": f"custom_provider,{model}"
            }
        }

        config_path = "/home/user/.claude-code-router/config.json"
        log_path = "/tmp/ccr.log"

        try:
            await sb.commands.run("mkdir -p /home/user/.claude-code-router")
            await sb.files.write(config_path, json.dumps(provider_config, indent=2))

            logger.info("Starting ccr service...")
            await sb.commands.run(f"ccr start > {log_path} 2>&1", background=True)

            try:
                tmpl = jinja_env.get_template("infra/scripts/wait_for_router.py.j2")
                check_script = tmpl.render()
            except Exception as e:
                logger.warning(f"Failed to load router check script: {e}")
                check_script = "import time; time.sleep(2)" # Fallback
            await sb.files.write("/tmp/wait_for_router.py", check_script)

            try:
                await sb.commands.run("python3 /tmp/wait_for_router.py", timeout=15)
            except Exception:
                logger.error("Router failed to bind port 8080 within timeout.")
                try:
                    logs = await sb.commands.run(f"cat {log_path}")
                    logger.error(f"=== CCR Logs ===\n{logs.stdout}\n================")
                except Exception:
                    pass
                return ""

            logger.info(
                f"✅ Claude Code Router started. Mapping 'default' -> {model}"
            )
            return "http://127.0.0.1:8080"

        except Exception as e:
            logger.error(f"Failed to start router: {e}")
            return ""

    async def run_agent_cli(
        self, 
        sb: AsyncSandbox, 
        prompt: str,
        runtime: Optional[RuntimeConfig] = None,  # [BYOK]
        timeout: Optional[int] = None  # [NEW] Allow dynamic boundary control
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Executes `claude` CLI with a specific time budget.
        """
        work_dir = settings.SANDBOX_DATA_DIR
        await sb.files.write(f"{work_dir}/prompt.txt", prompt)

        # [FIX] Pass runtime to _setup_router to enable BYOK config in router.json
        router_url = await self._setup_router(sb, runtime)

        env = {
            "NODE_OPTIONS": "--max-old-space-size=7500",
            "TAVILY_API_KEY": settings.TAVILY_API_KEY,
            "CI": "true",
            "NO_COLOR": "true",
        }

        if router_url:
            env["ANTHROPIC_BASE_URL"] = router_url
            env["ANTHROPIC_API_KEY"] = "sk-ant-api03-" + "dummy-key-for-local-router"
            env["ANTHROPIC_MODEL"] = "default"
            logger.info(f"🚀 Starting Agent CLI in ROUTER MODE (Target: {settings.AGENT_MODEL_NAME})")
        else:
            # [FIX] Direct Mode Fallback with BYOK support
            # Use runtime key if available, else fallback to settings
            byok_key = runtime.llm_api_key if runtime else None
            direct_key = byok_key or settings.ANTHROPIC_API_KEY or settings.API_KEY or ""
            direct_base = (runtime.llm_base_url if runtime else None) or settings.BASE_URL
            direct_model = (
                (runtime.llm_model_name if runtime else None)
                or settings.AGENT_MODEL_NAME
                or settings.MODEL_NAME
            )

            if is_anthropic_compatible_base(direct_base):
                normalized_model = normalize_anthropic_model(direct_model)
                env["ANTHROPIC_BASE_URL"] = anthropic_base_url(direct_base)
                env["ANTHROPIC_MODEL"] = normalized_model
                env["ANTHROPIC_SMALL_FAST_MODEL"] = normalized_model
                env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = normalized_model
                env["ANTHROPIC_DEFAULT_OPUS_MODEL"] = normalized_model
                env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = normalized_model
                env["API_TIMEOUT_MS"] = "3000000"
                env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
                if "minimax" in direct_base.lower() or "minimaxi" in direct_base.lower():
                    env["ANTHROPIC_AUTH_TOKEN"] = direct_key
                else:
                    env["ANTHROPIC_API_KEY"] = direct_key
                logger.info(f"🚀 Starting Agent CLI in ANTHROPIC-COMPAT DIRECT MODE (Target: {normalized_model})")
            else:
                env["ANTHROPIC_API_KEY"] = direct_key
                env["OPENAI_API_KEY"] = byok_key or settings.OPENAI_API_KEY
                env["ANTHROPIC_BASE_URL"] = "https://api.anthropic.com"
                logger.info("🚀 Starting Agent CLI in DIRECT MODE")

        # [FIX] Use dynamic timeout or fallback to global hard cap
        execution_timeout = timeout or settings.SANDBOX_EXECUTION_TIMEOUT

        cmd = "claude -p < prompt.txt --dangerously-skip-permissions"
        logger.info(f"Starting Agent CLI: {cmd} (Timeout: {execution_timeout}s)")

        queue: asyncio.Queue = asyncio.Queue()

        def on_stdout(output):
            queue.put_nowait({"type": "stdout", "content": output})

        def on_stderr(output):
            queue.put_nowait({"type": "stderr", "content": output})

        proc = await sb.commands.run(
            cmd,
            cwd=work_dir,
            envs=env,
            background=True,
            on_stdout=on_stdout,
            on_stderr=on_stderr,
            timeout=execution_timeout  # [FIX] Apply boundary
        )

        async def waiter():
            try:
                await proc.wait()
            except TimeoutException:
                logger.error(f"Agent CLI Timed Out ({execution_timeout}s)")
                await queue.put({
                    "type": "error",
                    "content": f"\n\n[SYSTEM ERROR] Execution Timed Out after {execution_timeout}s.\n"
                               "The agent took too long to respond or got stuck in a loop."
                })
                try:
                    await proc.kill()
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Agent CLI Wait Error: {e}")
                await queue.put({
                    "type": "error",
                    "content": f"\n\n[SYSTEM ERROR] Process Wait Failed: {str(e)}"
                })
            finally:
                await queue.put(None)

        asyncio.create_task(waiter())

        while True:
            item = await queue.get()
            if item is None:
                break
            yield self._classify_log(item)
            queue.task_done()

        if proc.exit_code is not None and proc.exit_code != 0:
            yield {"type": "error", "content": f"Agent Process Failed (Exit Code: {proc.exit_code})"}

    async def run_command_stream(
        self,
        sb: AsyncSandbox,
        cmd: str,
        cwd: Optional[str] = None,
        timeout: int = 120
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Direct Mode: Runs a shell command and streams output.
        """
        queue: asyncio.Queue = asyncio.Queue()

        def on_stdout(output):
            queue.put_nowait({"type": "stdout", "content": output})

        def on_stderr(output):
            queue.put_nowait({"type": "stderr", "content": output})

        proc = await sb.commands.run(
            cmd,
            cwd=cwd or settings.SANDBOX_DATA_DIR,
            background=True,
            on_stdout=on_stdout,
            on_stderr=on_stderr,
            timeout=timeout
        )

        async def waiter():
            try:
                await proc.wait()
            except TimeoutException:
                logger.error(f"Command '{cmd[:20]}...' Timed Out ({timeout}s)")
                await queue.put({
                    "type": "error",
                    "content": f"\n\n[SYSTEM ERROR] Command Timed Out after {timeout}s."
                })
                try:
                    await proc.kill()
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Command Wait Error: {e}")
                await queue.put({
                    "type": "error",
                    "content": f"\n\n[SYSTEM ERROR] Process Error: {str(e)}"
                })
            finally:
                await queue.put(None)

        asyncio.create_task(waiter())

        while True:
            item = await queue.get()
            if item is None:
                break
            yield self._classify_log(item)
            queue.task_done()

        if proc.exit_code is not None and proc.exit_code != 0:
            yield {"type": "error", "content": f"Command failed (Exit Code: {proc.exit_code})"}

    async def harvest_artifacts_diff(
        self,
        sb: AsyncSandbox,
        known_manifest: Dict[str, str]
    ) -> Tuple[Dict[str, bytes], Dict[str, str]]:
        """
        Diff Sync: Download only new/changed files to CAS, but return full manifest.
        """
        try:
            tmpl = jinja_env.get_template("infra/scripts/harvest_hashes.py.j2")
            py_hash = tmpl.render()
        except Exception as e:
            logger.error(f"Failed to load harvest script: {e}")
            return {}, {}

        cmd = "python3 - <<'PY'\n" + py_hash + "\nPY"

        try:
            res = await sb.commands.run(
                cmd,
                cwd=settings.SANDBOX_DATA_DIR,
                timeout=300
            )
        except Exception:
            return {}, {}

        if res.exit_code != 0:
            return {}, {}

        try:
            remote_map = json.loads(res.stdout)
        except json.JSONDecodeError:
            return {}, {}

        new_artifacts: Dict[str, bytes] = {}
        final_manifest: Dict[str, str] = {}

        for fname, fhash in remote_map.items():
            if fname in ["prompt.txt", "goal.txt"]:
                continue

            final_manifest[fname] = fhash

            if fname not in known_manifest or known_manifest[fname] != fhash:
                try:
                    content = await sb.files.read(
                        f"{settings.SANDBOX_DATA_DIR}/{fname}",
                        format="bytes"
                    )
                    new_artifacts[fname] = content
                except Exception as e:
                    logger.warning(f"Failed to download {fname}: {e}")
                    final_manifest.pop(fname, None)

        # Update sidecar manifest to keep optimistic sync accurate
        try:
            manifest_path = f"{settings.SANDBOX_DATA_DIR}/{self.manifest_file}"
            await sb.files.write(manifest_path, json.dumps(final_manifest))
        except Exception as e:
            logger.debug(f"Failed to update sidecar manifest after harvest: {e}")

        return new_artifacts, final_manifest

    async def _get_or_create_session(self, project_id: str, api_key: str) -> Tuple[AsyncSandbox, bool]:
        """
        L1 Lifecycle: Project Session.
        Returns: (sandbox_instance, is_newly_created)
        """
        label_key = settings.E2B_PROJECT_LABEL_KEY
        meta_filter = {label_key: str(project_id)}

        try:
            paginator = AsyncSandbox.list(
                api_key=api_key,  # [BYOK]
                query=SandboxQuery(metadata=meta_filter)
            )

            found = []
            if hasattr(paginator, 'next_items'):
                while True:
                    batch = await paginator.next_items()
                    if not batch: break
                    found.extend(batch)
                    if not paginator.has_next: break
            else:
                found = paginator

            target = next((s for s in found if s.state == "running"), None)

            if target:
                logger.info(f"Resuming Sandbox {target.sandbox_id} for {project_id}")
                sb = await AsyncSandbox.connect(target.sandbox_id, api_key=api_key)  # [BYOK]
                return sb, False  # Resumed

        except Exception as e:
            logger.warning(f"Discovery failed ({e}). Creating new session.")

        logger.info(f"Creating NEW Sandbox for {project_id}")
        try:
            sb = await AsyncSandbox.create(
                template=settings.E2B_TEMPLATE_ALIAS,
                api_key=api_key,  # [BYOK]
                metadata=meta_filter,
                timeout=settings.SANDBOX_TIMEOUT
            )
        except SandboxException as e:
            msg = str(e).lower()
            if "template" in msg and "not found" in msg:
                logger.warning(
                    f"Template '{settings.E2B_TEMPLATE_ALIAS}' missing. Building and retrying..."
                )
                
                # [FIX] Capture the NEW ID directly from the build process
                new_template_id = await SandboxTemplateManager.ensure_template_ready()
                
                # [FIX] Use the explicit ID for retry, NOT the alias
                # This bypasses the stale alias resolution cache
                sb = await AsyncSandbox.create(
                    template=new_template_id,
                    api_key=api_key,  # [BYOK]
                    metadata=meta_filter,
                    timeout=settings.SANDBOX_TIMEOUT
                )
            else:
                raise
        await sb.commands.run(f"mkdir -p {settings.SANDBOX_DATA_DIR}")
        return sb, True  # New

    async def get_active_session(self, project_id: str, api_key: Optional[str] = None) -> Optional[AsyncSandbox]:
        """
        Return a running sandbox for this project without creating a new one.
        """
        # Fallback to server key if not provided (e.g. background tasks without BYOK, rare)
        key = api_key or settings.E2B_API_KEY
        
        label_key = settings.E2B_PROJECT_LABEL_KEY
        meta_filter = {label_key: str(project_id)}

        try:
            paginator = AsyncSandbox.list(
                api_key=key,  # [BYOK]
                query=SandboxQuery(metadata=meta_filter)
            )

            found = []
            if hasattr(paginator, "next_items"):
                while True:
                    batch = await paginator.next_items()
                    if not batch: break
                    found.extend(batch)
                    if not paginator.has_next: break
            else:
                found = paginator

            target = next((s for s in found if s.state == "running"), None)
            if target:
                return await AsyncSandbox.connect(target.sandbox_id, api_key=key)  # [BYOK]
        except Exception as e:
            logger.warning(f"Active session lookup failed ({e}).")

        return None

    async def _sync_files(self, sb: AsyncSandbox, manifest: Dict[str, str], target_dir: str) -> Dict[str, str]:
        """
        Uploads files to the isolated directory.
        """
        if not manifest:
            return {}

        baseline = {}
        tasks = []

        for v_path, blob_hash in manifest.items():
            filename = v_path.split("/")[-1]
            remote_path = f"{target_dir}/{filename}"

            tasks.append(self._stream_upload(sb, remote_path, blob_hash))
            baseline[filename] = blob_hash

        if tasks:
            logger.info(f"Uploading {len(tasks)} files to {target_dir}...")
            await asyncio.gather(*tasks)

        return baseline

    async def _stream_upload(self, sb: AsyncSandbox, remote_path: str, blob_hash: str):
        try:
            with self.assets.open_blob(blob_hash) as f:
                await sb.files.write(remote_path, f, request_timeout=1200)
        except Exception as e:
            logger.warning(f"Failed to upload {remote_path}: {e}")

    def _clean_log(self, content: str) -> str:
        if not content:
            return ""
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", content)

    def _classify_log(self, event: Dict[str, Any]) -> Dict[str, Any]:
        content = self._clean_log(event.get("content", ""))
        etype = event.get("type", "stdout")

        if any(k in content for k in ["Thinking", "Tool Use", "Relevant file", "Cost:"]):
            return {"type": "thought", "content": content}
        return {"type": etype, "content": content}

    def _make_error(self, msg: str) -> NodeOutput:
        safe_msg = str(msg) if msg else "Unknown System Error"
        return NodeOutput(
            blocks=[ContentBlock(
                type=BlockType.MARKDOWN,
                label="Error",
                content=safe_msg
            )],
            metadata={"exit_code": 1}
        )

    async def _safe_kill(self, sb: AsyncSandbox):
        try:
            await sb.kill()
        except:
            pass
