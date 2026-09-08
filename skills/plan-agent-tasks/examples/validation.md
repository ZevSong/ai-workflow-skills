# 验证记录

本页记录可复查的验证范围。它不代表所有 Agent 或真实业务流程已通过。

## 环境与复现

- 日期：2026-09-06 至 2026-09-08。
- 本地环境：Windows / PowerShell，Python 3.14.6，PyYAML。
- 维护命令从发布仓库根执行：`python scripts/validate_skills.py`、`python -m unittest discover -s tests -v`。
- `scripts/` 和 `tests/` 属于开源仓库的维护工具，不是使用本 Skill 的运行依赖；单独安装 Skill 不需要这些文件。

## 实际范围

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
