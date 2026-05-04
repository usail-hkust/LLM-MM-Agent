"""
Ingestion Service.

Handles the intelligent processing of input files before they enter the workflow.
Classifies files into 'Context' (Problem Descriptions) and 'Data' (Datasets),
and extracts text to augment the initial instruction.
"""
import logging
from typing import Dict, List, Tuple, Any, Optional
import json

from app.infra.gateways.llm import LLMGateway
from app.infra.asset_manager import AssetManager
from app.infra.file_parsers import FileETL
from app.core.templates import jinja_env
from app.api.schemas import RuntimeConfig

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(self, llm: LLMGateway, assets: AssetManager):
        self.llm = llm
        self.assets = assets

    async def process_inputs(
        self, 
        file_manifest: Dict[str, str], 
        current_instruction: str,
        runtime: Optional[RuntimeConfig] = None
    ) -> Tuple[str, List[str]]:
        """
        Analyzes input files, extracts context, and augments the user instruction.
        
        Returns:
            Tuple[augmented_instruction, dataset_file_list]
        """
        if not file_manifest:
            return current_instruction, []

        filenames = list(file_manifest.keys())
        
        # 1. Classify Files via LLM
        context_files, dataset_files = await self._classify_files(filenames, runtime)
        
        # 2. Extract Text from Context Files
        context_text = await self._extract_context_content(context_files, file_manifest)
        
        # 3. Augment Instruction
        augmented_instruction = self._build_augmented_instruction(
            current_instruction, 
            context_text, 
            dataset_files
        )
        
        return augmented_instruction, dataset_files

    async def _classify_files(self, filenames: List[str], runtime: Optional[RuntimeConfig] = None) -> Tuple[List[str], List[str]]:
        """
        Uses LLM to categorize files into Problem Description vs Datasets.
        """
        if not filenames:
            return [], []

        # Use Jinja template instead of hardcoded string
        try:
            tmpl = jinja_env.get_template("system/ingestion_classifier.j2")
            system_content = tmpl.render()
        except Exception as e:
            logger.warning(f"Template load failed: {e}. Using fallback prompt.")
            system_content = (
                "You are a Data Engineering Assistant. Classify filenames into 'context' and 'data'. "
                "Return strictly JSON."
            )

        prompt = [
            {
                "role": "system",
                "content": system_content
            },
            {
                "role": "user",
                "content": f"Filenames: {json.dumps(filenames)}"
            }
        ]

        try:
            # Use a fast model if possible, or default
            # [FIX] Pass node_id="Ingestion" for observability (was defaulting to "Unknown")
            output = await self.llm.generate(prompt, temperature=0.1, node_id="Ingestion", runtime=runtime)  # [BYOK]
            
            # Extract JSON from the first block
            json_block = output.get_block("json") or output.get_block("data")
            
            if json_block and isinstance(json_block.content, dict):
                data = json_block.content
                context_files = data.get("context", [])
                dataset_files = data.get("data", [])
                logger.info(f"File Classification Result: Context={context_files}, Data={dataset_files}")
                return context_files, dataset_files
            
            # Fallback parsing if structure is raw text
            logger.warning("LLM did not return structured JSON for file classification. Using extension fallback.")
            return self._fallback_classification(filenames)

        except Exception as e:
            logger.error(f"File classification failed: {e}. Using fallback.")
            return self._fallback_classification(filenames)

    def _fallback_classification(self, filenames: List[str]) -> Tuple[List[str], List[str]]:
        """Heuristic fallback based on extensions."""
        context = []
        data = []
        data_exts = {'.csv', '.xlsx', '.xls', '.json', '.parquet', '.zip', '.tar', '.gz'}
        
        for f in filenames:
            lower = f.lower()
            if any(lower.endswith(ext) for ext in data_exts):
                data.append(f)
            else:
                context.append(f)
        return context, data

    async def _extract_context_content(self, context_files: List[str], manifest: Dict[str, str]) -> str:
        """Reads bytes from CAS and extracts text."""
        aggregated_text = []
        
        for fname in context_files:
            blob_hash = manifest.get(fname)
            if not blob_hash:
                continue
                
            content_bytes = await self.assets.get_asset_bytes(blob_hash)
            if content_bytes:
                text = FileETL.extract_text(fname, content_bytes)
                aggregated_text.append(f"--- START OF FILE: {fname} ---\n{text}\n--- END OF FILE: {fname} ---")
            else:
                logger.warning(f"Could not read bytes for {fname}")
                
        return "\n\n".join(aggregated_text)

    def _build_augmented_instruction(
        self, 
        original_instruction: str, 
        context_text: str, 
        dataset_files: List[str]
    ) -> str:
        """Constructs the final prompt string."""
        parts = []
        
        if original_instruction:
            parts.append(f"=== USER INSTRUCTION ===\n{original_instruction}\n")
            
        if context_text:
            parts.append(f"=== PROBLEM CONTEXT / BACKGROUND MATERIALS ===\n{context_text}\n")
            
        if dataset_files:
            file_list_str = "\n".join([f"- {f}" for f in dataset_files])
            parts.append(f"=== AVAILABLE DATASETS ===\nThe following data files are available for analysis:\n{file_list_str}\n")
            
        return "\n".join(parts)

