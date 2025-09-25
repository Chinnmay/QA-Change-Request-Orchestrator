"""Prompt templates for new feature test case generation."""

import json
from pathlib import Path
from typing import Dict, Any
from src.parsers.change_request_parser import ChangeRequest
from src.prompts.template_loader import render_template


class NewFeaturePrompts:
    """Prompt templates for generating test cases for new features."""
    
    @staticmethod

    @staticmethod
    def controlled_generation_variant(context_package: Dict[str, Any], variant: str) -> str:
        """Variant-specific prompt (positive | negative | edge) with strict schema output."""
        change_request = context_package.get("change_request", {})
        iw_context = context_package.get("iw_context", "")
        test_number = context_package.get("test_number", 1)

        schema_content = _load_test_case_schema()

        variant_instruction_map = {
            "positive": "Design a happy-path test validating the new behaviour under normal conditions.",
            "negative": "Design a negative test verifying correct handling of invalid inputs or denied actions without crashes.",
            "edge": "Design an edge-case test focusing on boundaries, race conditions, or rare configurations relevant to this change.",
        }
        variant_note = variant_instruction_map.get(variant, "Design a relevant test for the specified scenario.")

        context = {
            "title": change_request.get("title", ""),
            "description": change_request.get("description", ""),
            "acceptance_criteria": ', '.join(change_request.get("acceptance_criteria", [])),
            "change_type": change_request.get("change_type", ""),
            "iw_context": iw_context or "No additional context available.",
            "schema": schema_content,
            "test_number": test_number,
            "variant": variant,
            "variant_note": variant_note,
            "variant_upper": variant.upper(),
        }

        return render_template("new_feature/controlled_generation_variant.md.j2", context)


def _load_test_case_schema() -> str:
    """Load the test case schema for formatting requirements."""
    try:
        schema_path = Path("schema/test_case.schema.json")
        if schema_path.exists():
            with open(schema_path, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception:
        pass
    
    # Fallback schema if file not found
    return """{
  "type": "object",
  "required": ["title", "type", "priority", "steps"],
  "properties": {
    "title": {"type": "string", "minLength": 5, "maxLength": 300},
    "type": {"type": "string", "enum": ["functional", "integration", "ui", "api", "performance", "security", "regression"]},
    "priority": {"type": "string", "enum": ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"]},
    "preconditions": {"type": "string"},
    "steps": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["step_text", "step_expected"],
        "properties": {
          "step_text": {"type": "string", "minLength": 5},
          "step_expected": {"type": "string", "minLength": 3}
        }
      }
    }
  }
}"""
