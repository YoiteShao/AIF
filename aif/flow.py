from __future__ import annotations

from typing import List, Optional, Dict, Callable, Union, Any
from crewai import Crew # pyright: ignore[reportMissingImports]
from aif.step import Step, NextStep
from aif.artifact import Artifact, _debug_log_artifact
from aif.constant import RetryValidator
from aif.interactive import InteractionManager, UserExitException, RollbackException

class AIFFlow:
    """
    AIF Main Flow class.
    Manages graph-based execution of Steps, state snapshots, and rollback logic.
    """

    def __init__(
        self,
        interactive: InteractionManager
    ):
        self.interactive = interactive
        self.history: List[Artifact] = []  # Stores output of each successful step
        self._rollback_reason: Optional[str] = None
        
        self.step_map: Dict[str, Step] = {}
        self._steps_sequence: List[str] = [] # Track order for implicit next_step
        self.start_step: Optional[str] = None

    def add_step_from_crew(
        self,
        name: str,
        step_object: Union[Crew, Callable],
        output_processor: Optional[Callable[[Any], tuple[Any, Any]]] = None,
        guard_callback: Optional[RetryValidator] = None,
        next_step: NextStep = None,
        require_user_confirmation: bool = True
    ) -> Step:
        """
        Register a Step (wrapping a Crew or Callable) in this Flow.
        Unified registration method:
        - Creates a Step object with specified parameters.
        - Adds it to the Flow sequence.
        - Implicitly sets the first added step as the start_step if not set.
        
        Args:
            name: Name of the step
            step_object: Crew or Callable to execute
            output_processor: Optional function to separate step output from human display
            guard_callback: Optional validation callback
            next_step: Next step name or callable to determine next step
            require_user_confirmation: Whether to require user confirmation
        """
        step = Step(
            name=name,
            step_object=step_object,
            output_processor=output_processor,
            should_retry_guard_callback=guard_callback,
            next_step=next_step,
            require_user_confirmation=require_user_confirmation
        )
        self._add_step_internal(step)
        return step

    def add_step(self, step: Step) -> Step:
        """
        Add an existing Step object directly to this Flow.
        
        Args:
            step: An existing Step instance to add to the flow
            
        Returns:
            The added Step object
        """
        if not isinstance(step, Step):
            raise TypeError(f"Expected Step object, got {type(step)}")
        
        self._add_step_internal(step)
        return step

    def _add_step_internal(self, step: Step):
        if step.name in self.step_map:
             raise ValueError(f"Step '{step.name}' already exists in Flow.")
        self.step_map[step.name] = step
        self._steps_sequence.append(step.name)
        
        # If this is the first step added and no start_step defined, set it
        if self.start_step is None:
            self.start_step = step.name

    def inspect(self):
        """View the complete step flow structure."""
        print("\n📋 [Flow Configuration]")
        print(f"   Start Step: {self.start_step}")
        print(f"   Steps Sequence:")
        for i, name in enumerate(self._steps_sequence):
            step = self.step_map[name]
            next_s = step.next_step
            if next_s is None and i + 1 < len(self._steps_sequence):
                next_s = f"{self._steps_sequence[i+1]} (Implicit)"
            elif next_s is None:
                next_s = "End"
            
            print(f"      {i+1}. [{name}] → {next_s}")
            print(f"         Confirm: {step.require_user_confirmation}")
        print()

    async def run(self, initial_input: Optional[str] = None) -> Artifact:
        """
        Execute the Flow.
        Iterates through steps based on graph logic. Handles Rollback/Exit requests.
        
        Args:
            initial_input: Optional initial input to start the flow with.
                          Priority: method parameter > InteractionManager.initial_input > interactive prompt
        """
        # Priority: method parameter > InteractionManager preset > interactive prompt
        if initial_input is not None:
            # Use the provided parameter
            actual_initial_input = initial_input
        elif self.interactive.initial_input is not None:
            # Use the preset value in InteractionManager
            actual_initial_input = self.interactive.initial_input
        else:
            # Ask the user interactively
            actual_initial_input = await self.interactive.get_initial_input()
        
        current_artifact = Artifact(
            last_step="User Input",
            next_step=self.start_step,
            pass_data=actual_initial_input
        )
        
        current_step_name = self.start_step
        if not current_step_name:
             raise ValueError("Flow cannot start: No start_step defined and no steps provided.")

        while current_step_name:
            step = self._get_step(current_step_name)
            

            print(f"\n📋 [Step: {step.name}]")

            current_artifact.next_step = step.name

            try:
                # Debug log: Input artifact before step execution
                _debug_log_artifact(current_artifact, f"[Before {step.name}]")
                
                # Execute step (handles retry loops internally)
                output_artifact = await step.execute(
                    input_artifact=current_artifact, interactive=self.interactive
                )
                
                # Debug log: Output artifact after step execution
                _debug_log_artifact(output_artifact, f"[After {step.name}]")
                
                self.history.append(output_artifact)
                current_artifact = output_artifact
                
                # Determine Next Step
                next_step_val = step.next_step
                current_step_name = None
                
                if next_step_val is not None:
                    # Explicit next_step takes precedence
                    if isinstance(next_step_val, str):
                        current_step_name = next_step_val
                    elif isinstance(next_step_val, Step):
                        # Step object: use its name
                        current_step_name = next_step_val.name
                    elif callable(next_step_val):
                        # Callable: execute it to get step name (could return str or Step)
                        result = next_step_val(output_artifact)
                        if isinstance(result, Step):
                            current_step_name = result.name
                        else:
                            current_step_name = result
                    else:
                        print(f"   ⚠️  Invalid next_step type in step {step.name}. Ending flow.")
                else:
                    # Implicit next step from sequence
                    try:
                        # Find index of current step in the sequence
                        current_idx = self._steps_sequence.index(step.name)
                        if current_idx + 1 < len(self._steps_sequence):
                            current_step_name = self._steps_sequence[current_idx + 1]
                    except ValueError:
                         # Current step not in sequence list (shouldn't happen if initialized correctly)
                         pass

            except UserExitException:
                print("\n⚠️  Flow exited by user")
                return current_artifact

            except RollbackException as e:
                reason = str(e.args[0]) if e.args else "User requested rollback"
                print(f"\n⚠️  Rolling back... Reason: {reason}")
                
                if not self.history:
                    print("   Cannot rollback beyond the first step. Restarting current step.")
                    self._rollback_reason = reason
                else:
                    # Rollback to previous step
                    popped_artifact = self.history.pop()
                    step_to_retry = popped_artifact.last_step
                    
                    print(f"   Rolling back to step: {step_to_retry}")
                    current_step_name = step_to_retry
                    
                    # Restore input for that step
                    if self.history:
                        current_artifact = self.history[-1]
                    else:
                         current_artifact = Artifact(
                            last_step="User Input",
                            next_step=self.start_step,
                            pass_data=actual_initial_input
                        )
                    self._rollback_reason = reason

            except Exception as e:
                # Unexpected error outside step loop (or propagated)
                print(f"\n⚠️  Critical Error in Flow: {e}")
                raise e

        return current_artifact

    def _get_step(self, name: str) -> Step:
        """Resolve step by name from local step map."""
        if name in self.step_map:
            return self.step_map[name]
        raise ValueError(f"Step '{name}' not found in Flow configuration.")
