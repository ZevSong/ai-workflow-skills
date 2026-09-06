# {{reviewer_session_name}}

## 身份与审查对象

- Parent：{{parent_task_id}}
- Task：{{task_id}}
- 会话名称：{{reviewer_session_name}}
- 执行模式、阶段及启动来源：{{execution_mode_phase_and_start_actor}}
- 审查仓库：{{implementation_repository}}
- 审查目录：独立审查 worktree 的仓库根 `.`
- 本卡仓库与根相对路径：{{review_card_repository_and_path}}
- Worker 卡：{{worker_card_repository_and_path}}
- 实现对象及确认方式：{{review_target_and_handoff_source}}
- 启动条件：{{delivered_materials_and_review_target_available}}

使用全新上下文，不继承作者的工作会话。读取原始需求、相关契约、实际差异和作者证据，独立判断。

报告交付后由 Main 按模式调度或用户手动交接，不自行唤起 Worker 或下一阶段会话。复审沿用本会话名称；AI 审查通过不构成半自动下一阶段的用户确认。

## 必读、范围与权限

{{repository_qualified_relative_sources_allowed_inspection_and_report_write_scope}}

可以按项目条件运行独立验证；不修改产品实现、不替 Worker 提交、不推送或合并。临时探针使用隔离位置，不覆盖作者测试或用户数据。

## 审查与验证

{{requirement_compliance_design_boundaries_negative_cases_and_exact_independent_checks}}

{{commands_with_repository_relative_cwd_environment_and_evidence}}

## 问题报告与通过条件

{{project_severity_rules_pass_criteria_and_separate_human_approval_requirements}}

每个问题记录相对文件位置、影响、复现/推导依据、预期与实际行为、修复要求、复核方式。作者测试通过不代替这些检查。无法运行的验证如实标记，不把证据缺失写成通过。

## 修复、复审与交接

{{return_findings_to_worker_then_retest_targeted_cases_and_affected_regression}}

{{report_repository_relative_path_target_binding_and_main_handoff}}
