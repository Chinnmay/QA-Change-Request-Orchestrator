"""Prompt templates for bug fix test case analysis and generation."""

import json
from pathlib import Path
from typing import Dict, Any, List
from src.parsers.change_request_parser import ChangeRequest
from src.prompts.template_loader import render_template


class BugFixPrompts:
    """Prompt templates for analyzing and updating test cases for bug fixes."""
    
    @staticmethod
    def analyze_bug_impact(change: ChangeRequest, related_test_cases: List[Dict[str, Any]]) -> str:
        """
        Generate a prompt for analyzing the impact of a bug fix on existing test cases.
        
        Args:
            change: The change request containing bug fix details
            related_test_cases: List of related test cases that might be affected
            
        Returns:
            Formatted prompt string for LLM
        """
        base_prompt = """You are an expert QA engineer analyzing the impact of a bug fix on existing test cases.

## Bug Fix Details
**Title:** {title}
**Description:** {description}
**Bug Type:** {bug_type}
**Severity:** {severity}

## Related Test Cases
The following test cases are related to this bug fix and may need updates:

{related_test_cases}

## Task
Analyze each test case to determine what updates are needed to ensure the bug fix is properly tested.

## Analysis Requirements
For each test case, consider:
1. **Regression Testing**: Does this test case need to verify the bug fix?
2. **New Test Scenarios**: Are there new scenarios to test the fix?
3. **Existing Test Updates**: Do existing tests need modification to catch this bug?
4. **Edge Cases**: What edge cases should be tested?
5. **Integration Points**: Are there integration points that need testing?

## Output Format
Return ONLY a valid JSON array with this structure:

```json
[
  {{
    "test_case_id": "original_test_case_id",
    "action": "update|create|add_regression",
    "reason": "Explanation of why this action is needed",
    "updated_test_case": {{
      "id": "updated_id",
      "title": "Updated title",
      "description": "Updated description",
      "preconditions": ["updated", "preconditions"],
      "steps": ["updated", "steps", "Verify bug fix: {title}"],
      "expected_result": "Updated expected result",
      "tags": ["regression", "bug_fix", "other_tags"]
    }},
    "confidence": 0.90
  }}
]
```

## Guidelines
- Focus on regression testing to prevent the bug from reoccurring
- Add specific verification steps for the bug fix
- Consider both positive and negative test scenarios
- Include appropriate tags (regression, bug_fix, etc.)
- Ensure test cases are specific and actionable
- Consider the bug's impact on user workflows

Analyze the bug fix impact now:"""

        # Format related test cases
        tc_context = []
        for i, tc in enumerate(related_test_cases[:8], 1):  # Limit to top 8 for bug fixes
            tc_context.append(f"**Test Case {i}:**")
            tc_context.append(f"- ID: {tc.get('doc_id', 'N/A')}")
            tc_context.append(f"- Title: {tc.get('title', 'N/A')}")
            tc_context.append(f"- Description: {tc.get('description', 'N/A')}")
            tc_context.append(f"- Steps: {tc.get('steps', [])}")
            tc_context.append(f"- Expected Result: {tc.get('expected_result', 'N/A')}")
            tc_context.append(f"- Tags: {tc.get('tags', [])}")
            tc_context.append("")

        # Extract bug type and severity from description (simple heuristic)
        bug_type = "General"  # Default
        severity = "Medium"   # Default
        
        description_lower = change.description.lower()
        if any(word in description_lower for word in ["critical", "severe", "crash", "data loss"]):
            severity = "High"
        elif any(word in description_lower for word in ["minor", "cosmetic", "ui"]):
            severity = "Low"
            
        if any(word in description_lower for word in ["authentication", "login", "security"]):
            bug_type = "Security"
        elif any(word in description_lower for word in ["performance", "slow", "timeout"]):
            bug_type = "Performance"
        elif any(word in description_lower for word in ["ui", "interface", "display"]):
            bug_type = "UI/UX"

        formatted_prompt = base_prompt.format(
            title=change.title,
            description=change.description,
            bug_type=bug_type,
            severity=severity,
            related_test_cases='\n'.join(tc_context) if tc_context else "No related test cases found."
        )
        
        return formatted_prompt
    
    @staticmethod
    def generate_regression_tests(change: ChangeRequest, bug_scenarios: List[str]) -> str:
        """
        Generate a prompt for creating specific regression tests for a bug fix.
        
        Args:
            change: The change request
            bug_scenarios: List of scenarios that were affected by the bug
            
        Returns:
            Regression test generation prompt
        """
        return f"""Create regression tests to ensure this bug fix is properly validated.

## Bug Fix
**Title:** {change.title}
**Description:** {change.description}

## Bug Scenarios
{chr(10).join(f"- {scenario}" for scenario in bug_scenarios)}

## Task
Generate regression test cases that specifically verify:
1. The bug is fixed
2. The fix doesn't introduce new issues
3. Related functionality still works
4. Edge cases are covered

## Output Format
Return a JSON array of regression test cases:

```json
[
  {{
    "id": "regression_bug_fix_id",
    "title": "Regression: Verify bug fix for [specific issue]",
    "description": "Test case to verify the bug fix works correctly",
    "preconditions": ["list", "of", "preconditions"],
    "steps": [
      "Step to reproduce the original bug scenario",
      "Verify the bug is now fixed",
      "Verify no regression in related functionality"
    ],
    "expected_result": "Bug is fixed and no regression occurs",
    "tags": ["regression", "bug_fix", "critical"]
  }}
]
```

## Guidelines
- Focus on the specific bug scenario
- Include verification that the fix works
- Test related functionality for regressions
- Use clear, actionable steps
- Mark as high priority if the bug was critical

Generate regression tests now:"""
    
    @staticmethod
    def analyze_test_coverage(change: ChangeRequest, existing_tests: List[Dict[str, Any]]) -> str:
        """
        Generate a prompt for analyzing test coverage for a bug fix.
        
        Args:
            change: The change request
            existing_tests: List of existing test cases
            
        Returns:
            Test coverage analysis prompt
        """
        return f"""Analyze test coverage for this bug fix to identify gaps.

## Bug Fix
**Title:** {change.title}
**Description:** {change.description}

## Existing Test Cases
{len(existing_tests)} related test cases found.

## Analysis Task
Determine:
1. **Coverage Gaps**: What scenarios are not covered by existing tests?
2. **Test Quality**: Are existing tests sufficient to catch this type of bug?
3. **Missing Scenarios**: What additional test scenarios are needed?
4. **Priority Areas**: Which areas need the most attention?

## Output
Provide a coverage analysis with:
- Coverage assessment (Good/Fair/Poor)
- Identified gaps
- Recommended additional tests
- Priority recommendations

Focus on ensuring this type of bug cannot occur again without being caught by tests."""
    
    @staticmethod
    def create_bug_reproduction_test(change: ChangeRequest) -> str:
        """
        Generate a prompt for creating a test case that reproduces the original bug.
        
        Args:
            change: The change request
            
        Returns:
            Bug reproduction test prompt
        """
        return f"""Create a test case that reproduces the original bug (before the fix).

## Bug Details
**Title:** {change.title}
**Description:** {change.description}

## Task
Create a test case that:
1. Reproduces the original bug scenario
2. Shows the expected (buggy) behavior
3. Can be used to verify the fix works

## Output Format
```json
{{
  "id": "bug_reproduction_id",
  "title": "Reproduce: [bug description]",
  "description": "Test case to reproduce the original bug scenario",
  "preconditions": ["list", "of", "preconditions"],
  "steps": [
    "Steps to reproduce the bug",
    "Observe the buggy behavior"
  ],
  "expected_result": "Original buggy behavior (before fix)",
  "tags": ["bug_reproduction", "regression", "before_fix"]
}}
```

## Guidelines
- Focus on the exact steps that trigger the bug
- Be specific about the buggy behavior
- Include all necessary preconditions
- Make it easy to reproduce consistently

Create the bug reproduction test case:"""
    
    @staticmethod
    def controlled_analysis(context_package: Dict[str, Any]) -> str:
        """
        Generate a controlled bug fix analysis prompt following the new guidelines.
        
        Args:
            context_package: Dictionary containing change_request, original_test_case, and iw_context
            
        Returns:
            Formatted prompt for controlled LLM bug fix analysis with audit trail
        """
        change_request = context_package.get("change_request", {})
        original_tc = context_package.get("original_test_case", {})
        iw_context = context_package.get("iw_context", "")
        
        prompt = """You are an expert QA engineer performing a controlled analysis of a test case for a bug fix.

## CRITICAL INSTRUCTIONS
- Analyze the bug fix impact on the existing test case
- Update ONLY what is necessary to address the bug fix
- Keep the existing test case structure intact
- Provide a detailed audit trail of all changes
- Consider regression testing requirements

## Bug Fix Context
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
Analyze the bug fix and determine what updates are needed for this test case to:
1. Address the bug fix requirements
2. Add appropriate regression tests
3. Ensure the test case remains effective
4. Maintain test case quality and clarity
5. Use Instawork domain knowledge from the system context

## Analysis Guidelines
1. **Bug Impact Assessment**: Determine how this bug fix affects the test case
2. **Minimal Changes**: Only modify fields that are directly affected by the bug fix
3. **Structure Preservation**: Keep the same JSON structure and field names
4. **Regression Testing**: Add regression test steps if needed
5. **Audit Trail**: Document every change with before/after values

## Required Output Format
Return ONLY a valid JSON object with this exact structure:

```json
{{
  "updated_test_case": {{
    // Complete updated test case JSON with all fields
    // Include ALL original fields, only modify what needs to change
  }},
  "analysis_summary": {{
    "method": "LLM-controlled bug fix analysis",
    "bug_impact": "Detailed assessment of how the bug fix impacts this test case",
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
    "regression_tests": [
      "Regression test 1: Description of what to verify",
      "Regression test 2: Additional verification needed"
    ],
    "reasoning": "Detailed explanation of why these changes were made based on the bug fix",
    "assumptions": [
      "Assumption 1: Description of assumption made during analysis",
      "Assumption 2: Another assumption that influenced the changes"
    ]
  }}
}}
```

## Field Naming for Changes
- Use dot notation for nested fields: "steps[0].step_text", "preconditions[1]"
- For array elements: "tags[2]", "steps[3].step_expected"
- For root fields: "title", "description", "expected_result"

## Quality Checks
- Ensure all changes are justified by the bug fix
- Maintain test case readability and clarity
- Preserve existing test logic where possible
- Add appropriate regression test steps
- Consider edge cases and error scenarios

Analyze the bug fix impact now:"""

        # Load schema and render via template
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
            return render_template("bug_fix/controlled_analysis.md.j2", context)
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
