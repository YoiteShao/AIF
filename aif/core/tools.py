from typing import Type, Optional
from pydantic import BaseModel, Field # pyright: ignore[reportMissingImports]
from crewai.tools import BaseTool # pyright: ignore[reportMissingImports]
from aif.interactive import InteractionManager
import asyncio

class AskUserInput(BaseModel):
    """Input schema for AskUserTool."""
    question: str = Field(..., description="The question to ask the user.")

class AskUserTool(BaseTool):
    name: str = "Ask User"
    description: str = (
        "Useful when you need to ask the user for more information, "
        "confirmation, or clarification. "
        "The user's response will be returned as a string."
    )
    args_schema: Type[BaseModel] = AskUserInput
    interactive: Optional[InteractionManager] = None

    def __init__(self, interactive: InteractionManager, **kwargs):
        super().__init__(**kwargs)
        self.interactive = interactive

    def _run(self, question: str) -> str:
        """
        Execute the tool.
        
        This method bridges the synchronous execution model of standard Tools 
        with the asynchronous nature of InteractionManager.
        It detects if an asyncio loop is running and schedules the user interaction accordingly.
        """
        if not self.interactive:
            return "Error: InteractionManager not configured."
        
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # We are likely inside an async loop (e.g., Flow.run).
                # To execute the async get_user_input from this sync method, we need to schedule it.
                # Note: This assumes the sync method is running in a different thread or 
                # can block safely without deadlocking the loop if using run_coroutine_threadsafe.
                # If running in the same thread as the loop, this calls for specific async handling 
                # which standard sync tools don't support naturally.
                # We assume here that CrewAI/LangChain executes tools in a way that permits this,
                # or that the loop is available for scheduling.
                future = asyncio.run_coroutine_threadsafe(
                    self.interactive.get_user_input(question), loop
                )
                return future.result()
            else:
                # No running loop, or simple sync context.
                return asyncio.run(self.interactive.get_user_input(question))

        except Exception as e:
            return f"Error communicating with user: {str(e)}"
