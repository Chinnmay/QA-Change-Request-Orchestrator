"""OpenAI API provider."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.llm.interfaces import LLMProvider, LLMRequest, LLMResponse
from config.config_loader import get_api_key


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""
    
    def __init__(self, config):
        super().__init__(config)
        self._client = None
        self._api_key = None
    
    def _get_client(self):
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            try:
                import openai
                
                if self.config.api_key_env:
                    self._api_key = get_api_key(self.config.api_key_env)
                    openai.api_key = self._api_key
                
                self._client = openai
            except ImportError:
                raise ImportError("openai package not installed. Run: pip install openai")
            except Exception as e:
                raise RuntimeError(f"Failed to initialize OpenAI client: {e}")
        
        return self._client
    
    def complete(self, request: LLMRequest) -> LLMResponse:
        """Generate completion using OpenAI API."""
        try:
            client = self._get_client()
            
            # Prepare messages
            messages = []
            if request.system_message:
                messages.append({"role": "system", "content": request.system_message})
            
            if request.messages:
                messages.extend(request.messages)
            else:
                messages.append({"role": "user", "content": request.prompt})
            
            # Generate completion
            response = client.ChatCompletion.create(
                model=self.config.model,
                messages=messages,
                max_tokens=request.max_tokens or self.config.max_tokens,
                temperature=request.temperature or self.config.temperature,
                **(request.extra_params or {})
            )
            
            # Extract response
            choice = response.choices[0]
            response_text = choice.message.content
            
            # Extract usage information
            usage = None
            if hasattr(response, 'usage'):
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            
            return LLMResponse(
                text=response_text,
                usage=usage,
                model=self.config.model,
                finish_reason=choice.finish_reason,
                metadata={"provider": "openai"}
            )
            
        except Exception as e:
            raise RuntimeError(f"OpenAI API error: {e}")
    
    def is_available(self) -> bool:
        """Check if OpenAI provider is available."""
        try:
            if self.config.api_key_env:
                get_api_key(self.config.api_key_env)
            self._get_client()
            return True
        except Exception:
            return False
    
    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return "openai"
