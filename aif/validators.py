"""
Validators module for AIF framework.

This module contains validation logic for guard callbacks, specifically
handling Agent and Crew-based validators that use LLMs for intelligent validation.
"""

from __future__ import annotations

from typing import Any
import json
from crewai import Crew, Agent, Task  # pyright: ignore[reportMissingImports]


async def validate_with_agent_or_crew(
    guard_callback: Agent | Crew,
    result: Any
) -> tuple[bool, str]:
    """
    Validate result using Agent or Crew-based validator.
    
    This function supports two types of LLM-based validators:
    1. Agent: Uses a single LLM agent to intelligently validate results
    2. Crew: Uses multiple agents for complex validation scenarios
    
    The validator analyzes the result and returns structured feedback in JSON format,
    including whether a retry is needed, the reason, specific issues found, and
    suggestions for improvement.
    
    Args:
        guard_callback: An Agent or Crew instance to perform validation
        result: The result to validate
        
    Returns:
        tuple[bool, str]: (should_retry, reason)
            - should_retry: True if validation failed and retry is needed
            - reason: Detailed explanation including issues and suggestions
            
    Raises:
        json.JSONDecodeError: If validator returns invalid JSON
        Exception: For other validation errors
    """
    try:
        # Prepare validation input
        result_str = str(result)
        
        validation_prompt = f"""
You are a validation expert. Your task is to validate the following result and determine if it needs to be retried.

Result to validate:
{result_str}

Your validation should check:
1. Is the result complete and well-formed?
2. Does it contain all required information?
3. Are there any errors or inconsistencies?
4. Does it meet the expected quality standards?

You MUST respond in the following JSON format:
{{
    "should_retry": true/false,
    "reason": "Detailed explanation of why retry is needed (or empty if validation passed)",
    "issues": ["List of specific issues found (empty if none)"],
    "suggestions": ["Suggestions for improvement (empty if none)"]
}}

IMPORTANT: Return ONLY valid JSON, no additional text.
"""
        
        # Execute validation based on type
        if isinstance(guard_callback, Agent):
            # Single agent validation
            validation_task = Task(
                description=validation_prompt,
                expected_output="JSON object with validation result",
                agent=guard_callback
            )
            
            validation_crew = Crew(
                agents=[guard_callback],
                tasks=[validation_task],
                verbose=False
            )
            
            validation_result = validation_crew.kickoff()
            
        elif isinstance(guard_callback, Crew):
            # Crew validation (already has agents and tasks configured)
            validation_result = guard_callback.kickoff(
                inputs={"validation_input": result_str}
            )
        else:
            return False, ""
        
        # Parse validation result
        validation_str = str(validation_result)
        
        # Extract JSON from result (handle markdown code blocks)
        if "```json" in validation_str:
            json_start = validation_str.find("```json") + 7
            json_end = validation_str.find("```", json_start)
            validation_str = validation_str[json_start:json_end].strip()
        
        validation_data = json.loads(validation_str)
        
        should_retry = validation_data.get("should_retry", False)
        reason = validation_data.get("reason", "")
        issues = validation_data.get("issues", [])
        suggestions = validation_data.get("suggestions", [])
        
        # Build detailed reason message
        if should_retry:
            detailed_reason = reason
            if issues:
                detailed_reason += f"\n\nIssues found:\n" + "\n".join(f"  - {issue}" for issue in issues)
            if suggestions:
                detailed_reason += f"\n\nSuggestions:\n" + "\n".join(f"  - {suggestion}" for suggestion in suggestions)
            return True, detailed_reason
        
        return False, ""
        
    except json.JSONDecodeError as e:
        print(f"   ⚠️  Validator returned invalid JSON: {e}")
        return True, f"Validator error: Invalid JSON response - {str(e)}"
    except Exception as e:
        print(f"   ⚠️  Validation failed with error: {e}")
        return True, f"Validation error: {str(e)}"
