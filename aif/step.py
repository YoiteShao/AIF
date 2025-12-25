# aif/step.py
from __future__ import annotations

from typing import Union, Callable, Optional
from crewai import Agent
from .team import Team
from .core.types import Artifact, ExecutionStatus
from .interactive import InteractiveFlow


class Step:
    """
    Step 是 Flow 中的最小执行单元，可以是单个 Agent、Team 或简单函数。
    每个 Step 独立，支持回退时状态重置。
    """

    def __init__(
        self,
        name: str,
        executable: Union[Agent, Team, Callable[[Artifact], Artifact]],
        description: str = ""
    ):
        self.name = name
        self.executable = executable
        self.description = description

    async def execute(
        self,
        input_artifact: Artifact,
        interactive: InteractiveFlow,
        previous_error: Optional[str] = None
    ) -> tuple[ExecutionStatus, Artifact]:
        """
        执行 Step。
        - 对于 Agent：创建临时 Task 执行
        - 对于 Team：调用 Team.execute
        - 对于 Callable：直接调用
        """
        if isinstance(self.executable, Agent):
            # 简单包装为 Task
            from crewai import Task
            task = Task(
                description=f"Execute step {self.name}",
                expected_output="Result",
                agent=self.executable
            )
            result = task.execute(context={"input": input_artifact.data})
            return ExecutionStatus.SUCCESS, Artifact.success(result)

        elif isinstance(self.executable, Team):
            return await self.executable.execute(input_artifact, interactive, previous_error)

        elif callable(self.executable):
            try:
                result_artifact = self.executable(input_artifact)
                return ExecutionStatus.SUCCESS, result_artifact
            except Exception as e:
                return ExecutionStatus.FAILURE, Artifact.failure(str(e))

        raise ValueError("Unsupported executable type")
