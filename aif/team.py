# aif/team.py
from __future__ import annotations

from typing import List, Optional, Dict, Any
from crewai import Agent, Task, Crew, Process
from .core.types import Artifact, ExecutionStatus, RollbackInfo
from .interactive import InteractiveFlow


class Team:
    """
    Team 是对 CrewAI Crew 的二次封装，支持内部状态、回退和用户交互。
    内部使用 sequential 或 hierarchical 过程，支持循环校验（如 JSON 生成-校验）。
    """

    def __init__(
        self,
        name: str,
        agents: List[Agent],
        tasks: List[Task],
        process: Process = Process.sequential,
        manager_agent: Optional[Agent] = None,
        memory: bool = True,
        verbose: bool = False
    ):
        """
        :param name: Team 名称
        :param agents: 内部 Agent 列表
        :param tasks: 内部 Task 列表（顺序定义流程）
        :param process: 执行过程
        :param manager_agent: 对于 hierarchical 需要
        :param memory: 是否启用内存共享
        :param verbose: 日志详细
        """
        self.name = name
        self.crew = Crew(
            agents=agents,
            tasks=tasks,
            process=process,
            manager_agent=manager_agent,
            memory=memory,
            verbose=verbose
        )

    async def execute(
        self,
        input_artifact: Artifact,
        interactive: InteractiveFlow,
        previous_error: Optional[str] = None
    ) -> tuple[ExecutionStatus, Artifact]:
        """
        执行 Team。
        - 如果需要用户输入，通过 interactive 统一处理
        - 如果失败且需要回退，返回 ROLLBACK_REQUESTED
        """
        inputs: Dict[str, Any] = {"input": input_artifact.data}
        if previous_error:
            inputs["previous_error"] = previous_error  # 注入回退原因

        try:
            # 假设 Crew 支持 async kickoff（CrewAI 最新版支持）
            result = await self.crew.kickoff(inputs=inputs)  # type: ignore

            # 这里简单处理用户输入需求（实际中需在 Task 中抛特定异常或返回标志）
            # 为演示，假设 result 中有特殊标志
            if "NEED_USER_INPUT" in str(result):
                question = result.get("question", "请提供更多信息：")
                user_resp = await interactive.get_user_input(question)
                if user_resp.command == "exit":
                    return ExecutionStatus.EXIT_REQUESTED, Artifact.failure("用户退出")
                if user_resp.command == "rollback":
                    return ExecutionStatus.ROLLBACK_REQUESTED, Artifact.failure("用户要求回退")
                # 递归重试，注入用户输入
                inputs["user_input"] = user_resp.content
                result = await self.crew.kickoff(inputs=inputs)  # type: ignore

            return ExecutionStatus.SUCCESS, Artifact.success(result)

        except Exception as e:
            if "validation_failed" in str(e).lower():
                # 示例：校验失败，需要回退或问用户
                reason = str(e)
                user_resp = await interactive.get_user_input(f"生成失败：{reason}\n是否回退补充信息？(Yes/No)")
                if user_resp.content.lower() in ["yes", "y"]:
                    return ExecutionStatus.ROLLBACK_REQUESTED, Artifact.failure(reason)

            return ExecutionStatus.FAILURE, Artifact.failure(str(e))
