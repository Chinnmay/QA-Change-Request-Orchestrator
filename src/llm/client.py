"""LLM client with provider management and configuration."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.llm.interfaces import LLMProvider, LLMRequest, LLMResponse
from config.config_loader import Config, get_llm_config


class LLMClient:
    """Main LLM client that manages different providers."""
    
    def __init__(self, config: Optional[Config] = None, provider_name: Optional[str] = None):
        """Initialize the LLM client.
        
        Args:
            config: Configuration object. If None, loads from default config file.
            provider_name: Specific provider to use. If None, uses default from config.
        """
        self.logger = logging.getLogger(__name__)
        
        if config is None:
            from config.config_loader import load_config
            config = load_config()
        
        self.config = config
        self.provider_name = provider_name or config.default_provider
        self._provider: Optional[LLMProvider] = None
    
    def _get_provider(self) -> LLMProvider:
        """Get or create the LLM provider."""
        if self._provider is None:
            llm_config = get_llm_config(self.config, self.provider_name)
            self._provider = self._create_provider(llm_config)
        
        return self._provider
    
    def _create_provider(self, llm_config: Dict[str, Any]) -> LLMProvider:
        """Create a provider instance based on configuration."""
        # Support dict or SimpleNamespace
        provider_type = (
            llm_config['type'] if isinstance(llm_config, dict) else getattr(llm_config, 'type', '')
        ).lower()
        
        if provider_type == "mock":
            from src.llm.providers.mock_provider import MockProvider
            return MockProvider(llm_config)
        
        elif provider_type == "gemini":
            from src.llm.providers.gemini_provider import GeminiProvider
            return GeminiProvider(llm_config)
        
        elif provider_type == "openai":
            from src.llm.providers.openai_provider import OpenAIProvider
            return OpenAIProvider(llm_config)
        
        else:
            raise ValueError(f"Unsupported LLM provider type: {provider_type}")
    
    def complete(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system_message: Optional[str] = None,
        messages: Optional[list] = None,
        extra_params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate a completion using the configured provider.
        
        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            system_message: System message for the conversation
            messages: List of message dictionaries
            extra_params: Additional parameters for the provider
            **kwargs: Additional keyword arguments
            
        Returns:
            LLMResponse object with the generated text and metadata
        """
        try:
            provider = self._get_provider()
            
            if not provider.is_available():
                raise RuntimeError(f"Provider {self.provider_name} is not available")
            
            request = LLMRequest(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                system_message=system_message,
                messages=messages,
                extra_params=extra_params
            )
            
            self.logger.info(f"Generating completion with provider: {self.provider_name}")
            response = provider.complete(request)
            
            self.logger.info(f"Generated {len(response.text)} characters")
            return response
            
        except Exception as e:
            self.logger.error(f"LLM completion failed: {e}")
            raise
    
    def is_available(self) -> bool:
        """Check if the current provider is available."""
        try:
            provider = self._get_provider()
            return provider.is_available()
        except Exception:
            return False
    
    def get_available_providers(self) -> list[str]:
        """Get list of available providers."""
        available = []
        for provider_name in self.config.providers.keys():
            try:
                llm_config = get_llm_config(self.config, provider_name)
                provider = self._create_provider(llm_config)
                if provider.is_available():
                    available.append(provider_name)
            except Exception:
                continue
        return available
    
    def switch_provider(self, provider_name: str) -> None:
        """Switch to a different provider."""
        if provider_name not in self.config.providers:
            raise ValueError(f"Unknown provider: {provider_name}")
        
        self.provider_name = provider_name
        self._provider = None  # Force recreation
    
    @property
    def current_provider(self) -> str:
        """Get the current provider name."""
        return self.provider_name

    @property
    def current_model(self) -> str:
        """Get the current model name for the active provider, if available."""
        try:
            provider = self._get_provider()
            # Support both dict configs and objects (e.g., SimpleNamespace)
            cfg = getattr(provider, 'config', None)
            if cfg is None:
                return "unknown-model"
            if isinstance(cfg, dict):
                model = cfg.get('model')
            else:
                model = getattr(cfg, 'model', None)
            return str(model) if model else "unknown-model"
        except Exception:
            return "unknown-model"