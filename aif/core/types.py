from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable, Literal
from pydantic import BaseModel # pyright: ignore[reportMissingImports]
from .artifact import Artifact

RetryValidator = Callable[[Any], tuple[bool, str]]


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
