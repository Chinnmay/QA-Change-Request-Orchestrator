"""Database setup and initialization utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.retrieval.hybrid.hybrid_retriever import HybridRetriever
from config.config_loader import get_retriever_config


def setup_database_retriever(
    config,
    test_cases_dir: Path,
    cache_dir: Path,
    verbose: bool = True
) -> HybridRetriever:
    """Set up and initialize the hybrid retriever.
    
    Args:
        config: Configuration object containing database settings
        test_cases_dir: Directory containing test case JSON files
        cache_dir: Directory for caching database and embeddings
        verbose: Whether to print progress messages
        
    Returns:
        Initialized HybridRetriever instance
    """
    if verbose:
        print("🔍 Setting up database search system...")
    
    # Get database configuration
    db_config = get_retriever_config(config, "hybrid")
    db_filename = db_config.get("db_file", "test_cases.db")
    db_cache_dir = cache_dir / "database"
    db_cache_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_cache_dir / db_filename
    
    # Create retrieval config from YAML settings (with defaults)
    retrieval_config = {
        "keyword_weight": db_config.get("keyword_weight", 0.4),
        "semantic_weight": db_config.get("semantic_weight", 0.4),
        "priority_weight": db_config.get("priority_weight", 0.2),
        "max_candidates": db_config.get("max_candidates", 200),
        "max_results": 10,
        "min_similarity_threshold": db_config.get("min_similarity_threshold", 0.1)
    }
    
    # Try to load existing database
    retriever = HybridRetriever.load_from_cache(db_cache_dir, db_path, retrieval_config)
    
    if retriever is None:
        if verbose:
            print("📚 Building database from test cases...")
        retriever = HybridRetriever.from_test_case_dir(test_cases_dir, db_path, retrieval_config)
        
        # Generate embeddings for semantic search
        if verbose:
            print("🧠 Generating embeddings for semantic search...")
        retriever.generate_embeddings()
        
        # Save retriever state
        try:
            retriever.dump(db_cache_dir)
        except Exception:
            pass  # Cache saving is optional
    else:
        # Update config for loaded retriever
        retriever.config = retrieval_config
    
    if verbose:
        print("✅ Database search system ready")
        print()
    
    return retriever


def clear_database_cache(cache_dir: Path) -> None:
    """Clear the database cache, forcing a rebuild on next run.
    
    Args:
        cache_dir: Root cache directory
    """
    db_cache_dir = cache_dir / "database"
    if db_cache_dir.exists():
        import shutil
        shutil.rmtree(db_cache_dir)
        print(f"🗑️  Cleared database cache: {db_cache_dir}")


