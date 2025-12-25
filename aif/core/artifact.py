# aif/core/artifact.py
from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel


class Artifact(BaseModel):
    """
    Artifact 是 AIF 框架中 Step 和 Team 之间传递的核心数据结构。
    它封装了输出数据、元数据以及可能的错误信息，确保状态传递的可控性。
    """
    data: Any  # 主要输出数据（str, dict, Pydantic 等）
    metadata: Dict[str, Any] = {}  # 元数据，如 timestamp、source 等
    error_reason: Optional[str] = None  # 失败时的错误原因，用于回退时传递

    def success(self, data: Any, metadata: Optional[Dict[str, Any]] = None) -> Artifact:
        """创建成功 Artifact"""
        return Artifact(data=data, metadata=metadata or {}, error_reason=None)

    def failure(self, reason: str, data: Any = None) -> Artifact:
        """创建失败 Artifact"""
        return Artifact(data=data, metadata={}, error_reason=reason)
