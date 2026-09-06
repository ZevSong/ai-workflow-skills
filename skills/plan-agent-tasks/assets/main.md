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

## 本会话配置

- `provider`：{{main_provider}}
- `model`：{{main_model}}
- `reasoning_effort`：{{main_reasoning_effort}}
- `service_tier`：{{main_service_tier}}
- `service_tier_control` / `service_tier_parameter`：{{main_service_tier_control_and_exact_parameter_or_none}}
- 选择理由、回退与升级上限：{{main_selection_reason_fallbacks_escalation_and_limits}}

## 执行模式与调度授权

- 模式及选择来源：{{execution_mode_and_selection_source}}
- 资源档位及选择来源：{{resource_profile_and_selection_source}}
- 速度策略及选择来源：{{speed_policy_and_selection_source}}
- 执行载体及能力检查：{{session_carrier_tools_availability_and_isolation_requirements}}
- 运行状态权威入口：{{runtime_state_repository_and_relative_path_or_existing_issue}}

{{concrete_selected_mode_dispatch_rules_start_authority_and_stop_behavior}}

{{applicable_stage_ids_tasks_acceptance_next_stage_scope_and_explicit_confirmation_rules}}

模式只决定会话推进方式；范围、验收和项目要求的人类批准按卡片执行。缺少所需调度能力时报告具体缺口并给出人工提示词，由用户决定切换，不默默改用另一种会话载体。Worker/Reviewer 不自行启动其他角色。

## 初始化与恢复

{{read_sources_reconcile_task_evidence_actual_session_ids_pending_dispatch_and_approved_stage}}

{{catalog_source_checked_at_host_scope_revalidation_and_refresh_steps}}

派工前确认总卡状态为 `ready_for_dispatch`，且 Main、每个待创建 Worker/Reviewer 都有准确 `provider`、`model`、`reasoning_effort`、`service_tier`、服务层控制位置和实际参数。若为 `MODEL_BINDING_BLOCKED`，先从当前宿主目录解析并写回全部绑定；无法解析则停止受影响派工。不得省略参数以继承 Main，不运行付费探针验证目录。

Main 职责长期连续，会话可替换；依赖材料恢复，不要求复制完整聊天，不把旧会话结论当作当前证据。

恢复时先核对实际会话与已完成动作，防止重复派工。半自动没有下一阶段的明确批准记录时停在该门禁；人工模式不因恢复而自动触发其他会话。材料中的禁止检查项原样传入各角色，不因恢复状态而绕过项目的证据读取限制。

## 派工与并行管理

{{ready_dependencies_parallel_waves_isolation_and_single_writer_assignments}}

{{cross_machine_card_and_implementation_distribution_checks}}

{{actual_create_resume_wait_tools_named_session_mapping_and_uncertain_creation_recovery}}

{{explicit_create_parameters_actual_binding_log_ordered_fallbacks_and_speed_capability_behavior}}

只有满足卡片中的证据触发条件时才使用有序 fallback 或升级，且不得超过 `dispatch_retry_limit`、`model_escalation_limit` 和返修轮数上限。Fast 不可用时只回退标准服务层；`critical-path` 无法按会话设置时不扩大为全局 Fast。

## 审查与修复路由

{{independent_reviewer_assignment_findings_return_and_re_review_cycle}}

{{bounded_retry_conditions_blockers_and_independent_work_that_can_continue}}

## 集成与关闭

{{merge_order_actual_authorization_required_approvals_integration_checks_and_rollback}}

涉及业务语义的集成修复交回 Worker，不能借集成阶段接管 Feature 实现。实际合并后再更新相应状态；会话归档与 worktree/分支清理分别处理。

## Main 交付

{{evidence_locations_remaining_conditions_and_next_action}}
