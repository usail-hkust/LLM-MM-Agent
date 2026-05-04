"""
Paper Engine Subsystem (v2.0).
Sandbox-first, file-centric LaTeX workspace manager.
"""
from app.paper_engine.manager import PaperEngineManager
from app.paper_engine.domain import PaperWorkspace, VirtualFile

__all__ = ["PaperEngineManager", "PaperWorkspace", "VirtualFile"]
