"""
Scaffolding Service.
Generates the initial LaTeX directory structure.
[FIX] Generates 'structure.json' to enforce content integrity in the Sandbox.
"""
import json
import logging
import re
from typing import List, Dict, Any, Tuple, Union

from app.paper_engine.domain import VirtualFile, FileType, WritingTask
from app.paper_engine.templates.static_files import MAIN_TEX_TEMPLATE, EASYMCM_STY, BUILD_SCRIPT

logger = logging.getLogger(__name__)


class Scaffolder:
    def generate_skeleton(
        self,
        project_id: str,
        outline: List[Union[str, Dict[str, Any]]],
        metadata: Dict[str, Any],
        assets_map: Dict[str, str],
    ) -> Tuple[Dict[str, VirtualFile], List[WritingTask]]:
        """
        Creates the initial file map and the writing plan.
        """
        files: Dict[str, VirtualFile] = {}
        tasks: List[WritingTask] = []

        # 1. Level 0: Immutable System Files
        files["easymcm.sty"] = VirtualFile(
            path="easymcm.sty",
            content=EASYMCM_STY,
            file_type=FileType.STYLE,
            is_readonly=True,
        )
        
        # 2. Level 1: Mutable Sections & Integrity Manifest
        sections_meta = []
        # [INTEGRITY] List of references that MUST exist in main.tex
        required_inputs = []

        # Abstract
        abs_filename = "sections/00_abstract.tex"
        abs_ref = "sections/00_abstract" # LaTeX \input standard (no ext)
        
        files[abs_filename] = VirtualFile(
            path=abs_filename,
            content="% Abstract\n% <CONTENT_PLACEHOLDER>\n",
            file_type=FileType.LATEX_PART,
            is_readonly=False,
        )
        tasks.append(WritingTask(
            target_path=abs_filename,
            title="Abstract",
            instruction="Write a concise abstract summarizing the problem, methodology, and key results."
        ))
        # Abstract is critical structure
        required_inputs.append(abs_ref)

        # Content Sections
        # [FIX] Track valid index to handle skipped sections
        valid_section_index = 1
        
        for item in outline:  # Removed enumerate(outline) to handle manual indexing
            if isinstance(item, dict):
                title = item.get("title") or f"Section {valid_section_index}"
                instruction = item.get("instruction") or f"Write content for {title}."
                raw_tags = item.get("context_tags") or item.get("tags") or []
                if isinstance(raw_tags, list):
                    context_tags = [str(t).strip() for t in raw_tags if str(t).strip()]
                elif isinstance(raw_tags, str) and raw_tags.strip():
                    context_tags = [raw_tags.strip()]
                else:
                    context_tags = []
            else:
                title = str(item)
                instruction = f"Write detailed academic content for section: {title}."
                context_tags = []

            # --- [CRITICAL FIX] FILTER OUT REFERENCES ---
            # Prevent Reference/Bibliography sections from being generated to avoid LaTeX build errors
            # (Missing .bib file, undefined citations, etc.)
            title_lower = title.lower()
            if "reference" in title_lower or "bibliography" in title_lower or "works cited" in title_lower:
                logger.info(f"Scaffolder: Skipped reference section '{title}' to prevent build errors.")
                continue
            # ---------------------------------------------

            safe_title = self._sanitize_filename(title)
            # Use valid_section_index instead of i
            filename = f"sections/{valid_section_index:02d}_{safe_title}.tex"
            ref_name = f"sections/{valid_section_index:02d}_{safe_title}"

            content = (
                f"% Section: {title}\n"
                f"\\section{{{title}}}\n"
                f"\\label{{sec:{safe_title}}}\n\n"
                f"% <CONTENT_PLACEHOLDER>\n"
            )

            files[filename] = VirtualFile(
                path=filename,
                content=content,
                file_type=FileType.LATEX_PART,
                is_readonly=False,
            )
            tasks.append(WritingTask(
                target_path=filename,
                title=title,
                instruction=instruction,
                context_tags=context_tags
            ))
            sections_meta.append({"title": title, "path": ref_name})
            required_inputs.append(ref_name)
            
            valid_section_index += 1

        # 3. Main TeX (Level 0) - Control Plane
        input_cmds = []
        abstract_cmd = f"\\input{{{abs_ref}}}"
        
        for sec in sections_meta:
            input_cmds.append(f"\\input{{{sec['path']}}}")
            input_cmds.append("\\newpage")

        main_content = MAIN_TEX_TEMPLATE
        main_content = main_content.replace("{{CONTROL_NUMBER}}", str(metadata.get("control_number", "0000")))
        main_content = main_content.replace("{{PROBLEM_ID}}", str(metadata.get("problem_id", "A")))
        main_content = main_content.replace("{{TITLE}}", str(metadata.get("title", "Modeling Report")))
        main_content = main_content.replace("{{ABSTRACT_INPUT}}", abstract_cmd)
        main_content = main_content.replace("{{INPUTS}}", "\n".join(input_cmds))

        files["main.tex"] = VirtualFile(
            path="main.tex",
            content=main_content,
            file_type=FileType.LATEX_MAIN,
            is_readonly=True, # [FIX] Marked ReadOnly to trigger SyncService protection
        )

        # [FIX] Generate Integrity Manifest (structure.json)
        # This file informs build.py about what constitutes a "complete" paper.
        files["structure.json"] = VirtualFile(
            path="structure.json",
            content=json.dumps(required_inputs, indent=2),
            file_type=FileType.BUILD_LOG,
            is_readonly=True,
        )

        files["build.py"] = VirtualFile(
            path="build.py",
            content=BUILD_SCRIPT,
            file_type=FileType.SCRIPT,
            is_readonly=True,
        )
        files["assets_map.json"] = VirtualFile(
            path="assets_map.json",
            content=json.dumps(assets_map, indent=2),
            file_type=FileType.BUILD_LOG,
            is_readonly=True,
        )

        return files, tasks

    def _sanitize_filename(self, title: str) -> str:
        clean = re.sub(r"^[\d\.\s]+", "", title)
        clean = re.sub(r"[^a-zA-Z0-9]", "_", clean)
        return clean.lower()[:25]
