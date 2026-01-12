import asyncio
from typing import Any
from aif.flow import AIFFlow
from aif.interactive import InteractionManager
from aif.core.artifact import Artifact

# --- 1. Define Step Functions ---

# Step 1: Greeter
# Takes the input (from user) and adds a greeting.
def greet_step(artifact: Artifact) -> str:
    user_name = artifact.last_output
    print(f"[Step 1] Processing input: {user_name}")
    return f"Hello, {user_name}!"

# Step 2: Uppercaser
# Takes the greeting and makes it uppercase.
def uppercase_step(artifact: Artifact) -> str:
    greeting = artifact.last_output
    print(f"[Step 2] Processing input: {greeting}")
    return greeting.upper()

# --- 2. Setup Interaction ---

# A simple console input callback
async def console_input(question: str) -> str:
    print(f"\n[AIF System] {question}")
    return input("User Input> ")

interactive = InteractionManager(input_callback=console_input)

# --- 3. Build the Flow ---

flow = AIFFlow(interactive=interactive)

# Add Step 1: Greet
# require_user_confirmation=True means the user will be asked to confirm the result before moving to the next step.
flow.add_step(
    name="Greeter",
    step_object=greet_step,
    require_user_confirmation=True
)

# Add Step 2: Uppercase
# require_user_confirmation=False means it will run automatically after Step 1.
flow.add_step(
    name="Uppercaser",
    step_object=uppercase_step,
    require_user_confirmation=False
)

# --- 4. Run the Flow ---

async def main():
    # Print the flow structure
    flow.inspect()

    print("Welcome to the Simple AIF Example.")
    print("Please enter your name to start.")
    
    try:
        # The flow starts by asking for initial input via interactive.get_initial_input()
        result = await flow.run()
        print("\n=== Workflow Completed ===")
        print("Final Output:", result.last_output)
    except Exception as e:
        print("\n=== Workflow Failed ===")
        print(e)

if __name__ == "__main__":
    asyncio.run(main())
