from __future__ import annotations

import json
from typing import Any, Dict, Optional
from pydantic import BaseModel # pyright: ignore[reportMissingImports]


class Artifact(BaseModel):
    """
    Artifact is the data carrier between steps.
    It records the provenance (last_step), destination (next_step),
    and strictly separates the output of the previous step from the input of the next step.
    """
    # Step Lineage
    last_step: str = "system"        # The step that just finished
    next_step: Optional[str] = None  # The step this artifact is destined for
    
    # Data Payload
    last_output: Any = None          # The raw output produced by last_step
    next_input: Any = None           # The data to be consumed by next_step
    
    def _dump_data(self, data: Any) -> str:
        if data is None:
            return ""
        if isinstance(data, (dict, list)):
            try:
                return json.dumps(data, ensure_ascii=False)
            except (TypeError, ValueError):
                return str(data)
        return str(data)

    @property
    def last_output_str(self) -> str:
        """
        Safely convert last_output to a string format.
        Useful for logging or history.
        """
        return self._dump_data(self.last_output)

    @property
    def pass_to_next_input(self) -> str:
        """
        Safely convert next_input to a string format.
        Useful for passing to the next step (Agent/Task).
        """
        return self._dump_data(self.next_input)
