"""Shared pipeline utilities and common structures to reduce code duplication."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any
from src.retrieval.retriever_interface import Retriever
from src.validation.schema_validator import load_schema
from config.config_loader import get_pipeline_top_k


@dataclass
class PipelineOutput:
    """Standard output structure for all pipeline operations."""
    updated: list[Path]
    created: list[Path]
    report: str
    related_count: int
    related_test_cases: list[dict] = None


def display_retrieval_results(related: List[Dict[str, Any]], pipeline_name: str) -> None:
    """
    Display retrieval results in a consistent format across all pipelines.
    
    Args:
        related: List of related test cases
        pipeline_name: Name of the pipeline for context
    """
    print(f"🔍 Retrieved {len(related)} relevant test cases:")
    for i, tc in enumerate(related[:3], 1):  # Show top 3
        score = tc.get('score', 0)
        keyword_score = tc.get('keyword_score', 0)
        semantic_score = tc.get('semantic_score', 0)
        priority_score = tc.get('priority_score', 0)
        
        print(f"  {i}. {tc.get('title', 'Unknown')}")
        print(f"     Score: {score:.3f} (Keyword: {keyword_score:.3f}, Semantic: {semantic_score:.3f}, Priority: {priority_score:.3f})")
        print(f"     Priority: {tc.get('priority', 'Unknown')}")
    if len(related) > 3:
        print(f"  ... and {len(related) - 3} more")
    print()


def perform_retrieval(
    change, 
    retriever: Retriever, 
    config, 
    pipeline_name: str,
    query_text: str,
    default_top_k: int = 10
) -> List[Dict[str, Any]]:
    """
    Perform retrieval with consistent logic across all pipelines.
    
    Args:
        change: Change request object
        retriever: Retriever instance
        config: Configuration object
        pipeline_name: Name of the pipeline
        query_text: Query text for retrieval
        default_top_k: Default top_k if config is not available
        
    Returns:
        List of related test cases
    """
    top_k = get_pipeline_top_k(config, pipeline_name) if config else default_top_k
    related = retriever.query(query_text, top_k=top_k)
    
    # Display results
    display_retrieval_results(related, pipeline_name)
    
    return related


def load_validator(schema_path: Path):
    """
    Load schema validator with consistent error handling.
    
    Args:
        schema_path: Path to schema file
        
    Returns:
        Loaded validator
    """
    return load_schema(schema_path)


def display_pipeline_completion(
    pipeline_name: str,
    analyzed_count: int,
    updated_count: int,
    created_count: int = 0,
    log_entries_count: int = 0,
    updated_paths: List[Path] = None
) -> None:
    """
    Display consistent pipeline completion summary.
    
    Args:
        pipeline_name: Name of the pipeline
        analyzed_count: Number of test cases analyzed
        updated_count: Number of test cases updated
        created_count: Number of test cases created
        log_entries_count: Number of log entries
        updated_paths: List of updated file paths
    """
    print(f"✅ Completed {pipeline_name} analysis:")
    print(f"   📊 Analyzed: {analyzed_count} test cases")
    print(f"   ✏️  Updated: {updated_count} test cases")
    if created_count > 0:
        print(f"   📄 Created: {created_count} test cases")
    print(f"   📝 Analysis log entries: {log_entries_count}")
    
    if updated_paths:
        print(f"   📁 Updated files:")
        for path in updated_paths:
            print(f"      - {path.name}")


def display_skip_message(
    pipeline_name: str,
    reason: str,
    analyzed_count: int,
    updated_count: int = 0,
    created_count: int = 0,
    log_entries_count: int = 0
) -> None:
    """
    Display consistent skip message across pipelines.
    
    Args:
        pipeline_name: Name of the pipeline
        reason: Reason for skipping
        analyzed_count: Number that would have been analyzed
        updated_count: Number updated (usually 0 when skipped)
        created_count: Number created (usually 0 when skipped)
        log_entries_count: Number of log entries (usually 0 when skipped)
    """
    print(f"⚠️  {reason}, skipping {pipeline_name} analysis")
    
    if analyzed_count > 0:
        print(f"✅ {pipeline_name} analysis skipped:")
        print(f"   📊 Would have analyzed: {analyzed_count} test cases")
        print(f"   ✏️  Updated: {updated_count} test cases")
        if created_count > 0:
            print(f"   📄 Created: {created_count} test cases")
        print(f"   📝 Analysis log entries: {log_entries_count}")
