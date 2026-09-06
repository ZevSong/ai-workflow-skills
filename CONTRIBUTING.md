# 贡献说明

感谢提供可复用的工作流和实际反馈。请让每次贡献围绕一个明确用途，并提供足以复查的输入、输出和验证说明。

## 新增 Skill

1. 从 `templates/skill-template/` 开始，在 `skills/<skill-name>/` 创建独立目录；目录名与 YAML 中的 `name` 一致。
2. 提供 `SKILL.md`、面向使用者的 `README.md`、适用许可证和至少一个有输入及预期行为的示例。模板目录本身不是待发布 Skill。
3. 需要的说明、模板和脚本放在 Skill 自己的目录中，不引用其他 Skill 或仓库根资源作为运行依赖。
4. 写清触发条件、适用范围、输入、输出、执行权限、缺口处理及已验证环境。默认沿用宿主的触发机制；只有工作流确需显式调用时才声明并适配该限制。
5. 在根 README 登记用途和验证范围。不要预先建立尚未实现的 Skill 空目录。

## 修改现有 Skill

- 执行规则维护在 `SKILL.md` 及其引用中，README 介绍使用方式，避免形成第二套规则。
- 触发策略、输出结构、默认模式或权限变化应在 PR 中说明，并补充相应案例。
- 示例中的卡片、会话名称、提示词、流程图和依赖必须一致。
- 仅运行静态检查时说明其范围；不要写成跨 Agent、跨机器或业务流程已经通过。
- 使用可分发的虚构/脱敏材料，不包含真实客户数据、凭据、个人机器路径或未授权转载内容。

## 提交前检查

在仓库根执行：

```sh
python -m pip install -r requirements-dev.txt
python scripts/validate_skills.py
python -m unittest discover -s tests -v
```

变更涉及单独分发时，再运行 `python scripts/package_skill.py <skill-name>`，将 ZIP 解压到另一目录，确认所有引用资源和许可证齐全。`<skill-name>` 是贡献者应替换的 Skill 目录名。

Issue/PR 说明问题、预期与实际行为、修改原因、测试环境和未验证范围。对行为变更，附最小可复现输入；文字润色不要求运行整个 Agent 流程。

## 分支与合并

从最新的 `main` 创建任务分支，通过 PR 提交变更。`main` 的保护规则要求：

- `validate (ubuntu-latest)` 和 `validate (windows-latest)` 两项 GitHub Actions 检查通过。
- 分支与最新 `main` 保持同步，所有代码审查讨论已解决。
- 使用 Squash 合并并保留线性历史；合并后自动删除任务分支。

规则同样适用于管理员，不允许直接推送、强制推送或删除 `main`。目前只有一位维护者，暂不强制另一位 GitHub 用户批准；这不替代项目或任务要求的独立 Agent 审查。后续增加维护者时可提高审批门槛。

仓库允许对单个 PR 启用 Auto-merge，等待保护条件满足后合并；启用此功能不会让所有 PR 自动合入。外部贡献者的 fork PR 工作流需要维护者批准运行。工作流令牌默认为只读，Actions 不可提交批准性 PR 审查。

Dependabot 每周检查 Python 依赖和 GitHub Actions 版本并按需提交 PR，更新同样遵守分支保护。安全问题请按 [安全报告说明](SECURITY.md) 私密提交。

## 许可与版本

贡献内容按本仓库 MIT 许可证提供；贡献者应拥有相应权利。引入第三方内容时说明来源与许可，保留必要声明；不能直接把不兼容内容重新标为 MIT。

使用仓库发布标签和发布说明记录版本；Skill 的 `metadata.version` 表示该 Skill 的版本。新增兼容内容、行为修正和破坏性变化在发布说明中分别描述，不强制所有 Skill 同步升级。
