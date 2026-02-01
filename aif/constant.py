from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable, Literal, TYPE_CHECKING
from pydantic import BaseModel # pyright: ignore[reportMissingImports]

if TYPE_CHECKING:
    from crewai import Agent, Crew # pyright: ignore[reportMissingImports]

# RetryValidator can be:
# 1. A traditional function: (result: Any) -> (should_retry: bool, reason: str)
# 2. An Agent: Will use the agent to validate the result intelligently
# 3. A Crew: Will use the crew to perform complex validation
RetryValidator = Union[
    Callable[[Any], tuple[bool, str]],
    'Agent',
    'Crew'
]


class RollbackInfo(BaseModel):
    """回退信息"""
    reason: str  # 回退原因
    target_step_index: Optional[int] = None  # 如果指定，回退到特定 step（默认上一级）


# StepResult removed as Artifact is now the direct carrier of status and data.

# Constants
HUMAN_ASK_PRINCIPLE = (
    "\n\nIMPORTANT PRINCIPLE: You have access to an 'Ask User' tool. "
    "Prioritize solving the task independently using your available tools and knowledge. "
    "Only use the 'Ask User' tool if you are unable to proceed due to missing critical information "
    "or persistent errors. Avoid asking the user for confirmation unless strictly necessary."
)

# Feedback and Validation Context Templates
FEEDBACK_CONTEXT_HEADER = "=== USER FEEDBACK ==="
FEEDBACK_CONTEXT_EXPLANATION = (
    "(User feedback represents additional requirements or clarifications from the human user)"
)

VALIDATION_CONTEXT_HEADER = "=== VALIDATION ERRORS ==="
VALIDATION_CONTEXT_EXPLANATION = (
    "(Validation errors are system-level checks that failed. These are automated quality gates\n"
    "that verify your output meets specific criteria, constraints, or format requirements.)"
)

CUMULATIVE_CONTEXT_INSTRUCTIONS = (
    "\n=== INSTRUCTIONS ===\n"
    "Please fulfill ALL requirements above:\n"
    "1. Complete the original request\n"
)

CUMULATIVE_CONTEXT_FEEDBACK_INSTRUCTION = "2. Address all user feedback (additional requirements from human)\n"
CUMULATIVE_CONTEXT_VALIDATION_INSTRUCTION = "3. Fix all validation errors (system quality checks that failed)\n"
