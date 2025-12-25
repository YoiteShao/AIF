# aif/interactive.py
from __future__ import annotations

from typing import Optional, Callable, Awaitable
from .core.types import UserResponse, Artifact, ExecutionStatus


class InteractiveFlow:
    """
    InteractiveFlow 是 AIF 框架的中枢，负责统一处理所有用户交互。
    - 接收初始用户输入
    - 在需要时统一向用户提问（避免并发干扰）
    - 处理用户特殊命令（exit、rollback、retry）
    - 转发内部 Team/Step 的用户输入需求
    """

    def __init__(
        self,
        input_callback: Callable[[str], Awaitable[str]] | Callable[[str], str],
        initial_input: Optional[str] = None
    ):
        """
        :param input_callback: 异步或同步回调函数，用于向用户提问并获取输入
        :param initial_input: 初始用户输入（可选）
        """
        self.input_callback = input_callback
        self.initial_input: Optional[str] = initial_input
        self.current_question: Optional[str] = None

    async def get_user_input(self, question: str) -> UserResponse:
        """
        统一向用户提问，并解析响应。
        支持特殊命令：/exit, /rollback, /retry
        """
        self.current_question = question
        raw_input = await self.input_callback(question) if hasattr(self.input_callback, "__await__") else self.input_callback(question)

        if raw_input.strip().lower().startswith("/exit"):
            return UserResponse(content=raw_input, command="exit")
        if raw_input.strip().lower().startswith("/rollback"):
            return UserResponse(content=raw_input, command="rollback")
        if raw_input.strip().lower().startswith("/retry"):
            return UserResponse(content=raw_input, command="retry")

        return UserResponse(content=raw_input, command=None)

    async def get_initial_input(self) -> str:
        """获取初始输入，如果没有则询问"""
        if self.initial_input:
            return self.initial_input
        return await self.get_user_input("请提供初始输入：").content
