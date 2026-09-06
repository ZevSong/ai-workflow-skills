# AI Workflow Skills

Reusable workflows for AI agents, with task cards, examples, and explicit execution boundaries.

可独立复用的 AI Agent 工作流 Skills。每个 Skill 提供执行规则、使用文档、示例和验证说明，明确适用环境与能力边界。

## 已提供的 Skill

| Skill | 用途 | 当前验证范围 |
| --- | --- | --- |
| [plan-agent-tasks](skills/plan-agent-tasks/README.md) | 将已确认需求拆成可执行、可验收的任务卡，生成具名会话、逐会话模型/Fast 配置、提示词和 Mermaid 流程图 | 见 [验证记录](skills/plan-agent-tasks/examples/validation.md)；自动调度及逐会话模型/Fast 未完成端到端验证 |

## 快速开始

1. 获取完整的 `skills/plan-agent-tasks/` 目录，或从本仓库的 [Releases](https://github.com/ZevSong/ai-workflow-skills/releases) 下载独立 ZIP（发布后可用）。保留目录中的许可证及全部引用资源。
2. 按所用 Agent 的 Skill 安装方式安装整个目录。Codex 用户可以将下面的自然语言请求发送给内置 Skill Installer：

   ```text
   使用 $skill-installer，从 GitHub 仓库 ZevSong/ai-workflow-skills 安装 skills/plan-agent-tasks，保留完整目录及 MIT 许可证。
   ```

3. 先讨论清楚需求，再明确调用：

   ```text
   使用 $plan-agent-tasks，按人工模式将本会话已确认的需求生成任务包。
   ```

也可指定全自动或半自动模式。**生成任务包后，由用户发送其中的 Main 启动提示词开始执行。** 选择自动模式不会在生成阶段启动其他会话。

Codex 的安装和发现机制以 [官方文档](https://learn.chatgpt.com/docs/build-skills) 为准；此安装入口尚未在全新账号环境验收。其他 Agent 可按其支持方式加载整个 Skill 目录，但不能据此认定自动调度已经兼容。

本仓库中的 Skill 是维护源，宿主安装目录是使用副本。已有同名 Skill 时先保留个人定制，再按宿主支持的方式更新；不要将两个版本同时注册为同名 Skill。

## 执行模式

| 模式 | 谁推进会话 | 用户参与点 |
| --- | --- | --- |
| 人工 `manual` | 用户逐个启动或续接；Main 给出下一步和提示词 | 每次会话交接 |
| 全自动 `auto` | Main 在授权范围内调度开发、独立审查、修复、复审和集成 | 启动 Main、真实阻塞和项目所需批准 |
| 半自动 `semi-auto` | Main 自动推进已获准阶段 | 启动首阶段；确认每个后续阶段 |

未指定时默认人工；任务较多时才主动建议半自动。普通聊天不会隐式触发此 Skill。自动调度依赖实际宿主工具，Desktop 独立会话与内部子 Agent 分别处理。

## 仓库约定

- 一个 Skill 一个目录；运行依赖和模板放在该目录中，外部工具依赖明确声明。
- `SKILL.md` 面向 Agent，Skill 内的 `README.md` 面向使用者；执行规则只维护一份。
- 任务卡和提示词使用有明确锚点的相对路径；跨仓引用使用仓库标识加仓库内路径。
- 示例使用虚构项目；明确区分示例、静态检查、Agent 场景验证和真实执行。
- 格式遵循 [Agent Skills 规范](https://agentskills.io/specification)。`agents/openai.yaml` 是 Codex 可选配置，不代表其他宿主已支持相同配置。

根目录的 [skill-template](templates/skill-template/README.md) 用于编写新 Skill；各 Skill 执行时使用自身的 `assets/`。

## 校验与独立打包

以下命令从本仓库根执行，维护工具需要 Python 3.11+；Skill 本身不要求安装 Python。

```sh
python -m pip install -r requirements-dev.txt
python scripts/validate_skills.py
python -m unittest discover -s tests -v
python scripts/package_skill.py plan-agent-tasks
```

最后一条命令生成 `dist/plan-agent-tasks.zip`，包含完整 Skill 目录、示例和 MIT 许可证。静态校验检查元数据、文档链接、目录自包含和可移植路径，不证明自动调度或业务验收成功。

打包器不覆盖已有 ZIP；重新打包时可使用新的输出目录，例如 `python scripts/package_skill.py plan-agent-tasks --output dist/recheck`。

## 贡献与演进

欢迎提交真实使用反馈及可复现示例，参见 [贡献说明](CONTRIBUTING.md)。初期以仓库发布标签管理版本，发布记录按 Skill 列出变更。

变更通过 PR 和 Linux / Windows CI 后合入 `main`；安全漏洞请参见 [安全报告说明](SECURITY.md)。

后续候选方向包括仓库分析、设计文档生成和代码审查；收录前应先有可用 Skill 和验证案例。插件打包、更多 Agent 适配和自动评估按实际需求增加。

## 许可证

本仓库使用 [MIT License](LICENSE)。每个可独立分发的 Skill 包含同一许可证副本，复制或分发时保留相应版权与许可声明。
