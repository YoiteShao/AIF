from __future__ import annotations

from typing import Union, Callable, Optional, Any, Dict
from crewai import  Crew # pyright: ignore[reportMissingImports]
from .core.artifact import Artifact
from .core.types import HUMAN_ASK_PRINCIPLE, RetryValidator
from .interactive import InteractionManager, UserExitException, RollbackException, RetryException
from .core.tools import AskUserTool
import copy


ExecutableUnit = Union[Crew, Callable[[Artifact], Any]]
class Step:
    """
    Step is the smallest execution unit in Flow, wrapping Crew or Callable.
    Each Step is independent and supports state reset on rollback.
    """

    def __init__(
        self,
        name: str,
        step_object: ExecutableUnit,
        retry_check_callback: Optional[RetryValidator] = None,
        max_iterations: int = 3,
        next_step: Union[str, Callable[[Artifact], str], None] = None,
        require_user_confirmation: bool = True
    ):
        self.name = name
        self.executable_unit = step_object
        self.retry_check_callback = retry_check_callback
        self.max_iterations = max_iterations
        self.next_step = next_step
        self.require_user_confirmation = require_user_confirmation

    async def execute(
        self,
        input_artifact: Artifact,
        interactive: InteractionManager,
        previous_error: Optional[str] = None
    ) -> Artifact:
        """
        Execute the Step, handling automatic retries and user interaction.
        Returns Artifact on success.
        """
        current_error = previous_error

        while True:  # Manual Retry Loop
            
            # Automatic Retry Loop
            attempt = 0
            raw_result = None
            validation_passed = False
            validation_error = None
            
            while attempt < self.max_iterations:
                attempt += 1
                try:
                    raw_result = await self._execute_once(input_artifact, interactive, current_error)
                    validation_passed = True
                    if self.retry_check_callback:
                        should_retry, reason = self.retry_check_callback(raw_result)
                        if should_retry:
                            validation_passed = False
                            validation_error = reason
                            
                            if attempt < self.max_iterations:
                                current_error = reason
                                print(f"Step '{self.name}' auto-retry ({attempt}/{self.max_iterations}): {reason}")
                                continue
                    
                    break

                except Exception as e:
                    raise e
            
            # Check if we can auto-approve
            if validation_passed and not self.require_user_confirmation:
                print(f"Step '{self.name}' auto-approved.")
                return Artifact(
                    last_step=self.name,
                    last_output=raw_result,
                    next_input=raw_result
                )

            # User Interaction
            status_str = "Success" if validation_passed else "Validation Failed"
            if not validation_passed and attempt >= self.max_iterations:
                status_str += f" (Max retries {self.max_iterations} reached)"
            
            preview = str(raw_result)
            if len(preview) > 500:
                preview = preview[:500] + "..."
            
            msg = (f"Step '{self.name}' completed.\n"
                   f"Status: {status_str}\n"
                   f"Output Preview:\n{preview}\n")
            
            if validation_error:
                msg += f"Validation Error: {validation_error}\n"
            
            msg += "\nOptions:\n- Type 'yes' to confirm and proceed\n- Type feedback directly to retry step\n- '/rollback [reason]' to rollback flow"
            
            if not validation_passed:
                msg += "\n(Recommended: Retry)"

            try:
                user_input = await interactive.get_user_input(msg)
                
                # Check for explicit "yes"
                if user_input.strip().lower() == "yes":
                    return Artifact(
                        last_step=self.name,
                        last_output=raw_result,
                        next_input=raw_result
                    )
                
                # Treat as feedback/retry
                feedback = user_input if user_input.strip() else "User requested retry (empty input)"
                current_error = feedback
                continue

            except RetryException as e:
                # This catches explicit /retry commands if supported by interactive
                feedback = str(e.args[0]) if e.args else "User requested retry"
                current_error = feedback
                continue

            except (UserExitException, RollbackException):
                raise

            except Exception as e:
                error_msg = f"Step '{self.name}' execution failed with error: {str(e)}"
                try:
                    await interactive.get_user_input(f"{error_msg}\nOptions: /retry, /rollback, /exit")
                    current_error = str(e)
                    continue
                except RetryException as re:
                    current_error = str(re.args[0]) if re.args else str(e)
                    continue

    async def _execute_once(
        self,
        input_artifact: Artifact,
        interactive: InteractionManager,
        previous_error: Optional[str] = None
    ) -> Any:
        """
        Single execution of the Step logic.
        """

        if isinstance(self.executable_unit, Crew):
            original_crew = self.executable_unit
            inputs: Dict[str, Any] = {"input": input_artifact.pass_to_next_input}
            if previous_error:
                inputs["previous_error"] = previous_error
                inputs["feedback"] = previous_error

            ask_tool = AskUserTool(interactive)

            # Clone agents and inject tools
            run_agents = []
            agent_map = {}
            for original_agent in original_crew.agents:
                new_agent = copy.copy(original_agent)
                current_tools = new_agent.tools or []
                new_agent.tools = current_tools + [ask_tool]
                run_agents.append(new_agent)
                agent_map[original_agent] = new_agent

            # Clone tasks and map to new agents
            run_tasks = []
            for original_task in original_crew.tasks:
                new_task = copy.copy(original_task)
                if original_task.agent in agent_map:
                    new_task.agent = agent_map[original_task.agent]
                
                new_task.description += HUMAN_ASK_PRINCIPLE
                run_tasks.append(new_task)

            # Reconstruct Crew with new agents and tasks
            # We use kwargs unpacking to copy other attributes from the original crew
            # avoiding manual listing and deepcopying of shared resources (like memory)
            exclude_keys = {'agents', 'tasks', 'id', 'process_id'}
            crew_kwargs = {
                k: v for k, v in vars(original_crew).items() 
                if k not in exclude_keys and not k.startswith('_')
            }
            
            crew = Crew(
                agents=run_agents,
                tasks=run_tasks,
                **crew_kwargs
            )
            if hasattr(crew, 'kickoff_async'):
                return await crew.kickoff_async(inputs=inputs)
            else:
                return crew.kickoff(inputs=inputs)

        elif callable(self.executable_unit):
            return self.executable_unit(input_artifact)

        raise ValueError("Unsupported executable type")
