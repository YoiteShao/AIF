# aif/core/registry.py
from __future__ import annotations

from typing import Dict, Any, Union
from crewai import Crew # pyright: ignore[reportMissingImports]
from ..step import Step


class AIFRegistry:
    """
    Global registry for Crews and Steps.
    Supports decorator-based registration to simplify Flow construction.
    """
    _crews: Dict[str, Crew] = {}
    _steps: Dict[str, Step] = {}

    @classmethod
    def register_crew(cls, name: str, crew: Crew) -> None:
        """Register a Crew instance."""
        cls._crews[name] = crew

    @classmethod
    def get_crew(cls, name: str) -> Crew:
        """Get a registered Crew."""
        if name not in cls._crews:
            raise ValueError(f"Crew '{name}' not registered")
        return cls._crews[name]

    @classmethod
    def register_step(cls, name: str, step: Step) -> None:
        """Register a Step instance."""
        if not isinstance(step, Step):
            # Attempt to auto-wrap if it's not a Step but is executable
            raise TypeError(f"Expected Step object, got {type(step)}")
        
        cls._steps[name] = step

    @classmethod
    def get_step(cls, name: str) -> Step:
        """Get a registered Step. Auto-wraps registered Crews if no explicit Step exists."""
        if name in cls._steps:
            return cls._steps[name]
        
        if name in cls._crews:
            # Auto-wrap Crew into a Step
            # We use default settings here. 
            # Users can override by explicitly registering a Step.
            crew = cls._crews[name]
            # Create a default Step wrapper
            # We don't register it back to _steps to allow re-creation or dynamic changes if needed,
            # but caching it might be better for consistency. For now, create on fly.
            return Step(
                name=name,
                step_object=crew,
                require_user_confirmation=True, # Safety default
                max_iterations=3
            )

        raise ValueError(f"Step '{name}' not found in registry (checked steps and crews).")

    @classmethod
    def step(cls, 
             name: str, 
             next_step: Union[str, Any] = None, 
             max_iterations: int = 3, 
             require_user_confirmation: bool = True):
        """
        Decorator to register a function or Crew as a Step.
        
        Usage:
            @AIFRegistry.step(name="search_step", next_step="validate")
            def my_search_logic(artifact):
                ...
        """
        def decorator(obj):
            from ..step import Step  # Deferred import to avoid circular dependencies
            
            # Check if obj is a Crew or Callable
            if not (isinstance(obj, Crew) or callable(obj)):
                raise ValueError(f"Decorated object must be a Crew instance or callable, got {type(obj)}")

            step_instance = Step(
                name=name,
                step_object=obj,
                next_step=next_step,
                max_iterations=max_iterations,
                require_user_confirmation=require_user_confirmation
            )
            cls.register_step(name, step_instance)
            return step_instance
        return decorator
