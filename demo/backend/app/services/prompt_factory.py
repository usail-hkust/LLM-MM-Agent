"""
Prompt Factory - Jinja2 template rendering.

[Updated] JIT Context Unification (Anti-Poisoning).
Instead of appending a confusing 'Asset Identity Map', we now rewrite the
history string on-the-fly to replace virtual paths with physical paths.
This ensures the LLM sees a consistent world view.
"""
import logging
import json
from typing import Dict, Any, List, Optional, Tuple

from app.domain.blueprints import NodeBlueprint
from app.domain.unified_io import NodeOutput
from app.core.templates import jinja_env

logger = logging.getLogger(__name__)


class PromptFactory:
    """
    [Service]
    Prepares the rendering context for Jinja2 templates.
    """

    def _physicalize_context(self, text: str, asset_map: Optional[Dict[str, str]]) -> str:
        """
        [Anti-Poisoning] JIT Context Rewriter.
        Replaces virtual paths (DB View) with physical paths (Execution View) in text.
        
        Input: "Based on [Chart](history/2.1/plot.png)..."
        Map:   {"history/2.1/plot.png": "img/fig_01.png"}
        Output: "Based on [Chart](img/fig_01.png)..."
        """
        if not text or not asset_map:
            return text
        
        # Sort by length descending to prevent partial prefix replacement issues
        # e.g., replacing 'data.csv' shouldn't break 'my_data.csv' (though virtual paths are usually absolute)
        sorted_map = sorted(asset_map.items(), key=lambda x: len(x[0]), reverse=True)
        
        physicalized_text = text
        for v_path, p_path in sorted_map:
            physicalized_text = physicalized_text.replace(v_path, p_path)
            
        return physicalized_text

    def create_messages(
        self,
        blueprint: NodeBlueprint,
        intent: str,
        history_str: str,
        file_manifest: Dict[str, str],
        user_input: Dict[str, Any],
        previous_output: Optional[NodeOutput] = None,
        file_schemas: Dict[str, List[str]] = None,  # [NEW] Added argument
        num_samples: int = 1,  # [NEW] SCA batch size injection
        asset_map: Dict[str, str] = None  # [NEW] Virtual -> Physical
    ) -> List[Dict[str, str]]:
        """
        Constructs the LLM messages list.

        Args:
            intent: The interaction intent (generate/critique/refine).
            previous_output: The content of the current working draft (for iteration).
        """

        # 1. Select Template based on Intent
        template_ref = blueprint.get_template_for_intent(intent)

        if not template_ref:
            raise ValueError(f"No template found for intent '{intent}' in node {blueprint.id}")

        # 2. Normalize Inputs
        instruction = user_input.get("instruction")

        # [FIX] Jinja2 Silent Disappearance Check
        # Ensure instruction is never None or empty to prevent dangling headers in templates.
        # If the user didn't provide one, we inject a neutral fallback so the prompt remains coherent.
        if not instruction or not str(instruction).strip():
            instruction = "Proceed with the optimal modeling protocol strictly defined by your designated Role and Context."
            logger.debug(f"PromptFactory: Injected default instruction for node {blueprint.id}")

        dynamic_inputs = user_input.get("inputs", {}) if "inputs" in user_input else user_input

        # Ensure manifest is robust (prevent NoneType error)
        safe_manifest = file_manifest or {}
        
        # [REFACTOR] Check if Node is Agentic
        is_agentic = blueprint.meta.get("executor_engine") == "agentic_claude"

        # [FIX] JIT Context Unification
        # Rewrite the history string to match the physical environment
        clean_history = self._physicalize_context(history_str, asset_map)

        # [FIX] Schema Suppression for Agents
        # Agents use tools to inspect data; injecting schemas wastes tokens and causes hallucinations.
        # Generators still need them.
        safe_schemas = {} if is_agentic else (file_schemas or {})

        # [FIX] Resolve Physical Filenames for the prompt list
        physical_file_list: List[str] = []
        physical_schemas: Dict[str, List[str]] = {}

        if asset_map:
            # Canonical Mode (Reporting Phase)
            for v_path in safe_manifest.keys():
                if v_path in asset_map:
                    p_name = asset_map[v_path]
                    physical_file_list.append(p_name)
                    if v_path in safe_schemas:
                        physical_schemas[p_name] = safe_schemas[v_path]
                else:
                    fname = v_path.split("/")[-1]
                    physical_file_list.append(fname)
                    if v_path in safe_schemas:
                        physical_schemas[fname] = safe_schemas[v_path]
        else:
            # Flattening Mode (Analysis Phase)
            for v_path in safe_manifest.keys():
                fname = v_path.split("/")[-1]
                physical_file_list.append(fname)
                if v_path in safe_schemas:
                    physical_schemas[fname] = safe_schemas[v_path]

        physical_file_list.sort()

        # 3. Prepare Context Data (for Critique/Refine)
        target_context = {}
        if previous_output:
            # We also need to physicalize the previous output content if it contains references
            raw_ctx = previous_output.to_context_dict()
            # Serialize, replace, deserialize to handle nested structures deeply
            # This is expensive but safe. Alternatively, we assume context references are rare in raw data.
            # For now, we apply it to string fields we know might contain paths.
            if asset_map:
                try:
                    ctx_str = json.dumps(raw_ctx)
                    clean_ctx_str = self._physicalize_context(ctx_str, asset_map)
                    target_context = json.loads(clean_ctx_str)
                except Exception:
                    target_context = raw_ctx
            else:
                target_context = raw_ctx

        # 4. [REFACTOR] Output Protocol Suppression for Agents
        output_spec = blueprint.output_spec
        if is_agentic:
            expected_type = None
            target_label = None
        else:
            expected_type = output_spec.expected_type if output_spec else None
            target_label = output_spec.target_label if output_spec else None

        # [FIX] REMOVED: Asset Identity Map Generation
        # We no longer append the mapping table. The text is already rewritten.
        asset_map_str = "" 

        # 5. Prepare Template Variables
        render_vars = {
            "node": blueprint,
            "intent": intent,
            "global_history": clean_history,  # Pass the CLEAN history
            "file_list": physical_file_list,
            "file_schemas": physical_schemas,
            "user_instruction": instruction,
            "inputs": dynamic_inputs,
            "has_files": bool(safe_manifest),
            "target_output": target_context,
            "previous_draft": target_context,
            "expected_type": expected_type,
            "target_label": target_label,
            "num_samples": num_samples,
            "asset_map_str": asset_map_str # Empty string
        }

        try:
            # 6. Render Inner Template
            task_tmpl = jinja_env.get_template(template_ref)
            task_instructions = task_tmpl.render(**render_vars)

            # 7. Render Outer System Template
            meta_tmpl = jinja_env.get_template("base/meta_system.j2")
            
            # Apply physicalization to task instructions too (in case template logic used raw inputs)
            clean_task_instructions = self._physicalize_context(task_instructions, asset_map)

            system_prompt_content = meta_tmpl.render(
                specific_instructions=clean_task_instructions,
                **render_vars
            )

            # 8. Construct Messages
            messages = [{"role": "system", "content": system_prompt_content}]

            user_content = "Please execute the task."
            if instruction:
                user_content += f"\n\nUser Instruction: {instruction}"

            if intent == "refine" and "feedback" in dynamic_inputs:
                user_content += f"\n\nFeedback to Address: {dynamic_inputs['feedback']}"
                if not is_agentic:
                    user_content += "\n\n**IMPORTANT**: You must output the FULL, self-contained implementation, encapsulated strictly within the requested block format to ensure atomic replaceability."

            messages.append({"role": "user", "content": user_content})

            return messages

        except Exception as e:
            logger.error(f"Failed to render prompt for {blueprint.id}: {e}")
            raise ValueError(f"Prompt rendering failed: {e}")

    def create_task_messages(
        self,
        template_path: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        Renders a specific template directly (for sub-tasks like drafting).
        """
        try:
            # Extract potential asset map from context if passed (unlikely for subtasks but safe to support)
            # Usually subtasks use pre-processed context.
            
            task_tmpl = jinja_env.get_template(template_path)
            task_instructions = task_tmpl.render(**context)

            system_vars = {
                "node": {"title": "System Task", "id": "system", "phase_label": "Execution"},
                "global_history": context.get("global_history", ""),
                "file_list": context.get("file_list", []),
                "specific_instructions": task_instructions,
                "inputs": {},
                "has_files": bool(context.get("file_list")),
                "num_samples": 1,
                "target_label": None,
                "expected_type": None
            }

            meta_tmpl = jinja_env.get_template("base/meta_system.j2")
            system_prompt = meta_tmpl.render(**system_vars)

            return [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Proceed with the writing task."}
            ]

        except Exception as e:
            logger.error(f"Failed to render task template {template_path}: {e}")
            raise ValueError(f"Prompt rendering failed: {e}")

    def create_agent_goal(
        self,
        blueprint: NodeBlueprint,
        intent: str,
        context_str: str,
        user_input: Dict[str, Any],
        file_manifest: Dict[str, str] = None,
        asset_map: Dict[str, str] = None
    ) -> str:
        """
        Construct a context-aware goal for agentic CLI.
        [FIX] Apply JIT Physicalization to the agent context too.
        """
        role = blueprint.meta.get("agent_role", "Data Scientist")
        focus = blueprint.meta.get("agent_focus", "analysis")
        directive = blueprint.meta.get("primary_directive", "Solve the task.")

        # [FIX] Rewrite context paths instead of appending mapping
        clean_context_str = self._physicalize_context(context_str, asset_map)

        handover, constraints = self._build_handover_context(user_input, file_manifest, focus)

        # Physicalize handover notes if they contain virtual paths
        handover = self._physicalize_context(handover, asset_map)

        # [OPTIMIZATION] Source Diet Protocol
        # Force visualization nodes to be efficient to prevent snowball effect
        if focus == "visualization":
            constraints.append("**VISUALIZATION PROTOCOL (CRITICAL)**:")
            constraints.append("1. **FORMAT**: You MUST save all plots as `.jpg` or `.jpeg`. DO NOT use `.png` unless transparency is strictly required.")
            constraints.append("2. **RESOLUTION**: You MUST set `dpi=150` (Draft/Screen Resolution) to optimize storage. Do not use 300+ DPI.")
            constraints.append("3. **DIVERSITY**: Ensure strict non-repetition of chart types.")
            constraints.append("4. **CLEANUP**: Delete any temporary large files before finishing.")

        try:
            tmpl = jinja_env.get_template("agents/default_goal.j2")
            return tmpl.render(
                agent_role=role,
                agent_focus=focus,
                context_summary=(clean_context_str or "")[:3000],
                handover_notes=handover,
                mission_instruction=user_input.get("instruction", "Solve the task."),
                primary_directive=directive,
                dynamic_constraints=constraints
            )
        except Exception as e:
            logger.warning(f"Failed to render agent template: {e}. Falling back to legacy string.")
            instr = user_input.get("instruction", "Solve the task.")
            return (
                "# ROLE\n"
                f"You are {blueprint.title}.\n"
                "# TASK\n"
                f"{instr}\n"
                "# INSTRUCTIONS\n"
                "Execute the modeling task with scientific rigor. Explore data, implement logical structures, execute computational routines, and persist defensible outputs."
            )

    def _build_handover_context(
        self,
        user_input: Dict[str, Any],
        manifest: Dict[str, str],
        agent_focus: str
    ) -> Tuple[str, List[str]]:
        """
        Asset handover protocol.
        """
        notes: List[str] = []
        constraints: List[str] = []
        manifest = manifest or {}

        inputs = user_input.get("inputs", {})
        prev_out = inputs.get("previous_output")

        if prev_out and isinstance(prev_out, dict):
            notes.append("**Handover from Previous Step:**")
            if prev_out.get("thought"):
                summary = prev_out["thought"][:300].replace("\n", " ")
                notes.append(f"- Context: {summary}...")

        # For Agentic Handover, we rely on the normalized filenames provided by NodeProcessor
        # or the raw manifest. Since _physicalize_context handles path rewrites later,
        # we can just inspect extensions here.
        py_files = [f for f in manifest.keys() if f.endswith(".py")]
        data_files = [
            f for f in manifest.keys()
            if f.endswith((".csv", ".xlsx", ".json", ".parquet"))
        ]

        if py_files:
            # These might be virtual paths, they will be fixed by create_agent_goal's call to _physicalize_context
            notes.append(f"**Existing Code:** {', '.join(py_files)}")
        if data_files:
            notes.append(f"**Existing Data:** {', '.join(data_files)}")

        if agent_focus == "visualization":
            if data_files:
                constraints.append(f"Load data directly from {data_files[0]} (or similar).")
            if py_files:
                constraints.append(
                    f"Check {py_files[0]} to understand data structure, but DO NOT run it if it trains models."
                )
            constraints.append("Do NOT re-train models or re-run heavy simulations.")
            constraints.append("Create a NEW script 'plot.py' specifically for visualization.")
        elif agent_focus == "implementation":
            if py_files:
                constraints.append(f"Refine or extend existing script {py_files[0]}.")
            else:
                constraints.append("Write a robust Python script 'script.py'.")
        elif agent_focus == "inspection":
            constraints.append("Read the data files using pandas.")
            constraints.append("Output summary statistics (head, describe, info).")

        if not constraints:
            constraints.append("Write a Python script to perform the task.")
            constraints.append("Run the script and fix any errors.")

        return "\n".join(notes), constraints
