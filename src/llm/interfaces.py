"""LLM provider interfaces and abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    text: str
    usage: Optional[Dict[str, Any]] = None
    model: Optional[str] = None
    finish_reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class LLMRequest:
    """Request to an LLM provider."""
    prompt: str
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    system_message: Optional[str] = None
    messages: Optional[List[Dict[str, str]]] = None
    extra_params: Optional[Dict[str, Any]] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, config: Any):
        """Initialize the provider with configuration."""
        self.config = config
    
    @abstractmethod
    def complete(self, request: LLMRequest) -> LLMResponse:
        """Generate a completion for the given request."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available and properly configured."""
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the name of this provider."""
        pass
