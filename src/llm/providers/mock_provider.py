"""Mock LLM provider for testing and development."""

from __future__ import annotations

from src.llm.interfaces import LLMProvider, LLMRequest, LLMResponse


class MockProvider(LLMProvider):
    """Mock LLM provider that returns predefined responses."""
    
    def __init__(self, config):
        super().__init__(config)
        self._response_templates = {
            "test_case": {
                "id": "auto_generated_test",
                "title": "Generated Test Case",
                "description": "This is a mock generated test case",
                "preconditions": ["System is available"],
                "steps": ["Execute the test", "Verify results"],
                "expected_result": "Test passes",
                "tags": ["auto_generated", "mock"]
            }
        }
    
    def complete(self, request: LLMRequest) -> LLMResponse:
        """Return a mock response based on the request.
        
        Args:
            request: LLM request containing prompt and parameters
            
        Returns:
            Mock LLM response with predefined test case data
        """
        import json
        
        # Simple heuristic to determine response type
        if "test case" in request.prompt.lower() or "json" in request.prompt.lower():
            response_data = self._response_templates["test_case"]
            response_text = json.dumps(response_data, indent=2)
        else:
            response_text = "Mock LLM response: " + request.prompt[:100] + "..."
        
        return LLMResponse(
            text=response_text,
            usage={"prompt_tokens": len(request.prompt), "completion_tokens": len(response_text)},
            model="mock-model",
            finish_reason="stop",
            metadata={"provider": "mock"}
        )
    
    def is_available(self) -> bool:
        """Mock provider is always available."""
        return True
    
    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return "mock"
