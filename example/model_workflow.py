import asyncio
import os
import json
import shutil
from typing import Any, List, Dict
import litellm # pyright: ignore[reportMissingImports]
import httpx  # pyright: ignore[reportMissingImports]
from crewai import LLM, Agent, Task, Process, Crew  # pyright: ignore[reportMissingImports]
from aif.step import Step
from aif.flow import AIFFlow
from aif.interactive import InteractionManager
from aif.core.artifact import Artifact
from dotenv import load_dotenv # pyright: ignore[reportMissingImports]

load_dotenv()

# --- Setup ---
os.environ["OTEL_SDK_DISABLED"] = "true"
QGENIE_API_KEY = os.getenv("QGENIE_API_KEY")

# Disable SSL verification for internal servers if needed
litellm.client_session = httpx.Client(verify=False)

llm = LLM(
    model="openai/Turbo",
    base_url="https://qgenie-chat.qualcomm.com/v1",
    api_key=QGENIE_API_KEY,
    max_tokens=4096,
    is_litellm=True,
)

# Load Knowledge Base
MODEL_FILE = "./example/model.json"
with open(MODEL_FILE, "r", encoding="utf-8") as f:
    full_config = json.load(f)
    model_config = full_config.get("model_config", {})
    # Prepare a simplified list for the search agent to save tokens
    model_keys = list(model_config.keys())
    model_summaries = []
    for k, v in model_config.items():
        model_summaries.append(f"Key: {k}, Name: {v.get('model_name', '')}")
    
    knowledge_base_str = json.dumps(model_summaries, indent=2)
print(f"model_summaries: {model_summaries}")
# --- Agents ---

# Agent 1: Search
search_agent = Agent(
    role="Model Search Specialist",
    goal="Identify relevant model keys from the knowledge base based on user requirements.",
    backstory="You are an expert at mapping vague user requests to specific model identifiers in our database.",
    llm=llm,
    verbose=True
)

# Agent 2: Validation & Configuration
validation_agent = Agent(
    role="Configuration Specialist",
    goal="Validate model existence, apply parameter overrides, and prepare final JSONs.",
    backstory="You ensure technical accuracy. You take model keys, fetch their full configuration, apply user-requested changes, and validate the structure.",
    llm=llm,
    verbose=True
)

# Agent 3: Generator
generator_agent = Agent(
    role="File Generator",
    goal="Write JSON configurations to the workspace.",
    backstory="You are responsible for the final file generation step. You take the approved JSONs and save them to disk.",
    llm=llm,
    verbose=True
)

# --- Tasks ---

# Task 1: Search
# Input: User Query
# Output: JSON { "query": "...", "found_keys": [...] }
search_task = Task(
    description=f"""
    Analyze the user's request: "{{input}}"
    
    1. Search through the following model list for matches:
    {knowledge_base_str}
    
    2. Identify ALL model keys that match the user's description (e.g. "Qwen models", "7B models").
    
    3. Return a JSON object with:
       - "original_query": The user's input string.
       - "found_keys": A list of matching model keys (strings).
    
    DO NOT fabricate keys. Only use keys present in the list.
    """,
    expected_output="A JSON object containing original_query and found_keys.",
    agent=search_agent
)

# Task 2: Validation & Modification
# Input: Output of Task 1
validation_task = Task(
    description=f"""
    You will receive a JSON object with "original_query" and "found_keys".
    Input: {{input}}
    
    1. For each key in "found_keys", retrieve the FULL configuration from the global model_config.
       (Note: I will inject the full config context below)
    
    2. Analyze the "original_query" for any specific parameter overrides (e.g. "set CL to 2048", "change split to 4").
    
    3. For each model:
       - Start with the original JSON from model_config.
       - Apply the requested parameter changes.
       - Keep all other parameters exactly as they are in the original.
    
    4. Format the output as a list of JSON objects.
    
    Global Model Config (Keys and Values):
    {json.dumps(model_config, ensure_ascii=False)}
    """,
    expected_output="A list of modified JSON model configurations.",
    agent=validation_agent
)

# Task 3: Generation
# Input: Output of Task 2
generation_task = Task(
    description="""
    You will receive a list of JSON model configurations.
    
    1. Create a temporary directory named 'temp_workspace' if it doesn't exist.
    2. For each model configuration:
       - Use the 'model_name' or the dictionary key as the filename (e.g. 'model_name.json').
       - Write the JSON content to the file in 'temp_workspace'.
    
    3. Return a summary report of created files.
    """,
    expected_output="A text summary confirming the files created.",
    agent=generator_agent
)

# Define a tool for the generator to actually write files
# Since CrewAI agents generally need tools to affect the environment, 
# and AIF 'Step' execution wraps the crew, we can make the "Step" logic do the writing 
# OR give the agent a tool. 
# For simplicity in this flow, I will define a custom python function for the step execution 
# for Step 3, or use a tool. Let's use a callable Step for Step 3 to be explicit and safe.

def file_writer_step(artifact: Artifact) -> str:
    try:
        data = artifact.last_output
        # Parse if it's a string representation of json
        if isinstance(data, str):
            # Try to clean up markdown code blocks if present
            clean_data = data.strip()
            if clean_data.startswith("```json"):
                clean_data = clean_data[7:]
            if clean_data.startswith("```"):
                clean_data = clean_data[3:]
            if clean_data.endswith("```"):
                clean_data = clean_data[:-3]
            try:
                models = json.loads(clean_data)
            except json.JSONDecodeError:
                return f"Error: Could not parse JSON from previous step. Raw output: {data[:100]}..."
        else:
            models = data

        if not isinstance(models, list):
             return "Error: Expected a list of models."

        output_dir = "temp_workspace"
        os.makedirs(output_dir, exist_ok=True)
        
        created_files = []
        for model in models:
            # Try to find a good filename
            filename = model.get("model_name", "unknown_model").replace(" ", "_") + ".json"
            # If we had the original keys, that would be better, but model_name is fine.
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(model, f, indent=2, ensure_ascii=False)
            created_files.append(filename)
            
        return f"Successfully generated {len(created_files)} files in '{output_dir}': {', '.join(created_files)}"

    except Exception as e:
        return f"Failed to write files: {str(e)}"

# --- Interactive Flow ---

async def console_input(question: str) -> str:
    print(f"\n[AIF System] {question}")
    return input("User Input> ")

interactive = InteractionManager(input_callback=console_input)

# --- Define Flow using add_crew/add_step pattern ---

flow = AIFFlow(interactive=interactive)

# Step 1: Search
crew1 = Crew(agents=[search_agent], tasks=[search_task], verbose=True)
flow.add_step(
    name="SearchModels", 
    step_object=crew1, 
    max_iterations=3,
    require_user_confirmation=False,
    next_step="ValidateAndModify"
)

# Step 2: Validate
crew2 = Crew(agents=[validation_agent], tasks=[validation_task], verbose=True)
flow.add_step(
    name="ValidateAndModify", 
    step_object=crew2, 
    max_iterations=5, 
    require_user_confirmation=True,
    next_step="GenerateFiles"
)

# Step 3: Generate
flow.add_step(
    name="GenerateFiles",
    step_object=file_writer_step,
    max_iterations=1,
    require_user_confirmation=False
)

async def main():
    # View the flow structure
    flow.inspect()

    print("Welcome to the Model Generation Workflow.")
    print("Please describe the models you want (e.g. 'I want Qwen models with 2048 context length').")
    
    try:
        result = await flow.run()
        print("\n=== Workflow Completed ===")
        print("Final Output:", result.last_output)
    except Exception as e:
        print("\n=== Workflow Failed ===")
        print(e)

if __name__ == "__main__":
    asyncio.run(main())
