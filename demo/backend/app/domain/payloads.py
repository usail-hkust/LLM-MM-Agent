"""
Service Payloads - Command Pattern.

Defines the input contracts for the Service Layer.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class RunNodeCommand(BaseModel):
    """
    Payload for triggering node execution (Service Layer Input).
    Supports Unified Interaction Loop via `intent`.
    """
    project_id: str
    node_id: str
    instruction: Optional[str] = None
    
    # Dynamic inputs (e.g., from a previous selection or user form)
    inputs: Dict[str, Any] = Field(default_factory=dict)
    
    # [Unified Interaction]
    # "generate" (Default), "critique", "refine", "execute_only"
    intent: str = "generate"
    
    # Configuration override (e.g. retry logic, num_samples for SCA)
    config: Dict[str, Any] = Field(default_factory=dict)


class UpdateNodeCommand(BaseModel):
    """
    Payload for modifying a working draft (Manual Edit / Selection).
    """
    project_id: str
    node_id: str
    
    # If selecting a specific output option
    selected_output_id: Optional[str] = None
    
    # If manually editing content
    manual_content: Optional[str] = None
    target_block_id: Optional[str] = None


class CommitNodeCommand(BaseModel):
    """
    Payload for finalizing a node version.
    """
    project_id: str
    node_id: str

