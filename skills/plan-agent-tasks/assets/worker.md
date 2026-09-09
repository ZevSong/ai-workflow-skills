# {{worker_session_name}}

## 身份与执行边界

- Parent：{{parent_task_id}}
- Task：{{task_id}}
- 会话名称：{{worker_session_name}}
- 执行模式、阶段及启动来源：{{execution_mode_phase_and_start_actor}}
- 实施仓库：{{implementation_repository}}
- 工作目录：本任务独立 worktree 的仓库根 `.`
- 任务卡仓库与根相对路径：{{card_repository_and_path}}
- 分支：{{project_conforming_task_branch}}
- 实现责任：本任务 Worker；独立 Reviewer：{{review_role_and_card_repository_path}}
- 前置条件：{{dependencies_and_material_availability}}
- 操作授权和停止点：{{allowed_actions_and_exact_stop}}
- `provider` / `model`：{{worker_provider_and_exact_model}}
- `reasoning_effort` / `service_tier`：{{worker_reasoning_effort_and_service_tier}}
- 服务层控制 / 实际参数：{{worker_service_tier_control_and_exact_parameter_or_none}}
- 选择理由、有序 fallbacks 与 escalation 上限：{{worker_selection_reason_fallbacks_and_finite_limits}}

只完成本卡工作及本任务授权修复，交付后按模式等待 Main 调度或用户手动交接；不自动启动 Reviewer 或其他会话。修复沿用本会话名称。

启动时核对实际配置与本卡绑定。若 Main/用户无法显式设置准确模型，或实际值不在主选及有序回退中，停止执行并报告；不得靠隐式继承继续。Fast 不可用只影响服务层，不自行切换模型、提供方或推理强度。

## 必读与输入

{{exact_repository_qualified_relative_references_and_input_contracts}}

## 交付结果与非目标

{{observable_deliverable_and_non_goals}}

## 修改范围

{{allowed_files_with_create_or_modify_labels_shared_file_owner_and_exclusions}}

## 实施步骤与对外输出

{{bounded_steps_and_consumed_produced_interfaces_without_unnecessary_internal_design}}

## 验收与验证

| 编号/需求 | 输入与操作 | 期望结果 | 验证方法或命令 | 证据 |
| --- | --- | --- | --- | --- |
{{concrete_acceptance_rows}}

{{command_repository_cwd_environment_and_actual_vs_planned_test_status}}

## 风险、回滚与受阻处理

{{applicable_risks_rollback_and_exact_escalation_conditions}}

## 交付与修复闭环

- 本角色独占进展/交付报告：{{worker_report_repository_and_path}}
- 报告交付渠道及 Main 接收方式：{{worker_report_delivery_channel}}
- 当前任务轮次：{{task_round}}

启动、里程碑、阻塞、交付和修复时更新本报告：写 Task、逻辑角色/可观察的真实会话 ID、任务 round、来源 UTC 时间、进度摘要、阻塞（或无）、下一步、对应维度的 PASS/FAIL/UNRUN/BLOCKED、带仓库锚点的证据。续报按时间/轮次追加并保留旧结论；自己的交付不能宣布独立审查通过。

只在自己实施 worktree 的获准报告路径写入，通过上述已有渠道交付；不假定 Main 与本角色共享文件，也不要求访问 Main 工作区。不写共享 runtime/state.json、view.json、panel.json，不调用 panel.py publish，不改 dashboard；由 Main 核对并维护共享状态。

{{implementation_locator_changed_files_commands_results_open_questions_report_repository_path}}

{{handoff_to_review_fix_and_re_review_boundaries}}
