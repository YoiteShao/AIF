from __future__ import annotations

from typing import Optional, Callable, Awaitable, Union, cast, List, Dict, Any


async def console_input(question: str) -> str:
    """
    Default interactive console input with formatting.
    This is a reference implementation for CLI-based interaction.
    
    Usage:
        manager = InteractionManager(input_callback=console_input)
    """
    print(f"\n💬 [User Input Required]")
    print(f"   {question}")
    user_input = input("   👤 > ")
    return user_input


class UserExitException(BaseException):
    """Exception raised when user requests to exit."""
    pass

class RollbackException(BaseException):
    """Exception raised when user requests to rollback."""
    pass

class RetryException(BaseException):
    """Exception raised when user requests to retry."""
    pass

class InteractionManager:
    """
    InteractionManager is the hub for all user interactions.
    It receives initial input and handles questions from internal Agents/Crews.
    It processes special user commands (/exit, /rollback, /retry) by raising exceptions
    that control flow logic can catch.
    It also maintains conversation history and user context.
    """

    def __init__(
        self,
        #If you are running on a terminal, input_callback in Python input();
        #If you are running on a webpage, input_callback in websocket. send().
        input_callback: Union[Callable[[str], Awaitable[str]], Callable[[str], str]],
        initial_input: Optional[str] = None
    ):
        """
        :param input_callback: Async or sync callback to ask user and get response.
        :param initial_input: Optional initial input string.
        """
        self.input_callback = input_callback
        self.initial_input: Optional[str] = initial_input
        self.current_question: Optional[str] = None
        self.history: List[Dict[str, str]] = []
        self.context: Dict[str, Any] = {}

    def add_to_history(self, role: str, content: str):
        """Add a message to the conversation history."""
        self.history.append({"role": role, "content": content})

    def get_history(self) -> List[Dict[str, str]]:
        """Get the full conversation history."""
        return self.history

    def set_context(self, key: str, value: Any):
        """Set a value in the user context."""
        self.context[key] = value

    def get_context(self, key: str) -> Any:
        """Get a value from the user context."""
        return self.context.get(key)

    async def get_user_input(self, question: str) -> str:
        """
        Ask user a question.
        Parses commands and raises Control Flow exceptions if needed.
        """
        self.current_question = question
        self.add_to_history("system", question)
        
        # We try to await if it returns a coroutine, otherwise just use value.
        # But we can't know before calling.
        # So we just call it. If it returns awaitable, we await.
        
        result = self.input_callback(question)
        if hasattr(result, "__await__"):
            raw_input = await cast(Awaitable[str], result)
        else:
            raw_input = str(result)

        raw_input = raw_input.strip()
        self.add_to_history("user", raw_input)
        lower_input = raw_input.lower()

        if lower_input.startswith("/exit"):
            raise UserExitException("User requested exit")
        if lower_input.startswith("/rollback"):
            reason = raw_input[9:].strip() or "User requested rollback"
            raise RollbackException(reason)
        if lower_input.startswith("/retry"):
            feedback = raw_input[6:].strip() or "User requested retry"
            raise RetryException(feedback)

        return raw_input

    async def get_initial_input(self) -> str:
        """Get initial input, ask if missing."""
        if self.initial_input:
            return self.initial_input
        
        resp = await self.get_user_input("Please provide initial input:")
        return resp
