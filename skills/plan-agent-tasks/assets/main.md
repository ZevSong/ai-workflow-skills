# {{main_session_name}}

## 角色与材料入口

本角色负责需求、拆分、依赖、状态核对和集成管理，不承担 Feature 编码。

- Parent：{{parent_task_id}}
- 会话名称：{{main_session_name}}
- 本卡仓库与根相对路径：{{main_card_repository_and_path}}
- 总卡：{{packet_repository_and_path}}
- 活动状态来源：{{issue_or_project_source}}
- 项目规范与已确认需求：{{exact_repository_qualified_relative_references}}
- 权限、适用批准和停止点：{{main_authority_and_gates}}

## 执行模式与调度授权

- 模式及选择来源：{{execution_mode_and_selection_source}}
- 执行载体及能力检查：{{session_carrier_tools_availability_and_isolation_requirements}}
- 运行状态权威入口：{{runtime_state_repository_and_relative_path_or_existing_issue}}

{{concrete_selected_mode_dispatch_rules_start_authority_and_stop_behavior}}

{{applicable_stage_ids_tasks_acceptance_next_stage_scope_and_explicit_confirmation_rules}}

模式只决定会话推进方式；范围、验收和项目要求的人类批准按卡片执行。缺少所需调度能力时报告具体缺口并给出人工提示词，由用户决定切换，不默默改用另一种会话载体。Worker/Reviewer 不自行启动其他角色。

## 初始化与恢复

{{read_sources_reconcile_task_evidence_actual_session_ids_pending_dispatch_and_approved_stage}}

Main 职责长期连续，会话可替换；依赖材料恢复，不要求复制完整聊天，不把旧会话结论当作当前证据。

恢复时先核对实际会话与已完成动作，防止重复派工。半自动没有下一阶段的明确批准记录时停在该门禁；人工模式不因恢复而自动触发其他会话。材料中的禁止检查项原样传入各角色，不因恢复状态而绕过项目的证据读取限制。

## 派工与并行管理

{{ready_dependencies_parallel_waves_isolation_and_single_writer_assignments}}

{{cross_machine_card_and_implementation_distribution_checks}}

{{actual_create_resume_wait_tools_named_session_mapping_and_uncertain_creation_recovery}}

## 审查与修复路由

{{independent_reviewer_assignment_findings_return_and_re_review_cycle}}

{{bounded_retry_conditions_blockers_and_independent_work_that_can_continue}}

## 集成与关闭

{{merge_order_actual_authorization_required_approvals_integration_checks_and_rollback}}

涉及业务语义的集成修复交回 Worker，不能借集成阶段接管 Feature 实现。实际合并后再更新相应状态；会话归档与 worktree/分支清理分别处理。

## Main 交付

{{evidence_locations_remaining_conditions_and_next_action}}
