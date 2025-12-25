# aif/core/types.py
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable, Literal
from pydantic import BaseModel
from crewai import Agent, Task, Crew
from crewai.flow.flow import Flow as CrewAIFlow
from team import Team


class ExecutionStatus(Enum):
    """执行状态枚举"""
    SUCCESS = "success"
    FAILURE = "failure"
    USER_INPUT_REQUIRED = "user_input_required"
    ROLLBACK_REQUESTED = "rollback_requested"
    EXIT_REQUESTED = "exit_requested"


class Artifact(BaseModel):
    """Artifact: Flow 中传递的核心数据对象，代表每个 Step 或 Team 的输出结果"""
    data: Any  # 主要输出数据，可以是 str、dict、Pydantic Model 等
    metadata: Dict[str, Any] = {}  # 附加元数据，如版本、来源等
    error_reason: Optional[str] = None  # 如果失败，携带错误原因


class UserResponse(BaseModel):
    """用户响应模型"""
    content: str  # 用户输入内容
    command: Optional[Literal["exit", "rollback", "retry"]] = None  # 特殊命令


class RollbackInfo(BaseModel):
    """回退信息"""
    reason: str  # 回退原因
    target_step_index: Optional[int] = None  # 如果指定，回退到特定 step（默认上一级）


# 可执行单元类型
ExecutableUnit = Union[Agent, Team, Callable[[Artifact], Artifact]]
