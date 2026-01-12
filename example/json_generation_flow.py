import asyncio
import os
import litellm # pyright: ignore[reportMissingImports]
import httpx  # pyright: ignore[reportMissingImports]
from crewai import LLM, Agent, Task, Process, Crew  # pyright: ignore[reportMissingImports]
from aif.step import Step
from aif.flow import AIFFlow
from aif.interactive import InteractionManager
import json
from typing import Any
from dotenv import load_dotenv # pyright: ignore[reportMissingImports]
load_dotenv()

os.environ["OTEL_SDK_DISABLED"] = "true"
QGENIE_API_KEY = os.getenv("QGENIE_API_KEY")
litellm.client_session = httpx.Client(verify=False)
llm = LLM(
    model="openai/Turbo",
    base_url="https://qgenie-chat.qualcomm.com/v1",
    api_key=QGENIE_API_KEY,
    max_tokens=4096,
    is_litellm=True,
)

with open("./example/model.json", "r", encoding="utf-8") as f:
    data = json.load(f)
    # Escape curly braces to prevent formatting issues in CrewAI/LangChain
    json_text = json.dumps(data, ensure_ascii=False)
    safe_json_text = json_text.replace("{", "{{").replace("}", "}}")

json_guide = Agent(
    role="JSON Expert",
    goal="Understand the model configuration and extract relevant models based on user queries.",
    backstory=f"You are an expert in the following model configuration: {safe_json_text}\nYour job is to retrieve and modify these models as requested.",
    allow_delegation=False,
    llm=llm
)

gen_task = Task(
    description="""
    Analyze the user's request: "{input}"
    Identify target models and apply parameter overrides based on the provided model_config.

    1. **Retrieval**: Find ALL models in the `model_config` that match the user's vague instructions (e.g., if user says "7B models", find all models with "7B" in their name).
    2. **Modification**: If the user specifies parameter updates (e.g., "2K CL"), apply these changes to the matched models (e.g., set "CL" to "2048").
    3. **Filtering**: For the final output, strictly limit the fields for each model to ONLY:
       - `model_name`
       - `CL`
       - `ARNs`
       - `num_split`
    4. **Output**: Return a JSON object containing the processed list of models.
    """,
    expected_output="A JSON object containing the filtered and modified models.",
    agent=json_guide
)

valid_task = Task(
    description="""Verify if these JSON files actually exist in the model configuration
    If it exists, check if everything else has been tampered with except for the fields requested by the user that need to be modified.
    """,
    expected_output="""If the rule outputs true, otherwise false""",
    agent=json_guide
)



# --- Step 1: Generation & Validation ---
gen_val_team = Crew(
    agents=[json_guide],
    tasks=[gen_task, valid_task],
    process=Process.sequential
)


def check_validation(result: Any) -> tuple[bool, str]:
    """
    Callback to check if the Step output indicates failure.
    If Validator says FAIL, we trigger AIF auto-retry.
    """
    result_str = str(result)
    if "FAIL" in result_str:
        return True, result_str  # Should Retry, Reason
    return False, ""


# 3. Interactive Setup
async def console_input(question: str) -> str:
    print(f"\n[AIF] {question}")
    return input("[User]> ")

interactive = InteractionManager(input_callback=console_input)

# 4. Flow
flow = AIFFlow(interactive=interactive)

step1 = flow.add_step(
    name="GenerateAndValidate",
    step_object=gen_val_team,
    retry_check_callback=check_validation,
    max_iterations=3,
    next_step=None
)


async def main():
    print("Starting Flow...")
    try:
        result = await flow.run()
        print("\nFinal Result:", result.last_output)
    except Exception as e:
        print("\nFlow Failed:", e)

if __name__ == "__main__":
    asyncio.run(main())
