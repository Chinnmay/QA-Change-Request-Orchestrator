"""Configuration loader for LLM providers and system settings."""

from __future__ import annotations

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from types import SimpleNamespace
from dataclasses import dataclass


@dataclass
class Config:
    """Simplified configuration container."""
    default_provider: str
    providers: Dict[str, Dict[str, Any]]
    global_settings: Dict[str, Any]
    system: Dict[str, Any]


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load configuration from YAML file."""
    # Load .env automatically if present
    try:
        from dotenv import load_dotenv
        # Prefer project root .env
        project_root = Path(__file__).resolve().parents[1]
        env_path = project_root / '.env'
        if env_path.exists():
            load_dotenv(env_path)
        else:
            # Fallback: load from current working directory
            load_dotenv()
    except Exception:
        # dotenv is optional; ignore if not installed
        pass
    if config_path is None:
        config_path = Path(__file__).parent / "llm_config.yaml"
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    # Apply defaults and return configuration
    return Config(
        default_provider=data.get('default_provider', 'mock'),
        providers=data.get('providers', {}),
        global_settings=data.get('global', {
            'timeout': 30,
            'retry_attempts': 3,
            'retry_delay': 1.0,
            'log_level': 'INFO'
        }),
        system=data.get('system', {
            'test_cases_dir': 'test_cases',
            'schema_path': 'schema/test_case.schema.json',
            'reports_dir': 'reports',
            'cache_dir': '.cache',
            'sample_change_requests_dir': 'sample_change_requests',
            'default_retriever': 'hybrid',
            'top_k': {'new_feature': 5, 'feature_update': 10, 'bug_fix': 8},
            'database': {},
            'reports': {}
        })
    )


def get_llm_config(config: Config, provider_name: Optional[str] = None) -> Dict[str, Any]:
    """Get LLM configuration for a specific provider.
    
    Args:
        config: Configuration object
        provider_name: Name of the provider (defaults to config.default_provider)
        
    Returns:
        Dictionary containing provider configuration
        
    Raises:
        ValueError: If provider is not found in configuration
    """
    provider = provider_name or config.default_provider
    
    if provider not in config.providers:
        raise ValueError(f"Unknown LLM provider: {provider}")
    
    def _to_namespace(obj: Any) -> Any:
        """Recursively convert dicts to SimpleNamespace for attribute access."""
        if isinstance(obj, dict):
            return SimpleNamespace(**{k: _to_namespace(v) for k, v in obj.items()})
        if isinstance(obj, list):
            return [
                _to_namespace(item) for item in obj
            ]
        return obj

    return _to_namespace(config.providers[provider])


def get_api_key(api_key_env: str) -> str:
    """Get API key from environment variable.
    
    Args:
        api_key_env: Environment variable name containing the API key
        
    Returns:
        API key value
        
    Raises:
        ValueError: If API key is not found in environment
    """
    api_key = os.getenv(api_key_env)
    if not api_key:
        raise ValueError(f"API key not found in environment variable: {api_key_env}")
    return api_key


def get_pipeline_top_k(config: Config, pipeline_name: str) -> int:
    """Get top_k setting for a specific pipeline.
    
    Args:
        config: Configuration object
        pipeline_name: Name of the pipeline (e.g., 'bug_fix', 'feature_update', 'new_feature')
        
    Returns:
        Number of top results to retrieve (defaults to 5 if not configured)
    """
    return config.system.get('top_k', {}).get(pipeline_name, 5)


def get_retriever_config(config: Config, retriever_name: str) -> Dict[str, Any]:
    """Get configuration for a specific retriever.
    
    Args:
        config: Configuration object
        retriever_name: Name of the retriever (e.g., 'hybrid')
        
    Returns:
        Dictionary containing retriever configuration (empty dict if not found)
    """
    if retriever_name == "hybrid":
        return config.system.get('database', {})
    return {}


def get_report_config(config: Config) -> Dict[str, Any]:
    """Get report configuration.
    
    Args:
        config: Configuration object
        
    Returns:
        Dictionary containing report configuration
    """
    return config.system.get('reports', {})
