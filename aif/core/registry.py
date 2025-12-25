# aif/core/registry.py
from __future__ import annotations

from typing import Dict
from team import Team
from step import Step


class AIFRegistry:
    """
    全局注册表，用于注册可复用的 Team 和 Step，便于在 Flow 中引用。
    这有助于开发者模块化设计。
    """
    _teams: Dict[str, Team] = {}
    _steps: Dict[str, Step] = {}

    @classmethod
    def register_team(cls, name: str, team: Team) -> None:
        """注册一个 Team"""
        cls._teams[name] = team

    @classmethod
    def get_team(cls, name: str) -> Team:
        """获取已注册的 Team"""
        if name not in cls._teams:
            raise ValueError(f"Team '{name}' not registered")
        return cls._teams[name]

    @classmethod
    def register_step(cls, name: str, step: Step) -> None:
        """注册一个 Step"""
        cls._steps[name] = step

    @classmethod
    def get_step(cls, name: str) -> Step:
        """获取已注册的 Step"""
        if name not in cls._steps:
            raise ValueError(f"Step '{name}' not registered")
        return cls._steps[name]
