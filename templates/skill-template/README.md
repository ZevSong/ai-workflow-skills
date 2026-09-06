# Skill 编写模板

这是编写新 Skill 的起点，不是可安装的正式 Skill。

1. 复制到 `skills/<skill-name>/`，同步修改 `SKILL.md` 的 `name`，使其等于目录名。
2. 替换模板变量，删除不适用内容。说明具体触发场景、输入、输出、权限和停止条件。
3. 将本 README 改为用户文档，包含用途、调用方式、输入输出示例、依赖、已验证环境和限制。
4. 按需增加 `references/`、`assets/`、`scripts/`；脚本需要真实验证，不为齐全而创建空目录。
5. 添加 `examples/` 与至少一个输入及预期行为案例；复制适用的 MIT 许可证到独立 Skill 目录。
6. 从仓库根运行 `python scripts/validate_skills.py`。正式 Skill 不能保留未实例化变量；生成用的 `assets/` 模板除外。

保持 Skill 自包含：用户复制该目录后，不应还需要访问此编写模板或仓库的维护脚本才能执行工作流。
