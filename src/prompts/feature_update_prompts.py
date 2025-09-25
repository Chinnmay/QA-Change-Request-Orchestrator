"""Prompt templates for feature update test case modification."""

import json
from pathlib import Path
from typing import Dict, Any, List
from src.parsers.change_request_parser import ChangeRequest
from src.prompts.template_loader import render_template


class FeatureUpdatePrompts:
    """Prompt templates for updating existing test cases when features change."""
    
    @staticmethod
    def analyze_impact(change: ChangeRequest, related_test_cases: List[Dict[str, Any]]) -> str:
        """
        Generate a prompt for analyzing the impact of feature updates on existing test cases.
        
        Args:
            change: The change request containing update details
            related_test_cases: List of related test cases that might be affected
            
        Returns:
            Formatted prompt string for LLM
        """
        base_prompt = """You are an expert QA engineer analyzing the impact of a feature update on existing test cases.

## Feature Update Details
**Title:** {title}
**Description:** {description}
**Acceptance Criteria:** {acceptance_criteria}

## Related Test Cases
The following test cases are related to this feature and may need updates:

{related_test_cases}

## Task
Analyze each test case and determine what updates are needed based on the feature changes.

## Analysis Requirements
For each test case, consider:
1. **Steps that need modification**: Which test steps are affected by the feature update?
2. **Expected results changes**: How do the expected outcomes change?
3. **New test scenarios**: Are there new scenarios to test?
4. **Obsolete scenarios**: Are any existing scenarios no longer relevant?
5. **Preconditions updates**: Do preconditions need to change?

## Output Format
Return ONLY a valid JSON array with this structure:

```json
[
  {{
    "test_case_id": "original_test_case_id",
    "action": "update|create|deprecate",
    "reason": "Explanation of why this action is needed",
    "updated_test_case": {{
      "id": "updated_id",
      "title": "Updated title",
      "description": "Updated description",
      "preconditions": ["updated", "preconditions"],
      "steps": ["updated", "steps"],
      "expected_result": "Updated expected result",
      "tags": ["updated", "tags"]
    }},
    "confidence": 0.85
  }}
]
```

## Guidelines
- Be conservative: only suggest changes that are clearly necessary
- Maintain test case quality and clarity
- Consider backward compatibility
- Focus on user-facing changes
- Provide clear reasoning for each action

Analyze the impact now:"""

        # Format related test cases
        tc_context = []
        for i, tc in enumerate(related_test_cases[:10], 1):  # Limit to top 10
            tc_context.append(f"**Test Case {i}:**")
            tc_context.append(f"- ID: {tc.get('doc_id', 'N/A')}")
            tc_context.append(f"- Title: {tc.get('title', 'N/A')}")
            tc_context.append(f"- Description: {tc.get('description', 'N/A')}")
            tc_context.append(f"- Steps: {tc.get('steps', [])}")
            tc_context.append(f"- Expected Result: {tc.get('expected_result', 'N/A')}")
            tc_context.append(f"- Tags: {tc.get('tags', [])}")
            tc_context.append("")

        formatted_prompt = base_prompt.format(
            title=change.title,
            description=change.description,
            acceptance_criteria=', '.join(change.acceptance_criteria) if change.acceptance_criteria else "Not specified",
            related_test_cases='\n'.join(tc_context) if tc_context else "No related test cases found."
        )
        
        return formatted_prompt
    
    @staticmethod
    def generate_update_suggestions(change: ChangeRequest, test_case: Dict[str, Any]) -> str:
        """
        Generate specific update suggestions for a single test case.
        
        Args:
            change: The change request
            test_case: The test case to update
            
        Returns:
            Prompt for updating a specific test case
        """
        return f"""You are updating a test case based on a feature change.

## Feature Update
**Title:** {change.title}
**Description:** {change.description}
**Acceptance Criteria:** {', '.join(change.acceptance_criteria) if change.acceptance_criteria else "Not specified"}

## Current Test Case
**ID:** {test_case.get('id', 'N/A')}
**Title:** {test_case.get('title', 'N/A')}
**Description:** {test_case.get('description', 'N/A')}
**Steps:** {test_case.get('steps', [])}
**Expected Result:** {test_case.get('expected_result', 'N/A')}
**Tags:** {test_case.get('tags', [])}

## Task
Update this test case to reflect the feature changes. Consider:
1. Which steps need modification?
2. How do expected results change?
3. Are new preconditions needed?
4. Should tags be updated?

## Output
Return the updated test case in the same JSON format as the original, with only the necessary changes.

Focus on:
- Maintaining test clarity and effectiveness
- Reflecting the actual feature changes
- Preserving test case structure and quality
- Adding appropriate tags (e.g., "updated", "regression")

Provide the updated test case:"""
    
    @staticmethod
    def batch_update_analysis(change: ChangeRequest, test_cases: List[Dict[str, Any]]) -> str:
        """
        Generate a prompt for analyzing multiple test cases for batch updates.
        
        Args:
            change: The change request
            test_cases: List of test cases to analyze
            
        Returns:
            Batch analysis prompt
        """
        return f"""Analyze {len(test_cases)} test cases for updates based on this feature change:

**Feature Update:** {change.title}
**Description:** {change.description}

For each test case, determine:
1. Does it need updates? (Yes/No)
2. What type of updates? (Steps/Expected Results/Preconditions/Tags)
3. Priority level (High/Medium/Low)

Provide a summary analysis focusing on:
- Most critical updates needed
- Common patterns across test cases
- Recommended update strategy
- Risk assessment for each change type

Keep the analysis concise and actionable."""
    
    @staticmethod
    def controlled_update(context_package: Dict[str, Any]) -> str:
        """
        Generate a controlled update prompt following the new guidelines.
        
        Args:
            context_package: Dictionary containing change_request, original_test_case, and iw_context
            
        Returns:
            Formatted prompt for controlled LLM updates with audit trail
        """
        change_request = context_package.get("change_request", {})
        original_tc = context_package.get("original_test_case", {})
        iw_context = context_package.get("iw_context", "")
        
        prompt = """You are an expert QA engineer performing a controlled update of a test case based on a feature change.

## CRITICAL INSTRUCTIONS
- Update ONLY what is necessary to align with the change request
- Keep the existing test case structure intact
- Provide a detailed audit trail of all changes
- Do NOT free-write new tests - only edit in context
- DO NOT add any fields that are not in the original test case (like "tags")
- ONLY use these exact field names: title, type, priority, preconditions, steps

## Change Request Context
**Title:** {title}
**Description:** {description}
**Acceptance Criteria:** {acceptance_criteria}
**Change Type:** {change_type}

## Original Test Case
```json
{original_test_case}
```

## System Context
{iw_context}

## Test Case Schema Requirements
The updated test case MUST conform to the following JSON schema:
```json
{schema}
```

**Required Fields:**
- `title`: Descriptive title (5-300 characters)
- `type`: One of: functional, integration, ui, api, performance, security, regression
- `priority`: One of: P1 - Critical, P2 - High, P3 - Medium, P4 - Low
- `steps`: Array of objects with `step_text` and `step_expected` (minimum 1 step)

**Optional Fields:**
- `preconditions`: Prerequisites or setup required

## Task
Analyze the change request and update the test case to reflect the necessary changes while maintaining its structure and quality. Use Instawork domain knowledge from the system context.

## Update Guidelines
1. **Minimal Changes**: Only modify fields that are directly affected by the change request
2. **Structure Preservation**: Keep the same JSON structure and field names
3. **Quality Maintenance**: Ensure updated content maintains test clarity and effectiveness
4. **Audit Trail**: Document every change with before/after values

## Required Output Format
Return ONLY a valid JSON object with this exact structure. The change_summary MUST include ALL four required fields: feature_impact, changes, reasoning, and assumptions:

```json
{{
  "updated_test_case": {{
    // Complete updated test case JSON with all fields
    // Include ALL original fields, only modify what needs to change
  }},
  "change_summary": {{
    "feature_impact": "Detailed assessment of how the feature update impacts this test case",
    "changes": [
      {{
        "field": "field_name",
        "before": "original_value",
        "after": "updated_value"
      }},
      {{
        "field": "steps[2].step_expected",
        "before": "original_expected_result",
        "after": "updated_expected_result"
      }}
    ],
    "reasoning": "Detailed explanation of why these changes were made based on the feature update",
    "assumptions": [
      "Assumption 1: Description of assumption made during analysis",
      "Assumption 2: Another assumption that influenced the changes"
    ]
  }}
}}
```

## Field Naming for Changes
- Use dot notation for nested fields: "steps[0].step_text", "preconditions[1]"
- For array elements: "steps[3].step_expected"
- For root fields: "title", "preconditions"

## Quality Checks
- Ensure all changes are justified by the change request
- Maintain test case readability and clarity
- Preserve existing test logic where possible
- DO NOT add extra fields like "tags" - the schema only allows: title, type, priority, preconditions, steps

Update the test case now:"""

        # Load schema for formatting requirements
        schema_content = _load_test_case_schema()
        context = {
            "title": change_request.get("title", ""),
            "description": change_request.get("description", ""),
            "acceptance_criteria": ', '.join(change_request.get("acceptance_criteria", [])),
            "change_type": change_request.get("change_type", ""),
            "original_test_case": json.dumps(original_tc, indent=2),
            "iw_context": iw_context or "No additional context available.",
            "schema": schema_content,
        }
        try:
            return render_template("feature_update/controlled_update.md.j2", context)
        except FileNotFoundError:
            return prompt.format(**context)


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
