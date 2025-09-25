from __future__ import annotations

import json
from pathlib import Path
from jsonschema import Draft7Validator


def load_schema(schema_path: Path) -> Draft7Validator:
    """Load and validate a JSON schema from file.
    
    Args:
        schema_path: Path to the JSON schema file
        
    Returns:
        Draft7Validator instance for schema validation
    """
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return Draft7Validator(schema)


def validate_instance(validator: Draft7Validator, instance: dict) -> list[str]:
    """Validate an instance against a JSON schema.
    
    Args:
        validator: Draft7Validator instance
        instance: Dictionary to validate
        
    Returns:
        List of validation error messages (empty if valid)
    """
    errors = [e.message for e in validator.iter_errors(instance)]
    return errors


