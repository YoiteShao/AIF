# aif/example/json_generation_flow.py
import asyncio
from crewai import Agent, Task, Process
from aif.team import Team
from aif.step import Step
from aif.flow import AIFFlow
from aif.interactive import InteractiveFlow
from aif.core.artifact import Artifact

# 定义 Agent
generator = Agent(
    role="JSON 生成器",
    goal="根据用户需求生成合法 JSON",
    backstory="你擅长生成结构化 JSON",
    allow_delegation=False
)

validator = Agent(
    role="JSON 校验器",
    goal="校验 JSON 是否合法并符合要求",
    backstory="你严格校验 JSON 格式和内容"
)

writer = Agent(
    role="文件写入器",
    goal="将 JSON 写入文件",
    backstory="你负责安全写入文件"
)

# 定义 Task
gen_task = Task(description="生成 JSON",
                expected_output="JSON 字符串", agent=generator)
val_task = Task(description="校验 JSON", expected_output="校验结果", agent=validator)
write_task = Task(description="写入文件", expected_output="写入确认", agent=writer)

# 创建 Team（内部循环校验）
json_team = Team(
    name="JSONTeam",
    agents=[generator, validator, writer],
    tasks=[gen_task, val_task, write_task],  # 实际循环在 Team.execute 中处理
    process=Process.sequential
)

# 创建 Step
step1 = Step(name="GenerateAndValidateJSON", executable=json_team)

# 交互回调（示例使用 input）


def sync_input(question: str) -> str:
    print(question)
    return input("> ")


interactive = InteractiveFlow(input_callback=sync_input)

# 创建 Flow
flow = AIFFlow(steps=[step1], interactive=interactive)

# 运行
final_artifact = asyncio.run(flow.run())
print("最终结果:", final_artifact.data)
