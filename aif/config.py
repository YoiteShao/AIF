from __future__ import annotations

import os
from typing import Optional


class AIFConfig:
    """
    Global configuration for AIF framework.
    Manages debug settings and other framework-wide options.
    """
    
    _instance: Optional['AIFConfig'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Debug settings
        self.debug_artifact_transmission = self._get_env_bool('AIF_DEBUG_ARTIFACT', False)
        self.debug_step_execution = self._get_env_bool('AIF_DEBUG_STEP', False)
        
        self._initialized = True
    
    @staticmethod
    def _get_env_bool(key: str, default: bool = False) -> bool:
        """Get boolean value from environment variable."""
        value = os.environ.get(key, '').lower()
        if value in ('true', '1', 'yes', 'on'):
            return True
        elif value in ('false', '0', 'no', 'off'):
            return False
        return default
    
    def enable_debug_artifact(self, enabled: bool = True):
        """Enable or disable artifact transmission debug logging."""
        self.debug_artifact_transmission = enabled
    
    def enable_debug_step(self, enabled: bool = True):
        """Enable or disable step execution debug logging."""
        self.debug_step_execution = enabled
    
    def is_debug_artifact_enabled(self) -> bool:
        """Check if artifact debug is enabled."""
        return self.debug_artifact_transmission
    
    def is_debug_step_enabled(self) -> bool:
        """Check if step debug is enabled."""
        return self.debug_step_execution


# Global config instance
aif_config = AIFConfig()
