# 人工模式任务包：独立前向生成案例

本例由独立验证会话实际读取 [plan-agent-tasks Skill](../../SKILL.md)、两份 reference 和全部五种模板后生成，不是只有结构的空示例。输入为可公开的虚构仓库 `demo-handbook`，没有真实客户资料、宿主 ID 或机器路径。当前保留的是本地草案。

本次测试先建立并读取最小输入，再核对需求、确定两个叶子任务及会话、写入任务包和示例回复，最后检查文件与入口一致性。只验证这一次材料生成，不执行计划中的业务任务，也不启动计划中的任何会话。

## 原始用户请求

以下请求与 [fixture README](fixture/demo-handbook/README.md) 中保留的输入相同：

> 请使用 `$plan-agent-tasks`，为虚构仓库 demo-handbook 生成一个人工模式任务包，仅生成材料，不开始业务执行。需要两项能独立验收的中文文档成果：
>
> 1. 计划新建 `docs/quickstart.md`，说明获取完整 Skill 目录、按宿主安装、显式调用、查看结果四步，并指出只生成计划不会启动业务。
> 2. 计划新建 `docs/troubleshooting.md`，覆盖卡片缺失、需求不明确、自动调度工具缺失三种情况，每种写可观察现象和下一步。
>
> 非目标：安装任何工具、实际调度、产品代码、发布。明确采用人工模式，只生成任务包。项目没有额外人类审查门禁；默认不推送、不合并。两项文件写入不冲突，均为计划新建。验收用可复查的阅读步骤即可，不虚构测试命令。

## 文件与路径锚点

`fixture/demo-handbook/` 是本例的目标仓库根。所有卡片里的 `demo-handbook` 根相对路径都在这个目录解析；输出直接位于它的 `docs/task-packets/DEMO-DOCS/`，没有借助另一份文件镜像或相邻克隆。Markdown 链接按所在文件解析。

```text
manual-task-pack/
  README.md
  reply.md
  fixture/demo-handbook/
    AGENTS.md
    README.md
    docs/task-packets/DEMO-DOCS/
      packet.md
      main.md
      prompts.md
      workers/DEMO-DOCS-01.md
      workers/DEMO-DOCS-02.md
      reviews/DEMO-DOCS-01.md
      reviews/DEMO-DOCS-02.md
```

- 输入：[AGENTS.md](fixture/demo-handbook/AGENTS.md) 与 [README.md](fixture/demo-handbook/README.md)。
- 输出入口：[总卡](fixture/demo-handbook/docs/task-packets/DEMO-DOCS/packet.md)、[Main 卡](fixture/demo-handbook/docs/task-packets/DEMO-DOCS/main.md)、[提示词](fixture/demo-handbook/docs/task-packets/DEMO-DOCS/prompts.md)。
- [快速入门 Worker](fixture/demo-handbook/docs/task-packets/DEMO-DOCS/workers/DEMO-DOCS-01.md) 与 [独立 Reviewer](fixture/demo-handbook/docs/task-packets/DEMO-DOCS/reviews/DEMO-DOCS-01.md)。
- [故障排查 Worker](fixture/demo-handbook/docs/task-packets/DEMO-DOCS/workers/DEMO-DOCS-02.md) 与 [独立 Reviewer](fixture/demo-handbook/docs/task-packets/DEMO-DOCS/reviews/DEMO-DOCS-02.md)。
- [reply.md](reply.md)：本轮复制给用户的完整示例回复，含同一流程图、五个具体会话名称及 11 段启动/续接提示词。

计划业务文件 `docs/quickstart.md`、`docs/troubleshooting.md` 以及卡片约定的运行报告均未创建。上述计划路径不作为已存在文件的 Markdown 链接发布。

## 如何复现

1. 使用本仓库完整的 `skills/plan-agent-tasks/` 目录，使所选宿主能够读取 Skill 及相对依赖。无需为了验证本例安装调度工具。
2. 在新的隔离目录准备名为 `demo-handbook` 的输入根，只复制本例 fixture 中的 AGENTS.md 和 README.md；不要复制生成后的 `docs/task-packets/DEMO-DOCS/`。本例没有自己的 Git 元数据，不应读取外层发布仓库的分支作为目标项目状态。
3. 将此输入根指定为实施/卡片仓库 `demo-handbook`，在全新验证会话发送上面的完整原始请求。要求仅生成文件，并将最终交付回复保存在 `reply.md`；不要发送任务包中的 Main 启动提示词。
4. 检查产物仍使用目标根内 `docs/task-packets/DEMO-DOCS/`，两份文档依然是计划创建，两个叶子任务可独立验收，每个 Worker 都有独立 Reviewer。措辞无需与本例逐字相同；会话名、Task ID、路径和启动条件须在本次产物内部一致。
5. 按下节的阅读步骤复核。若未来确实要执行业务，另行准备真实仓库基线和隔离工作区，再由用户按人工模式逐个启动会话；本例没有执行这一步。

## 可复查的阅读步骤

1. 对照 fixture README 与总卡 R1–R3，再打开两张 Worker 卡，逐项核对 A1–A5、B1 都有输入、阅读操作、预期结果和计划证据位置。
2. 从总卡依次打开 Main、Worker、Reviewer、prompts 的链接，再从各角色卡返回原始 README 与 AGENTS.md；所有已存在文件链接应可读取。
3. 逐一核对五个完整会话名称在名册、卡片标题、Mermaid 标签和提示词首句中一致；Main 集成、Worker 修复和 Reviewer 复审均续接原会话。
4. 对比总卡和 reply 的 Mermaid 代码内容，以及 prompts 和 reply 的 11 个 `text` 代码块；内容应分别一致。人工模式每次启动/续接由用户触发；两分支汇合必须等两项交付和审查均通过，修复后仍需复审。
5. 检查所有实际任务卡入口按 `demo-handbook` 根可解析；计划业务文件和报告路径已标为计划创建。检查没有绝对机器路径、模板变量或虚构的实际会话 ID。
6. 检查两份计划业务文档、运行报告和 fixture 自有 Git 元数据均不存在。阅读 Main 停止点，确认无推送、合并或发布动作。

## 本次实际验证

2026-09-06，生成完成后使用临时 Python 标准库脚本读取本例 Markdown 文件，实际执行以下静态检查，进程退出码为 0。脚本只读取本例和链接目标，不是业务测试设施；复查可使用上面的阅读步骤。

| 检查范围 | 实际结果 | 能证明的范围 |
| --- | --- | --- |
| 输入和需求核对 | PASS | 先建立并实际读取两个输入文件；无需求决定缺失，已知 Git/隔离前置条件单列 |
| 文件与 Markdown 链接 | PASS：11 个 Markdown 文件，42 个链接目标存在 | 本机留存材料完整、文件相对链接可解析 |
| 会话和根相对入口 | PASS：5 个唯一会话，11 段具体提示词 | 每段有真实卡片入口、仓库、人工模式及停止点；卡片标题和会话名称一致 |
| 回复与文件一致性 | PASS：11 个提示词代码块逐字一致，1 个 Mermaid 代码块逐字一致 | reply 提供与源文件相同的图和完整具体入口 |
| 依赖与流程图文本 | PASS：8 个节点、12 条边；正常依赖无环，返修回路单独核对 | 两分支汇合条件完整，修复回原 Worker 并回原 Reviewer 复审；不证明渲染效果 |
| 需求与计划证据 | PASS | A1–A5、B1 覆盖原始需求，Worker 和 Reviewer 对应；报告均为计划创建 |
| 生成边界 | PASS | 计划业务文档、业务报告及 fixture 自有 Git 元数据均不存在；未残留模板变量或绝对机器路径 |
| Mermaid 渲染 | UNRUN | 仅核对文本，没有打开渲染器 |
| 业务实施、业务阅读验收和独立业务审查 | UNRUN | 未启动计划中的 Main、Worker 或 Reviewer |
| 自动执行、跨机器分发、提交、合并与发布 | UNRUN | 本例未执行这些动作，不能推断能力或结果 |

## 生成与业务执行的界限

生成器本次只写输入 fixture、七份任务包文件、本 README 和 reply。没有创建目标 Git 仓库、分支、worktree、远端资源或业务执行会话，也没有提交、推送、合并、发布、安装工具或检查 SHA。

生成器的静态检查不等于 Reviewer 已完成业务审查。图表示未来执行关系；卡片中的验收表是未来阅读计划。没有声称两个业务文档已写成、业务测试已通过、自动执行可用或跨机器协作已经验收。当前仅是一次人工模式生成测试，不能推出其他模式均有效。
