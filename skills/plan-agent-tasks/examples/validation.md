# 验证记录

本页记录可复查的验证范围。它不代表所有 Agent 或真实业务流程已通过。

## Task 6 页面、恢复与迁移实测

2026-09-09 在 Windows、Python 3.11.16、Chromium 151.0.7922.34 执行新增的真实 CLI/HTTP/浏览器合成链，详见 [面板实测验收记录](progress-panel/verification.md)。

| 检查 | 状态 | 实际证据与界限 |
| --- | --- | --- |
| 合成完整生命周期和完成门禁 | PASS | 真正启动两个包的服务；A 的 seq 0–10 覆盖交付、审查发现、返修、当前轮双审查 PASS、等待、完成；旧轮结果不能满足 done |
| 真实 HTTP 更新与恢复 | PASS | 11 个自动轮询显示样本最大 1859 ms；视图保留、格式错误和旧 seq 保留最后有效页面、原来源恢复均实测；这是显示时延，不是角色采集频率 |
| 实例隔离与 Main 新鲜度 | PASS | 停 A 后 B 仍可读取；HTTP 成功不刷新 Main 来源时间，181 秒过期时任务仍 implementing；最终服务与浏览器均关闭 |
| 阻断网络离线与中文/空格搬迁 | PASS | 服务关闭后原包和搬迁包的 file 页面均可读，HTTP(S) 请求为 0；搬迁后 status/export 不改变原状态 |
| 旧来源保留和完整 v1 投影导入 | PASS（本地机制） | legacy state.json 保留原字节，view.json 与导入快照完整相等；没有实际外部平台连接 |
| 当前本地实际角色/恢复 | PASS（受限文档任务） | 独立生成完整 auto 包、实际 Worker 交付、独立文档 Reviewer 零发现、Main 单独验收；Main A 中断后 Main B 复用原 Worker/run/plan/service，最终 seq 7，无重复派工/事件 |
| 真实前台页面显示 | PASS | seq 2–7 共 6 个自动轮询样本最大 1977.842 ms，seq 1 初次加载排除；实际最终离线快照断页面网络可读、零 HTTP 请求，服务/浏览器均回收 |
| Main 30 秒核对目标 | FAIL（本次未全程达到） | 外部报告产生→Main 首次可见为 82.863–108.121 秒，可见→实际核对为 26.473–156.895 秒；包括写报告、交付、调度及核对，不能当作浏览器延迟；刻意恢复窗口单独说明 |

此处更新后续实测范围；下方 Task 5 的 UNRUN 是当时任务的证据边界。CI、合并、部署、发布、其他宿主和真实跨机器仍分别保持 UNRUN。

## v0.3.0 面板接入的当前本地验证

本节为 2026-09-08 至 2026-09-09 的 Task 5 接入检查，Windows / PowerShell、Python 3.11.16、PyYAML。Skill metadata=0.3.0 与 panel tool_version=0.1.0 分开记录；没有据此执行发布。未改面板 Python 实现、HTML/CSS/JavaScript 或图布局资源。

| 检查 | 状态 | 实际证据与界限 |
| --- | --- | --- |
| 旧 Skill 同请求生成行为 RED | FAIL（新增面板要求） | 主控在独立上下文使用原人工任务包请求，得到总卡、Main、提示词及 Worker/Reviewer 卡，但 HTML=0、面板工具=0；这不否定旧生成范围 |
| 新分发测试 RED | FAIL（预期缺口） | 修改指引前运行 test_distribution.py：19 项中 1 项失败，真实 ZIP 缺少 references/progress-panel.md；其余 18 项通过 |
| 复制包 CLI 与真实 ZIP 迁移 | PASS | test_panel_integration.py 共 11 项，23.664 秒；新增测试真实打包/解压到中文及空格目录，再复制 dashboard，改变 cwd 并以屏蔽维护模块的子进程运行 init/export/status，seq=0、planned、无实际身份、无服务、导出不改状态 |
| 完整 Python 回归及分发 GREEN | PASS | 113 项，29.356 秒；包含上面的分发测试和迁移闭环，以及契约、存储、渲染、回环预览和 CLI 既有测试。不是 CI 或业务角色执行 |
| 仓库静态检查 | PASS | 元数据、链接、围栏、自包含和可移植路径通过；不验证远程链接、Markdown 锚点或所有未来生成结果 |
| Skill 创建器基础校验 | PASS（UTF-8 模式） | Windows 默认 GBK 读取中文 UTF-8 时曾出现 UnicodeDecodeError；用 Python -X utf8 重跑得到 Skill is valid，未修改该外部校验器 |
| 独立 ZIP 命令与资源清单 | PASS | package_skill.py 实际产出 50 文件 ZIP，含 12 个 dashboard 文件、MIT 与面板接入/状态契约，无缓存或维护 scripts；迁移运行范围见上方真实 ZIP 测试 |
| 新 Skill 同请求独立生成 GREEN | PASS（人工生成限定范围） | 同一原始请求生成 1 Task、2 个 Worker/Reviewer 角色、7 段独立提示词；12 个固定 dashboard 文件和契约完整复制，真实 init/status 成功。主控产物审计 14 项 PASS：planned/seq0/run1、实际身份/模型为空、规范本地权威、HTML 与固定渲染器一致、无服务或业务启动；作者未提示预期或修复产物 |
| 本次浏览器 UI 重跑 | UNRUN | 本任务只改接入说明/模板/测试，未改网页资源；既有界面 fixture 及图像证据见 [面板案例](progress-panel/README.md)，不能扩大为新模式业务验收 |
| 真实 Main/Worker/Reviewer、三模式端到端及跨机器 | UNRUN | 生成评估不启动业务会话，目录搬迁不代表多机器并发；宿主观察频率、真实模型/Fast、批准、CI、合并、部署、发布和实机验收分别待证 |

实际维护命令从仓库根执行：

```sh
.venv/Scripts/python.exe -m unittest discover -s tests -p test_distribution.py -v
.venv/Scripts/python.exe -m unittest discover -s tests -p test_panel_integration.py -v
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe scripts/validate_skills.py
.venv/Scripts/python.exe scripts/package_skill.py plan-agent-tasks --output .superpowers/sdd/2026-09-08-task-packet-progress-panel/task-5-package-check
```

独立生成使用普通人工模式请求；评估者报告 7 个本地 Markdown 链接、模板展开/路径/JSON 检查及 12 个固定文件逐字节一致性通过。主控还核对 Main 的 planned 复用、真实身份发布、恢复确认旧 Main 停止、保留 run/history/service、单写入者和独占报告约定。首次初始化因 Python 相对路径错误未进入 CLI；第二次因 plan 位于错误检出路径返回 code 2、state_published=false，纠正路径后才初始化成功，未覆盖既有状态。这不是首次尝试全部成功。Mermaid 仅完成文本检查，实际渲染 UNRUN；生成行为 PASS 不代表业务实施、独立审查、三模式调度或真实角色通过。

真实 ZIP 测试调用本仓库 package_skill，解压完整 Skill 后复制其 dashboard；迁移后的子进程只用随包模块与 Python 标准库，PYTHONPATH 放入会抛错的 package_skill/validate_skills/panel_fixtures 同名模块，证明 CLI 没有导入维护代码。没有重复实现已有 CLI 错误分支测试，也没有为了生成网页而新增网页代码。工具运行需要 Python 3.11+；已有独立 HTML 离线查看无需 Python。

## v0.1 至 v0.2.1 历史范围

- 日期：2026-09-06 至 2026-09-08。
- 本地环境：Windows / PowerShell，Python 3.14.6，PyYAML。
- 维护命令从发布仓库根执行：`python scripts/validate_skills.py`、`python -m unittest discover -s tests -v`。
- `scripts/` 和 `tests/` 属于开源仓库的维护工具，不是使用本 Skill 的运行依赖；单独安装 Skill 不需要这些文件。

### 历史实际范围

| 项目 | 状态 | 证据与界限 |
| --- | --- | --- |
| 校验器与打包行为测试 | PASS | 18 个单元测试通过；11 个覆盖链接缺失、目录逃逸、名称不一致、机器路径、未完成模板、Mermaid 模板变量及 ZIP 迁移等，7 个覆盖模型/速度契约、关键边界与模板字段 |
| 全部公开文档的静态校验 | PASS | 本仓库校验器通过；本地 Codex Skill 创建器的基础格式校验也通过 |
| 人工模式 v0.1 任务包生成 | PASS（原有范围） | 独立生成 11 份 Markdown、5 个具名会话、11 段具体提示词；42 个文件链接可读；未包含 v0.2 模型绑定，详见 [基线案例](manual-task-pack/README.md) |
| 模型资源与 Fast 规则片段 | PASS（静态契约） | 三个独立轴、五个资源档位、关键路径 Fast、显式绑定及安全回退已进入 reference、模板和单元测试；详见 [规则案例](model-and-fast-selection.md) |
| 图与提示词在交付副本中的一致性 | PASS | 主会话再次比对 11 段提示词与 Mermaid 源码，文件和 reply 的内容分别一致 |
| 完整 Skill ZIP 异目录解压 | PASS | 29 个文件，含 MIT 许可证；实际 ZIP 解压到另一含空格和中文的临时目录后，独立目录校验通过 |
| GitHub CI | UNRUN（本地发布前快照） | 最新工作流结果以 [GitHub Actions](https://github.com/ZevSong/ai-workflow-skills/actions/workflows/validate.yml) 为准，不在此复制持续变化的状态 |
| Mermaid 模板与完整示例渲染 | PASS（限定范围） | Mermaid CLI 11.17.0 实际将 `assets/packet.md` 和人工完整示例各自渲染为 SVG；动态生成的其他模式与任意规模流程图仍 UNRUN |
| Desktop 自动调度及逐会话模型/Fast 端到端 | UNRUN | 未创建真实业务 Worker/Reviewer，未验证宿主逐会话模型或服务层参数，也未执行集成 |
| 真实多机器并发与其他 Agent | UNRUN | 单机目录迁移不代表多机器验收，格式兼容不代表宿主功能兼容 |

需求缺口、半自动、工具缺失和模型/Fast 页面均为手工编写的预期行为示例。人工 v0.1 任务包单独记录当时的实际生成方式和证据，不证明 v0.2 模型绑定或宿主调度；示例仓库中的未来业务文档、测试与会话均不据此声称完成。

## 后续验证建议

新增宿主适配时记录宿主版本、模式、输入、真实工具能力、实际生成物和未验证范围。自动模式验证应覆盖：独立工作区、审查独立性、失败返修、恢复去重、阶段确认及最终停止点。
