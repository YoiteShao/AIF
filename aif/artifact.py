from __future__ import annotations

import json
from typing import Any, Dict, Optional, Callable
from pydantic import BaseModel # pyright: ignore[reportMissingImports]


def _debug_log_artifact(artifact: 'Artifact', context: str = ""):
    """
    Internal helper to log artifact transmission details when debug is enabled.
    """
    from .config import aif_config
    
    if not aif_config.is_debug_artifact_enabled():
        return
    print("      ","-"*15)
    print(f"      🔍 [Debug] Artifact {context} start")
    print(f"      Last Step: {artifact.last_step} → Next Step: {artifact.next_step}")
    print(f"      Pass Data: 【{artifact.pass_data}】")
    print("      ","-"*15,)


class Artifact(BaseModel):
    """
    Artifact is the data carrier between steps.
    It records the provenance (last_step), destination (next_step),
    and carries the data payload between steps.
    """
    # Step Lineage
    last_step: str = "system"        # The step that just finished
    next_step: Optional[str] = None  # The step this artifact is destined for
    
    # Data Payload - now supports str, dict, or list
    pass_data: Any = ""              # The data to be passed between steps (str, dict, or list)
    
    @staticmethod
    def dump_data_to_str(data: Any) -> str:
        """Convert any data type to string representation for display purposes."""
        if data is None:
            return ""
        if isinstance(data, str):
            return data
        if isinstance(data, (dict, list)):
            try:
                return json.dumps(data, ensure_ascii=False, indent=2)
            except (TypeError, ValueError):
                return str(data)
        return str(data)
    
    def get_data(self, key: Optional[str] = None) -> Any:
        """
        Get the data payload, preserving original data types.
        
        Args:
            key: Optional key to extract from pass_data if it's a dict
            
        Returns:
            The data (preserving original type) or specific key value
        """
        if key and isinstance(self.pass_data, dict):
            return self.pass_data.get(key)
        return self.pass_data
    
    def get_data_as_str(self) -> str:
        """
        Get the data payload as a string representation.
        Useful when you need string format for LLM input.
        
        Returns:
            String representation of pass_data
        """
        return self.dump_data_to_str(self.pass_data)
