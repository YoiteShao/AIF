# aif/flow.py
from __future__ import annotations

from typing import List, Optional
from .step import Step
from .core.types import Artifact, ExecutionStatus
from .interactive import InteractiveFlow


class AIFFlow:
    """
    AIF 主 Flow 类，管理多个 Step 的顺序执行、状态快照、回退。
    每个 Step 执行成功后保存快照，支持回退到任意前序 Step。
    """

    def __init__(
        self,
        steps: List[Step],
        interactive: InteractiveFlow
    ):
        self.steps = steps
        self.interactive = interactive
        self.history: List[Artifact] = []  # 每个 Step 成功后的输出快照
        self.current_step_index: int = -1

    async def run(self) -> Artifact:
        """
        运行整个 Flow。
        - 从当前 step 开始执行
        - 支持回退、用户交互、退出
        """
        initial_input = await self.interactive.get_initial_input()
        current_artifact = Artifact.success(initial_input)

        while self.current_step_index < len(self.steps) - 1:
            self.current_step_index += 1
            step = self.steps[self.current_step_index]

            previous_error = None
            if len(self.history) > self.current_step_index:
                # 回退后重置
                previous_error = self.history[self.current_step_index].error_reason

            status, output_artifact = await step.execute(
                current_artifact, self.interactive, previous_error
            )

            if status == ExecutionStatus.SUCCESS:
                self.history.append(output_artifact)
                current_artifact = output_artifact
                continue

            elif status == ExecutionStatus.USER_INPUT_REQUIRED:
                # 处理用户输入后重试当前 step
                self.current_step_index -= 1  # 临时回退以重试
                continue

            elif status == ExecutionStatus.ROLLBACK_REQUESTED:
                if self.current_step_index == 0:
                    raise ValueError("无法回退到更前一步")
                # 回退到上一步，重置当前
                self.current_step_index -= 2  # 执行上一步时会 +1
                current_artifact = self.history[self.current_step_index] if self.current_step_index >= 0 else Artifact.success(
                    initial_input)
                continue

            elif status == ExecutionStatus.EXIT_REQUESTED:
                return Artifact.failure("用户退出 Flow")

            else:
                # 失败处理
                raise RuntimeError(
                    f"Step {step.name} 失败: {output_artifact.error_reason}")

        return current_artifact  # 最终输出
