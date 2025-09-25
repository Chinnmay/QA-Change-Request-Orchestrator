"""Google Gemini API provider."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from src.llm.interfaces import LLMProvider, LLMRequest, LLMResponse
from config.config_loader import get_api_key


class GeminiProvider(LLMProvider):
    """Google Gemini API provider."""
    
    def __init__(self, config):
        super().__init__(config)
        self._client = None
        self._api_key = None
    
    def _get_client(self):
        """Lazy initialization of Gemini client."""
        if self._client is None:
            try:
                import google.generativeai as genai
                
                if self.config.api_key_env:
                    self._api_key = get_api_key(self.config.api_key_env)
                    genai.configure(api_key=self._api_key)
                
                self._client = genai.GenerativeModel(
                    model_name=self.config.model,
                    safety_settings=self._get_safety_settings()
                )
            except ImportError:
                raise ImportError("google-generativeai package not installed. Run: pip install google-generativeai")
            except Exception as e:
                raise RuntimeError(f"Failed to initialize Gemini client: {e}")
        
        return self._client
    
    def _get_safety_settings(self) -> List[Dict[str, Any]]:
        """Convert safety settings to Gemini format."""
        if not self.config.safety_settings:
            return []
        
        safety_map = {
            "harassment": "HARM_CATEGORY_HARASSMENT",
            "hate_speech": "HARM_CATEGORY_HATE_SPEECH", 
            "sexually_explicit": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "dangerous_content": "HARM_CATEGORY_DANGEROUS_CONTENT"
        }
        
        threshold_map = {
            "BLOCK_NONE": "BLOCK_NONE",
            "BLOCK_ONLY_HIGH": "BLOCK_ONLY_HIGH",
            "BLOCK_MEDIUM_AND_ABOVE": "BLOCK_MEDIUM_AND_ABOVE",
            "BLOCK_LOW_AND_ABOVE": "BLOCK_LOW_AND_ABOVE"
        }
        
        # Support dict or SimpleNamespace
        raw_settings = self.config.safety_settings
        if hasattr(raw_settings, 'items'):
            items_iter = raw_settings.items()
        elif hasattr(raw_settings, '__dict__'):
            items_iter = raw_settings.__dict__.items()
        else:
            return []

        settings = []
        for category, threshold in items_iter:
            if category in safety_map and threshold in threshold_map:
                settings.append({
                    "category": safety_map[category],
                    "threshold": threshold_map[threshold]
                })
        
        return settings
    
    def complete(self, request: LLMRequest) -> LLMResponse:
        """Generate completion using Gemini API."""
        try:
            client = self._get_client()
            
            # Prepare the prompt
            full_prompt = request.prompt
            if request.system_message:
                full_prompt = f"System: {request.system_message}\n\nUser: {request.prompt}"
            
            # Generate content
            generation_config = {
                "max_output_tokens": request.max_tokens or self.config.max_tokens,
                "temperature": request.temperature or self.config.temperature,
            }
            
            # Add extra parameters
            if request.extra_params:
                generation_config.update(request.extra_params)
            
            response = client.generate_content(
                full_prompt,
                generation_config=generation_config
            )
            
            # Extract response text
            response_text = response.text if response.text else ""
            
            # Extract usage information if available
            usage = None
            if hasattr(response, 'usage_metadata'):
                usage = {
                    "prompt_tokens": getattr(response.usage_metadata, 'prompt_token_count', 0),
                    "completion_tokens": getattr(response.usage_metadata, 'candidates_token_count', 0),
                    "total_tokens": getattr(response.usage_metadata, 'total_token_count', 0)
                }
            
            return LLMResponse(
                text=response_text,
                usage=usage,
                model=self.config.model,
                finish_reason=getattr(response, 'finish_reason', 'stop'),
                metadata={"provider": "gemini", "safety_ratings": getattr(response, 'safety_ratings', [])}
            )
            
        except Exception as e:
            raise RuntimeError(f"Gemini API error: {e}")
    
    def is_available(self) -> bool:
        """Check if Gemini provider is available."""
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
        return "gemini"
