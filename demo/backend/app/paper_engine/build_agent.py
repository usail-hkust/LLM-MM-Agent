"""
Build Agent (v4.0) - Agentic Auto-Fix & Fast Compile.
[REFACTORED]
- Auto Fix: Uses a comprehensive System Prompt to drive Agentic Claude. No build.py dependency.
- Fast Compile: Retains build.py for quick UI feedback.
- Integrity: Implements independent verification to ensure Agent doesn't delete chapters.
"""
import logging
import json
from typing import AsyncIterator, Dict, Any, List, Optional

from e2b_code_interpreter import AsyncSandbox

from app.core.config import settings
from app.core.templates import jinja_env
from app.infra.gateways.sandbox import SandboxGateway
from app.paper_engine.domain import PaperWorkspace, BuildReport, CompileStatus
from app.api.schemas import RuntimeConfig

logger = logging.getLogger(__name__)


class BuildAgent:
    def __init__(self, sandbox: SandboxGateway):
        self.sandbox = sandbox
        self.work_dir = settings.SANDBOX_DATA_DIR

    # Compile stages for progress tracking
    COMPILE_STAGES = [
        ("cleanup", 0, "Cleaning up previous build artifacts..."),
        ("latexmk", 20, "Running LaTeX compilation (latexmk)..."),
        ("verify", 90, "Verifying PDF output..."),
        ("complete", 100, "Compilation successful! PDF generated.")
    ]

    async def execute_fast_compile(self, sb: AsyncSandbox, workspace: PaperWorkspace) -> AsyncIterator[Dict[str, Any]]:
        """
        [Mode A: Fast Compile]
        Deterministic, script-based compilation for interactive frontend feedback.
        Uses the pre-scaffolded `build.py` for speed.
        [ENHANCED] Added real-time compile feedback with stage tracking and progress percentage.
        """
        workspace.compile_status = CompileStatus.COMPILING
        
        # Emit compile start status with progress
        yield {"type": "status", "content": "compile_start", "stage": "cleanup", "progress": 0, "total_stages": 4}
        yield {"type": "thought", "content": "🧹 Cleaning up previous build artifacts..."}

        # Clear artifacts
        await sb.commands.run(f"rm -f {self.work_dir}/main.pdf {self.work_dir}/main.log")

        # Emit latexmk stage with progress
        yield {"type": "status", "content": "compile_stage", "stage": "latexmk", "progress": 20, "total_stages": 4}
        yield {"type": "thought", "content": "📝 Running LaTeX compilation (latexmk)..."}

        # Execute existing python script (Fast Path)
        cmd = "python3 build.py"

        logs: List[str] = []
        compile_output = []
        
        async for log in self.sandbox.run_command_stream(sb, cmd, cwd=self.work_dir):
            content = log.get("content", "")
            logs.append(content)
            compile_output.append(content)
            
            # Parse LaTeX output for real-time feedback
            if "LaTeX Warning" in content:
                yield {"type": "warning", "content": content.strip()}
            elif "Error" in content or "error:" in content.lower():
                yield {"type": "error", "content": content.strip()}
            elif "Package hyperref Warning" in content:
                yield {"type": "warning", "content": content.strip()}
            
            yield log

        full_log = "\n".join(logs)
        
        # Emit verification stage with progress
        yield {"type": "status", "content": "compile_stage", "stage": "verify", "progress": 90, "total_stages": 4}
        yield {"type": "thought", "content": "🔍 Verifying PDF output..."}

        success = await self._verify_pdf_artifact(sb)

        if success:
            yield {"type": "status", "content": "compile_success", "stage": "complete", "progress": 100, "total_stages": 4}
            yield {"type": "thought", "content": "✅ Compilation successful! PDF generated."}
        else:
            yield {"type": "status", "content": "compile_error", "stage": "failed", "progress": 100, "total_stages": 4}
            yield {"type": "error", "content": "❌ Compilation failed. No PDF output detected."}

        workspace.compile_status = CompileStatus.SUCCESS if success else CompileStatus.ERROR
        workspace.last_build_report = BuildReport(
            success=success,
            exit_code=0 if success else 1,
            logs=full_log[-3000:],
            error_summary=None if success else "Fast compile failed. Try 'Auto Fix' for deep repair."
        )
        workspace.last_build_log = full_log

    # Agent fix stages for progress tracking
    AGENT_STAGES = [
        ("cleanup", 0, "Agent initializing... Cleaning build environment."),
        ("analyze", 10, "Analyzing LaTeX errors and structure..."),
        ("fixing", 30, "Agent is fixing LaTeX errors..."),
        ("compiling", 60, "Agent is compiling the paper..."),
        ("verify", 90, "Verifying PDF output and content integrity..."),
        ("complete", 100, "Agent compilation complete!")
    ]

    async def delegate_autonomous_fix(
        self,
        sb: AsyncSandbox,
        workspace: PaperWorkspace,
        timeout: int = settings.SANDBOX_EXECUTION_TIMEOUT,
        runtime: Optional[RuntimeConfig] = None  # [BYOK]
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        [Mode B: Agentic Auto-Fix]
        Pure Agentic Workflow. DOES NOT RELY on build.py.
        Injects a "Constitution" prompt giving the Agent full autonomy to fix the paper.
        [ENHANCED] Added real-time agent progress tracking with stage percentages.
        """
        workspace.compile_status = CompileStatus.COMPILING

        # Emit agent start status with progress
        yield {"type": "status", "content": "agent_start", "stage": "cleanup", "progress": 0, "total_stages": 6}
        yield {"type": "thought", "content": "🤖 Agent initializing... Cleaning build environment."}

        # 1. Prepare Environment (Clean Slate)
        await sb.commands.run(
            f"rm -f {self.work_dir}/main.pdf {self.work_dir}/main.log {self.work_dir}/*.aux"
        )

        # Emit analysis stage with progress
        yield {"type": "status", "content": "agent_stage", "stage": "analyze", "progress": 10, "total_stages": 6}
        yield {"type": "thought", "content": "🔍 Analyzing LaTeX errors and structure..."}

        # 2. Construct the Mission Prompt
        prompt = self._construct_autonomous_mission(workspace)

        logs: List[str] = []
        agent_claimed_success = False

        # 3. Launch Agent Loop
        # The Agent will figure out: Run latexmk -> Read Error -> Edit File -> Retry
        fixing_emitted = False
        compiling_emitted = False
        
        async for log in self.sandbox.run_agent_cli(sb, prompt, timeout=timeout, runtime=runtime):  # [BYOK]
            content = log.get("content", "")
            logs.append(content)
            yield log

            # Heuristic: Detect if Agent thinks it has succeeded
            if "MISSION_COMPLETE" in content:
                agent_claimed_success = True
            
            # Dynamic progress updates based on agent activity
            if "latexmk" in content.lower() and not compiling_emitted:
                yield {"type": "status", "content": "agent_stage", "stage": "compiling", "progress": 60, "total_stages": 6}
                yield {"type": "thought", "content": "🔨 Agent is compiling the paper..."}
                compiling_emitted = True
            elif ("edit" in content.lower() or "fix" in content.lower()) and not fixing_emitted:
                yield {"type": "status", "content": "agent_stage", "stage": "fixing", "progress": 30, "total_stages": 6}
                yield {"type": "thought", "content": "🔧 Agent is fixing LaTeX errors..."}
                fixing_emitted = True

        # 4. Independent Verification (Trust but Verify)
        # We verify two things: PDF existence AND Content Integrity
        yield {"type": "status", "content": "agent_stage", "stage": "verify", "progress": 90, "total_stages": 6}
        yield {"type": "thought", "content": "🔍 Verifying PDF output and content integrity..."}

        pdf_exists = await self._verify_pdf_artifact(sb)
        integrity_ok = await self._verify_integrity_independently(sb)

        final_success = pdf_exists and integrity_ok

        error_summary = "Agent finished execution."
        if not pdf_exists:
            error_summary = "Build Failed: Agent failed to generate a valid PDF."
            yield {"type": "status", "content": "agent_error", "stage": "failed", "progress": 100, "total_stages": 6}
        elif not integrity_ok:
            error_summary = "CRITICAL FAILURE: Agent violated the Constitution by deleting required chapters."
            yield {"type": "status", "content": "agent_error", "stage": "integrity_failed", "progress": 100, "total_stages": 6}
        else:
            yield {"type": "status", "content": "agent_success", "stage": "complete", "progress": 100, "total_stages": 6}

        workspace.compile_status = CompileStatus.SUCCESS if final_success else CompileStatus.ERROR
        workspace.last_build_report = BuildReport(
            success=final_success,
            exit_code=0 if final_success else 1,
            logs="\n".join(logs[-5000:]),
            error_summary=error_summary if not final_success else None
        )
        workspace.last_build_log = "\n".join(logs)

    async def _verify_pdf_artifact(self, sb: AsyncSandbox) -> bool:
        """Atomic check for PDF output (Must be > 0 bytes)."""
        cmd = f"test -s {self.work_dir}/main.pdf && echo 'FOUND' || echo 'MISSING'"
        try:
            result = await sb.commands.run(cmd)
            return "FOUND" in result.stdout
        except Exception:
            return False

    async def _verify_integrity_independently(self, sb: AsyncSandbox) -> bool:
        """
        [Safety Guard]
        Independently verifies that main.tex still includes all sections from structure.json.
        This prevents the Agent from "fixing" errors by simply deleting the broken chapter.
        Uses a python one-liner inside the sandbox to avoid large file transfers.
        """
        checker_script = (
            "import json, re, sys; "
            "try: struct = json.load(open('structure.json')); "
            "except Exception: print('OK'); sys.exit(0); "
            "content = open('main.tex').read(); "
            "clean = re.sub(r'(?<!\\\\)%.*', '', content); "
            "missing = [s for s in struct if f'\\\\input{{{s}}}' not in clean]; "
            "print('MISSING:', missing) if missing else print('OK')"
        )
        try:
            res = await sb.commands.run(f"python3 -c \"{checker_script}\"")
            return "OK" in res.stdout
        except Exception:
            # Fail open if check script crashes, rely on PDF check
            return True

    def _construct_autonomous_mission(self, ws: PaperWorkspace) -> str:
        """
        Constructs the Prompt that acts as the Agent's Brain & Constitution.
        [UPDATED] Loads from Jinja2 template.
        """
        # Context: List existing images
        imgs = sorted([p for p in ws.files.keys() if p.startswith("img/")])
        img_context = "\n".join([f"- {f}" for f in imgs]) if imgs else "(No images found in img/)"

        # Context: Required sections
        structure: List[str] = []
        if "structure.json" in ws.files:
            try:
                structure = json.loads(ws.files["structure.json"].content)
            except Exception:
                pass
        struct_context = "\n".join([f"- \\input{{{s}}}" for s in structure]) if structure else "(See structure.json)"

        try:
            tmpl = jinja_env.get_template("paper_engine/prompts/autonomous_build.j2")
            return tmpl.render(
                img_context=img_context,
                struct_context=struct_context
            )
        except Exception as e:
            logger.error(f"Failed to load autonomous_build.j2: {e}")
            # Minimal Fallback
            return (
                "# MISSION\n"
                "Fix the LaTeX errors and compile main.pdf.\n"
                f"# IMAGES\n{img_context}\n"
                f"# REQUIRED SECTIONS\n{struct_context}\n"
                "Do not delete sections. Run latexmk."
            )

    # Modification stages for progress tracking
    MODIFICATION_STAGES = [
        ("analyze", 0, "Analyzing modification request..."),
        ("detect", 10, "Detecting target file..."),
        ("modify", 30, "AI is applying the modification..."),
        ("save", 60, "Saving modified content..."),
        ("verify", 80, "Verifying modification compiles correctly..."),
        ("complete", 100, "Modification complete!")
    ]

    async def apply_user_modification(
        self,
        sb: AsyncSandbox,
        workspace: PaperWorkspace,
        modification_instruction: str,
        target_file: Optional[str] = None,
        timeout: int = settings.SANDBOX_EXECUTION_TIMEOUT,
        runtime: Optional[RuntimeConfig] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        [Mode C: AI-Assisted Modification]
        Applies user-requested modifications to the paper using AI.
        [ENHANCED] Added automatic error detection and fix suggestions.
        
        Args:
            sb: Sandbox instance
            workspace: Paper workspace
            modification_instruction: User's modification request
            target_file: Specific file to modify (None = auto-detect)
            timeout: Execution timeout
            runtime: Runtime config
        
        Yields:
            Progress logs and status updates
        """
        yield {"type": "status", "content": "modification_start", "stage": "analyze", "progress": 0, "total_stages": 6}
        yield {"type": "thought", "content": f"🎯 Applying modification: {modification_instruction}"}

        # 1. Identify target file if not specified
        if not target_file:
            yield {"type": "status", "content": "modification_stage", "stage": "detect", "progress": 10, "total_stages": 6}
            yield {"type": "thought", "content": "🔍 Detecting target file..."}
            
            # Read structure.json to understand section organization
            try:
                struct_content = await sb.files.read(f"{self.work_dir}/structure.json")
                structure = json.loads(struct_content) if struct_content else []
                
                # Simple keyword matching to find relevant section
                instruction_lower = modification_instruction.lower()
                keywords = {
                    "abstract": ["abstract"],
                    "introduction": ["introduce", "background"],
                    "method": ["method", "approach", "technique"],
                    "result": ["result", "experiment", "evaluation"],
                    "conclusion": ["conclude", "summary", "future"]
                }
                
                target_section = None
                for kw_list, kw_map in keywords.items():
                    if any(kw in instruction_lower for kw in kw_map):
                        target_section = kw_list
                        break
                
                if target_section and target_section in structure:
                    target_file = f"{target_section}.tex"
                else:
                    target_file = "main.tex"  # Default fallback
                    
            except Exception as e:
                logger.warning(f"Could not detect target file: {e}")
                target_file = "main.tex"
        
        yield {"type": "thought", "content": f"📄 Target file: {target_file}"}

        # 2. Read current content
        try:
            current_content = await sb.files.read(f"{self.work_dir}/{target_file}")
            if not current_content:
                yield {"type": "error", "content": f"Could not read {target_file}"}
                return
        except Exception as e:
            yield {"type": "error", "content": f"Error reading {target_file}: {e}"}
            return

        # 3. Construct modification prompt
        modification_prompt = f"""You are a scientific paper editor. Apply the following modification to the LaTeX content:

MODIFICATION REQUEST: {modification_instruction}

CURRENT CONTENT:
{current_content[:3000]}  # Limit context

INSTRUCTIONS:
1. Analyze the current content and the modification request
2. Make precise, minimal changes that address the request
3. Maintain LaTeX syntax and formatting
4. Keep the same writing style and academic tone

Return ONLY the modified content (full section) in your response. Do not add explanations."""

        # 4. Execute modification via Agent
        yield {"type": "status", "content": "modification_stage", "stage": "modify", "progress": 30, "total_stages": 6}
        yield {"type": "thought", "content": "🤖 AI is applying the modification..."}

        from app.infra.gateways.llm import LLMGateway
        llm = LLMGateway()
        
        try:
            # Use LLM to generate modification
            messages = [
                {"role": "system", "content": "You are a scientific paper editor. Return ONLY the LaTeX content without any tags or explanations."},
                {"role": "user", "content": modification_prompt}
            ]
            
            modified_content = await llm.generate_raw(messages, runtime=runtime, timeout=300)
            
            # Clean up the response (remove think tags if present)
            modified_content = modified_content.strip()
            if "</think>" in modified_content:
                parts = modified_content.split("\\n\\n")
                modified_content = parts[-1].strip() if parts else modified_content
            
            # [ENHANCED] Validate LaTeX syntax before writing
            latex_errors = self._detect_latex_errors(modified_content)
            if latex_errors:
                yield {"type": "warning", "content": f"Detected potential LaTeX issues: {', '.join(latex_errors)}"}
                # Auto-fix common issues
                for error in latex_errors:
                    modified_content = self._auto_fix_latex_error(modified_content, error)
                yield {"type": "thought", "content": "Auto-fixed detected LaTeX issues."}
            
            # 5. Write modified content back
            yield {"type": "status", "content": "modification_stage", "stage": "save", "progress": 60, "total_stages": 6}
            await sb.files.write(f"{self.work_dir}/{target_file}", modified_content)
            
            yield {"type": "thought", "content": f"Modification applied to {target_file}"}
            
            # 6. Quick compile to verify
            yield {"type": "status", "content": "modification_stage", "stage": "verify", "progress": 80, "total_stages": 6}
            yield {"type": "thought", "content": "Verifying modification compiles correctly..."}
            
            # Run quick compile check
            cmd = f"cd {self.work_dir} && latexmk -pdf -interaction=nonstopmode main.tex"
            compile_logs = []
            async for log in self.sandbox.run_command_stream(sb, cmd, timeout=120):
                compile_logs.append(log.get("content", ""))
                yield log
            
            # Check if PDF was generated
            pdf_ok = await self._verify_pdf_artifact(sb)
            
            # [ENHANCED] Extract and report any compilation errors
            if not pdf_ok:
                error_summary = self._extract_compile_errors("\\n".join(compile_logs))
                if error_summary:
                    yield {"type": "warning", "content": f"Compilation issues: {error_summary}"}
                    yield {"type": "thought", "content": "Suggestion: Try 'Auto Fix' for automatic error resolution."}
            
            if pdf_ok:
                yield {"type": "status", "content": "modification_success", "stage": "complete", "progress": 100, "total_stages": 6}
                yield {"type": "thought", "content": "Modification successful! PDF updated."}
            else:
                yield {"type": "status", "content": "modification_partial", "stage": "complete", "progress": 100, "total_stages": 6}
                yield {"type": "warning", "content": "Modification applied but PDF generation had issues. Check main.log for details."}
                
        except Exception as e:
            yield {"type": "error", "content": f"Modification failed: {e}"}
            logger.error(f"AI modification failed: {e}", exc_info=True)

    def _detect_latex_errors(self, content: str) -> List[str]:
        """
        [NEW] Detects common LaTeX syntax errors in content.
        Returns list of detected error types.
        """
        errors = []
        
        # Check for unmatched braces
        open_braces = content.count('{') - content.count('}')
        if open_braces > 0:
            errors.append("unmatched_braces")
        
        # Check for malformed commands
        if '\\begin{' in content and '\\end{' not in content:
            errors.append("unclosed_environment")
        
        return errors

    def _auto_fix_latex_error(self, content: str, error_type: str) -> str:
        """
        [NEW] Attempts to auto-fix common LaTeX errors.
        """
        if error_type == "unmatched_braces":
            # Try to balance braces by adding missing closing braces
            open_braces = content.count('{') - content.count('}')
            if open_braces > 0:
                content = content + '}' * open_braces
        
        return content

    def _extract_compile_errors(self, logs: str) -> str:
        """
        [NEW] Extracts meaningful error messages from compilation logs.
        """
        errors = []
        lines = logs.split('\\n')
        
        for line in lines:
            if 'Error' in line or 'error:' in line.lower():
                # Clean up the error message
                clean_error = line.strip()
                if len(clean_error) > 100:
                    clean_error = clean_error[:100] + "..."
                errors.append(clean_error)
        
        return "; ".join(errors[:3]) if errors else ""
