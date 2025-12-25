# AIF: Artifact-Oriented Interactive Flow Framework

[![GitHub stars](https://img.shields.io/github/stars/YoiteShao/aif?style=social)](https://github.com/YoiteShao/aif)
[![CrewAI Compatible](https://img.shields.io/badge/Built%20on-CrewAI-blue)](https://docs.crewai.com)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org)

**AIF（Artifact-Oriented Interactive Flow Framework）** 是一个基于 **CrewAI** 的高级交互式工作流框架，专为需要**频繁用户交互（Human-in-the-Loop）、自动纠错回退、严格状态控制**的复杂 AI 任务而设计。

在 CrewAI 官方 Flows 已非常成熟的今天（2025 年支持持久化状态、条件路由、可视化、HITL），AIF 专注于补足官方 Flows 在**高交互 + 纠错回退**场景下的体验空白，提供更安全、可控、用户友好的解决方案。

## 为什么选择 AIF？核心差异化优势


| 特性               | CrewAI 官方 Flows (2025 最新)              | AIF 框架突出优势                                                                                                |
| ------------------ | ------------------------------------------ | --------------------------------------------------------------------------------------------------------------- |
| **统一用户交互**   | 支持 HITL，但输入可能分散在多个路由/方法中 | **InteractiveFlow 中枢**：所有用户提问统一管理，避免多 Agent 并发干扰，支持 `/exit`、`/rollback`、`/retry` 命令 |
| **显式回退机制**   | 无原生回退（依赖持久化或手动恢复）         | **内置回退快照**：携带错误原因自动注入上一步，状态重置，支持用户主动回退                                        |
| **纠错循环**       | 可通过路由模拟循环                         | **Team 内置生成-校验-补充循环**：校验失败自动回退或询问用户补充信息                                             |
| **状态与内存控制** | 全局共享 state，灵活但易污染               | **Artifact 严格传递**：仅成功结果或失败原因跨 Step 传递，防止 prompt 泄漏                                       |
| **人工干预支持**   | 可实现，但需大量自定义逻辑                 | 用户可随时退出、手动修复后`/retry`，交互体验更友好                                                              |
| **适用场景**       | 通用自动化、生产级复杂 workflow            | **交互密集任务**：JSON/表单生成验证、数据补全、多轮用户确认、内容审核等                                         |

**AIF 不是替代官方 Flows，而是完美补充**——当你的任务涉及“多次问用户”“失败自动补信息”“严格防泄漏”时，AIF 能大幅减少自定义代码，让开发更高效、更可靠。
