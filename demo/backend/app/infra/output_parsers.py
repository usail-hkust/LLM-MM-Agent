"""
Output Parser - MEP Protocol with Dual-Anchor Defense.
[FIXED] Added aggressive noise filtering to prevent empty blocks.
"""
import re
import json
import html
import logging
from typing import List, Dict, Any, Optional

from app.core.definitions import BlockType
from app.domain.unified_io import NodeOutput, ContentBlock

logger = logging.getLogger(__name__)


class StandardOutputParser:
    """
    Parses LLM output conforming to the Markdown Fenced-Block Protocol (MEP).
    Implements Dual-Anchor Protocol:
    1. L1: Fence Label (e.g., ```json:label)
    2. L2: Content Anchor (e.g., "__kind__": "label" or # @kind: label)
    """
    
    # Regex captures: 1=type, 2=label (optional)
    FENCE_START = re.compile(r"^\s*```(\w*)(?::([a-zA-Z0-9_\-\s]+))?\s*$", re.MULTILINE)
    FENCE_END = re.compile(r"^\s*```\s*$", re.MULTILINE)
    
    # L2 Magic Anchor Regex: matches "# @kind: label" or "% @kind: label"
    # Scans first few lines of code/text blocks.
    MAGIC_ANCHOR = re.compile(r"^[\#%]\s*@kind:\s*([a-zA-Z0-9_\-]+)", re.MULTILINE)
    
    # L2 JSON Anchor Regex: matches "__kind__": "label"
    JSON_ANCHOR = re.compile(r'"__kind__"\s*:\s*"([^"]+)"')

    def parse(self, text: str) -> NodeOutput:
        """Standard single-pass parsing."""
        blocks, thought = self._extract_blocks_and_thought(text)
        
        # [FIX] Zero-Fence Fallback Strategy
        # If no structured blocks (CODE/DATA) were detected via Fences,
        # check if the "thought" content is actually a raw JSON payload.
        # This fixes fragility when LLMs return valid JSON without markdown wrappers.
        has_structured_content = any(b.type in (BlockType.CODE, BlockType.DATA, BlockType.FILE) for b in blocks)
        
        if not has_structured_content and thought.strip():
            stripped_thought = thought.strip()
            # Heuristic: Starts and ends with JSON-like brackets
            if (stripped_thought.startswith("{") and stripped_thought.endswith("}")) or \
               (stripped_thought.startswith("[") and stripped_thought.endswith("]")):
                
                parsed_json = self._repair_json(stripped_thought)
                
                # If _repair_json returns a dict or list, it was successful
                if isinstance(parsed_json, (dict, list)):
                    logger.info("Parser: Detected Implicit Zero-Fence JSON. Promoting to DATA block.")
                    
                    # Create a synthetic block
                    implicit_block = ContentBlock(
                        type=BlockType.DATA,
                        label="json",  # Generic label to satisfy get_block("json") lookups
                        content=parsed_json,
                        tags=["json", "implicit_repair"]
                    )
                    
                    # Inject into blocks and clear the thought (since it was data)
                    blocks.append(implicit_block)
                    thought = ""

        return NodeOutput(blocks=blocks, thought=thought)

    def parse_batch(self, text: str, target_label: str = None) -> List[NodeOutput]:
        """
        Parses multiple options.
        [FIX] Added validation to filter out empty/ghost options.
        """
        all_blocks, full_thought = self._extract_blocks_and_thought(text)
        
        if not target_label:
            return [NodeOutput(blocks=all_blocks, thought=full_thought)]

        raw_outputs = self._segment_aware_parse(target_label, text, all_blocks)
        
        # [FIX] Filter Ghost Options
        # SCA logic requires valid options. If parsing splits out a segment that has 
        # no blocks and no meaningful thought (just whitespace), discard it.
        valid_outputs = []
        for out in raw_outputs:
            has_blocks = len(out.blocks) > 0
            # Require at least 5 chars of thought to consider it a valid option description
            has_thought = len(out.thought.strip()) > 5 
            
            if has_blocks or has_thought:
                valid_outputs.append(out)
            else:
                logger.debug("Dropped ghost option (empty blocks and thought)")
                
        return valid_outputs

    def _segment_aware_parse(self, target_label: str, original_text: str, pre_parsed_blocks: List[ContentBlock]) -> List[NodeOutput]:
        # Reuse existing implementation but ensure robust matching
        matches = list(self.FENCE_START.finditer(original_text))
        target_indices = []
        for m in matches:
            label = m.group(2)
            # Fuzzy match label
            if label and target_label in label:
                target_indices.append(m.start())
        
        if not target_indices:
             return [NodeOutput(blocks=pre_parsed_blocks, thought=original_text)]

        outputs = []
        cursor = 0
        for i, start_idx in enumerate(target_indices):
            block_candidate = original_text[start_idx:]
            end_match = self.FENCE_END.search(block_candidate)
            
            if end_match:
                block_end_abs = start_idx + end_match.end()
                
                thought_text = original_text[cursor:start_idx].strip()
                block_text = original_text[start_idx:block_end_abs]
                
                try:
                    parsed_result = self.parse(block_text)
                    if parsed_result.blocks:
                        outputs.append(NodeOutput(
                            blocks=parsed_result.blocks,
                            thought=thought_text
                        ))
                    cursor = block_end_abs
                except Exception:
                    cursor = block_end_abs
            else:
                cursor = len(original_text)
        
        return outputs if outputs else [NodeOutput(blocks=pre_parsed_blocks, thought=original_text)]

    def _extract_blocks_and_thought(self, text: str) -> tuple[List[ContentBlock], str]:
        """Internal helper extracted from original parse method."""
        blocks: List[ContentBlock] = []
        text_buf: List[str] = []
        
        # [NEW] Container for the main thought/explanation
        # Collect all non-fenced text content as thought
        extracted_thought_parts: List[str] = []

        lines = text.splitlines()
        in_fence = False
        fence_meta = {"type": "text", "label": "content"}
        fence_lines = []

        for line in lines:
            # 1. Check for Fence Start
            if not in_fence:
                match = self.FENCE_START.match(line)
                if match:
                    if text_buf:
                        # Before processing fence, accumulate text_buf as thought
                        content = "\n".join(text_buf).strip()
                        if content:
                            extracted_thought_parts.append(content)
                        self._add_text_block(blocks, text_buf)
                        text_buf = []

                    in_fence = True
                    raw_type = match.group(1).lower()
                    raw_label = match.group(2)
                    
                    # Store metadata but defer processing to block end
                    # to allow L2 anchors to override generic labels
                    fence_meta = {
                        "type": raw_type, 
                        "label": raw_label
                    }
                    fence_lines = []
                    continue
            
            # 2. Check for Fence End
            if in_fence:
                if self.FENCE_END.match(line):
                    in_fence = False
                    self._add_fence_block(blocks, fence_meta, fence_lines)
                    fence_lines = []
                    continue
                else:
                    fence_lines.append(line)
                    continue

            # 3. Accumulate Text (Outside Fence)
            text_buf.append(line)
        
        if in_fence:
            self._add_fence_block(blocks, fence_meta, fence_lines)
        elif text_buf:
            # [MODIFIED] Accumulate text_buf content as thought before adding block
            content = "\n".join(text_buf).strip()
            if content:
                extracted_thought_parts.append(content)
            self._add_text_block(blocks, text_buf)

        extracted_thought = "\n".join(extracted_thought_parts).strip()
        
        # [FIX] Post-Processing Filter (The First Line of Defense)
        # Remove MARKDOWN blocks that are effectively empty (whitespace only).
        # We keep CODE/DATA blocks even if empty as they might be structurally significant.
        clean_blocks = []
        for b in blocks:
            if b.type == BlockType.MARKDOWN:
                if b.content and str(b.content).strip():
                    clean_blocks.append(b)
            else:
                clean_blocks.append(b)

        return clean_blocks, extracted_thought

    def _add_text_block(self, blocks: List[ContentBlock], lines: List[str]):
        content = "\n".join(lines).strip()
        content = html.unescape(content)
        # [FIX] Do not add if empty
        if content:
            blocks.append(ContentBlock(
                type=BlockType.MARKDOWN,
                label="Explanation",
                content=content
            ))

    def _add_fence_block(self, blocks: List[ContentBlock], meta: Dict[str, str], lines: List[str]):
        content_str = "\n".join(lines)
        # Healing: Unescape HTML entities potentially hallucinated by LLM
        content_str = html.unescape(content_str)
        
        raw_type = meta["type"]
        label = meta.get("label")
        
        # --- Dual-Anchor Resolution Strategy ---
        
        # 1. Determine Initial Type & Parse Content
        b_type = BlockType.MARKDOWN
        parsed_content: Any = content_str
        block_meta = {"language": raw_type} if raw_type else {}
        tags = [raw_type] if raw_type else []
        
        if raw_type == "latex":
            b_type = BlockType.CODE
            block_meta["language"] = "latex"
            tags.append("section_content")
        elif raw_type in ("json", "data"):
            b_type = BlockType.DATA
            parsed_content = self._repair_json(content_str)
            if isinstance(parsed_content, str):
                # Parsing failed, fallback to text but keep error info
                b_type = BlockType.MARKDOWN
                block_meta["error"] = "Invalid JSON"
        elif raw_type in ("python", "code", "bash", "sh", "shell", "javascript", "js"):
            b_type = BlockType.CODE
        elif raw_type == "file":
             b_type = BlockType.FILE
        
        # 2. L2 Anchor Check (Content Inspection)
        detected_label = None
        
        # Case A: JSON Structure Anchor ("__kind__" field)
        # Check parsed dict first, then raw string (for robustness)
        if b_type == BlockType.DATA and isinstance(parsed_content, dict):
            if "__kind__" in parsed_content:
                detected_label = parsed_content["__kind__"]
        elif raw_type in ("json", "data"):
             match = self.JSON_ANCHOR.search(content_str)
             if match:
                 detected_label = match.group(1)

        # Case B: Magic Comment Anchor (# @kind: label)
        # Check code or text blocks (scan first 5 lines)
        if not detected_label and b_type in (BlockType.CODE, BlockType.MARKDOWN):
            header = "\n".join(lines[:5])
            match = self.MAGIC_ANCHOR.search(header)
            if match:
                detected_label = match.group(1)

        # 3. Finalize Label (Priority: L2 > L1 > Default)
        if detected_label:
            label = detected_label
            # Explicitly add the detected semantic label to tags
            if detected_label not in tags:
                tags.append(detected_label)
        elif not label:
            # [FIX] Defensive Fallback: Use type-specific defaults
            # For CODE blocks, default to "code" (lowercase) to match magic comment convention
            if b_type == BlockType.CODE:
                label = "code"
            elif b_type == BlockType.DATA:
                label = "Output"
            else:
                label = "Code"
        
        # [FIX] If fence had explicit label (e.g., python:code), use it
        # This handles cases where template specifies ```python:code but magic comment is missing
        if meta.get("label") and not detected_label:
            label = meta["label"]
            if label not in tags:
                tags.append(label)
        
        # Normalize label for semantic tagging (ensure safe_label is in tags)
        if label:
            safe_label = "".join(c for c in label if c.isalnum() or c in "_-").lower()
            if safe_label and safe_label not in tags:
                tags.append(safe_label)
        
        # [FIX] Filter empty Fence Blocks unless they are CODE/DATA
        # Empty text fences are usually mistakes.
        if b_type == BlockType.MARKDOWN and not str(parsed_content).strip():
            return

        blocks.append(ContentBlock(
            type=b_type,
            label=label,
            content=parsed_content,
            meta=block_meta,
            tags=tags
        ))

    def _repair_json(self, json_str: str) -> Any:
        if not json_str.strip():
            return {}
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return json_str
