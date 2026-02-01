from __future__ import annotations

from typing import Union, Callable, Optional, Any, Dict, Tuple
from crewai import Crew, Agent, Task # pyright: ignore[reportMissingImports]
from aif.artifact import Artifact
from aif.constant import (
    HUMAN_ASK_PRINCIPLE, 
    RetryValidator,
    FEEDBACK_CONTEXT_HEADER,
    FEEDBACK_CONTEXT_EXPLANATION,
    VALIDATION_CONTEXT_HEADER,
    VALIDATION_CONTEXT_EXPLANATION,
    CUMULATIVE_CONTEXT_INSTRUCTIONS,
    CUMULATIVE_CONTEXT_FEEDBACK_INSTRUCTION,
    CUMULATIVE_CONTEXT_VALIDATION_INSTRUCTION
)
from aif.interactive import InteractionManager, UserExitException, RollbackException, RetryException
from aif.tools import AskUserTool
from aif.config import aif_config
from aif.validators import validate_with_agent_or_crew
import copy


ExecutableUnit = Union[Crew, Callable[[Artifact], Any]]
OutputProcessor = Callable[[Any], Tuple[str, Any]]
NextStep = Union[str, 'Step', Callable[[Artifact], Union[str, 'Step']], None]

class Step:
    """
    Step is the smallest execution unit in Flow, wrapping Crew or Callable.
    Each Step is independent and supports state reset on rollback.
    Supports separating step output from human display through output_processor.
    
    The Step object can be used directly as next_step parameter:
        search = flow.add_step(create_search_step(llm))
        build = flow.add_step(create_build_step(llm, next_step=search))
    """

    def __init__(
        self,
        name: str,
        step_object: ExecutableUnit,
        output_processor: Optional[OutputProcessor] = None,
        should_retry_guard_callback: Optional[RetryValidator] = None,
        next_step: NextStep = None,
        require_user_confirmation: bool = True
    ):
        self.name = name
        self.executable_unit = step_object
        self.output_processor = output_processor
        self.should_retry_guard_callback = should_retry_guard_callback
        self.next_step = next_step
        self.require_user_confirmation = require_user_confirmation
    
    def __str__(self) -> str:
        """Return step name when Step is used as string (e.g., in next_step)."""
        return self.name
    
    def __repr__(self) -> str:
        """Return a readable representation."""
        return f"Step('{self.name}')"

    def _process_step_output(self, raw_result: Any) -> Tuple[str, Any]:
        """
        Process step output into display message and pass data.
        
        Args:
            raw_result: The raw output from step execution
            
        Returns:
            Tuple of (msg, pass_data):
            - msg: String message to display to the user
            - pass_data: Data to be passed to the next step (in native format: str/dict/list)
            
        Note:
            If no output_processor is provided:
            - msg: String representation of raw_result for display
            - pass_data: raw_result in its native format (preserves dict/list types)
            
            Users can provide their own output_processor function that returns a tuple
            of (msg, pass_data) to customize how step results are processed and displayed.
        """
        if self.output_processor:
            return self.output_processor(raw_result)
        
        # Default: convert to string for display, but keep native format for pass_data
        return (str(raw_result), raw_result)

    async def execute(
        self,
        input_artifact: Artifact,
        interactive: InteractionManager
    ) -> Artifact:
        """
        Execute the Step, handling automatic retries and user interaction.
        Returns Artifact on success.
        """
        # Track all feedback in chronological order with type distinction
        # Each item is a tuple: (type, content) where type is 'user_feedback' or 'validation_error'
        feedback_history = []
        current_attempt = 0

        while True:  # Manual Retry Loop
            current_attempt += 1
            
            try:
                raw_result = await self._execute_once(input_artifact, interactive, feedback_history, current_attempt)
                validation_passed = True
                validation_error = None
                
                if self.should_retry_guard_callback:
                    should_retry, reason = await self._should_retry_guard(raw_result)
                    if should_retry:
                        validation_passed = False
                        validation_error = reason
                        # Add validation error to feedback history with type marker
                        feedback_history.append(('validation_error', reason))

            except Exception as e:
                raise e
            
            # Process step output - separate msg for display and pass_data for next step
            msg, pass_data = self._process_step_output(raw_result)
            
            # Check if we can auto-approve
            if validation_passed and not self.require_user_confirmation:
                print(f"   ✓ Auto-approved")
                return Artifact(
                    last_step=self.name,
                    pass_data=pass_data
                )

            
            display_msg = f"\n{msg}\n"
            
            if validation_error:
                display_msg += f"Validation Not Pass!: {validation_error}\n"
            
            display_msg += "\n\nOptions:\n- Press Enter or type 'yes' to confirm and continue\n- Type feedback directly to retry step\n- '/rollback [reason]' to rollback flow"
            
            if not validation_passed:
                display_msg += "\n(Recommended: Retry with your new comments)"

            try:
                user_input = await interactive.get_user_input(display_msg)
                
                # Check for explicit "yes" or empty input (Enter key)
                if user_input.strip().lower() == "yes" or user_input.strip() == "":
                    return Artifact(
                        last_step=self.name,
                        pass_data=pass_data
                    )
                
                # Treat as feedback/retry - add to history with type marker
                feedback = user_input
                feedback_history.append(('user_feedback', feedback))
                continue

            except RetryException as e:
                # This catches explicit /retry commands if supported by interactive
                feedback = str(e.args[0]) if e.args else "User requested retry"
                feedback_history.append(('user_feedback', feedback))
                continue

            except (UserExitException, RollbackException):
                raise

            except Exception as e:
                error_msg = f"Step '{self.name}' execution failed with error: {str(e)}"
                try:
                    await interactive.get_user_input(f"{error_msg}\nOptions: /retry, /rollback, /exit")
                    continue
                except RetryException as re:
                    feedback = str(re.args[0]) if re.args else str(e)
                    feedback_history.append(('user_feedback', feedback))
                    continue

    async def _execute_once(
        self,
        input_artifact: Artifact,
        interactive: InteractionManager,
        feedback_history: list,
        current_attempt: int
    ) -> Any:
        """
        Single execution of the Step logic with cumulative context.
        
        Following best practices from mature AI products (ChatGPT, Claude),
        we merge the original request with feedback history into a clear,
        cumulative context that the LLM can understand.
        
        Args:
            input_artifact: The input artifact containing the original request
            interactive: The interaction manager
            feedback_history: List of tuples (type, content) in chronological order
                            where type is 'user_feedback' or 'validation_error'
            current_attempt: Current attempt number
        """

        if isinstance(self.executable_unit, Crew):
            original_crew = self.executable_unit
            original_request: Any = input_artifact.pass_data
            
            # Build cumulative context following AI product best practices
            if feedback_history:
                context_parts = [
                    "=== TASK CONTEXT ===",
                    f"Original request: {original_request}",
                    "",
                    "=== FEEDBACK HISTORY (in chronological order) ==="
                ]
                
                # Add explanations for both types
                context_parts.extend([
                    FEEDBACK_CONTEXT_EXPLANATION,
                    VALIDATION_CONTEXT_EXPLANATION,
                    ""
                ])
                
                # Add all feedback in chronological order with type labels
                has_user_feedback = False
                has_validation_errors = False
                
                for i, (feedback_type, content) in enumerate(feedback_history, 1):
                    if feedback_type == 'user_feedback':
                        context_parts.append(f"{i}. [User Feedback] {content}")
                        has_user_feedback = True
                    elif feedback_type == 'validation_error':
                        context_parts.append(f"{i}. [Validation Error] {content}")
                        has_validation_errors = True
                
                context_parts.append("")
                
                # Build final context with instructions
                cumulative_context = "\n".join(context_parts)
                cumulative_context += CUMULATIVE_CONTEXT_INSTRUCTIONS
                if has_user_feedback:
                    cumulative_context += CUMULATIVE_CONTEXT_FEEDBACK_INSTRUCTION
                if has_validation_errors:
                    cumulative_context += CUMULATIVE_CONTEXT_VALIDATION_INSTRUCTION
                
                inputs: Dict[str, Any] = {"input": cumulative_context}
            else:
                # First attempt, use original request directly
                inputs: Dict[str, Any] = {"input": original_request}

            ask_tool = AskUserTool(interactive)

            # Deep copy the crew using its native copy method
            # This preserves all attributes/methods and graph integrity (tasks -> agents, task -> context)
            if hasattr(original_crew, "copy"):
                 crew = original_crew.copy()
            else:
                 # Fallback if .copy() is unavailable (unlikely in recent CrewAI)
                 crew = copy.copy(original_crew)

            # Inject AskUserTool into all agents in the copied crew
            for agent in crew.agents:
                current_tools = agent.tools or []
                agent.tools = current_tools + [ask_tool]

            # Debug: Print actual inputs for Crew
            if aif_config.is_debug_step_enabled():
                print(f"      ","-"*15)
                print(f"   🔍 [Debug] Crew kickoff")
                print(f"      - Current Attempt: {current_attempt}")
                if feedback_history:
                    print(f"      - Feedback History ({len(feedback_history)} items in chronological order):")
                    for i, (feedback_type, content) in enumerate(feedback_history, 1):
                        print(f"        {i}. [{feedback_type}] {content}")
                # Display the complete inputs dict that will be passed to LLM
                for key, value in inputs.items():
                    # Add indentation to multi-line values for better readability
                    value_str = str(value)
                    indented_value = '\n           '.join(value_str.split('\n'))
                    print(f"   - Actual inputs:      {key}: {indented_value}")
                    print(f"      ","-"*15)
            if hasattr(crew, 'kickoff_async'):
                return await crew.kickoff_async(inputs=inputs)
            else:
                return crew.kickoff(inputs=inputs)

        elif callable(self.executable_unit):
                    # Debug: Print input information
            if aif_config.is_debug_step_enabled():
                print(f"   🔍 [Debug] Callable input: {input_artifact}")
            return self.executable_unit(input_artifact)

        raise ValueError("Unsupported executable type")

    async def _should_retry_guard(
        self,
        result: Any
    ) -> tuple[bool, str]:
        """
        Validate result using guard_callback.
        Supports three types of validators:
        1. Traditional function: (result) -> (should_retry, reason)
        2. Agent: Uses LLM to intelligently validate
        3. Crew: Uses multiple agents for complex validation
        
        Returns:
            (should_retry, reason): True if validation failed and should retry
        """
        if self.should_retry_guard_callback is None:
            return False, ""
        
        # Type 1: Traditional function validator
        if callable(self.should_retry_guard_callback) and not isinstance(self.should_retry_guard_callback, (Agent, Crew)):
            result_tuple = self.should_retry_guard_callback(result)
            if isinstance(result_tuple, tuple) and len(result_tuple) == 2:
                return result_tuple
            return False, ""
        
        # Type 2 & 3: Agent or Crew validator (delegated to validators module)
        return await validate_with_agent_or_crew(self.should_retry_guard_callback, result)
