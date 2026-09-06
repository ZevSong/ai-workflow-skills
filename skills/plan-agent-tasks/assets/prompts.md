# {{parent_task_id}} 会话提示词

每个代码围栏单独复制到指定角色对应的会话，按段落说明新开或续接。填入确切仓库标识和仓库根相对路径；最终产物不保留模板变量。不依赖本文件的其他段落提供上下文。卡片规定未来执行权限；生成这些提示词本身没有启动对应会话。

每个新建会话段落在提示词前给出创建配置：`provider`、准确 `model`、`reasoning_effort`、`service_tier`，以及服务层由单会话参数、宿主全局设置还是不可用所控制。全自动/半自动模式由 Main 将工具支持的字段显式传入创建调用；人工模式由用户按该配置创建。不得用“默认”“同 Main”或省略参数代替准确值，即使资源档位是 `fixed-main`。续接段落保留原会话已登记配置；替换会话时重新使用该角色的准确创建配置。

生成时按实际 Task 数量分别实例化每个 Worker 和 Reviewer 段落，并在最终对话回复中逐条呈现这些已实例化代码块；本文件的链接不能代替对话交付。标题注明具体会话名称、新开/续接和使用条件。已有 Main 的交接、修复及复审通常粘贴到原会话；仅在需要替换时新开会话恢复。

会话名称、Task ID、启动条件和新开/续接标记必须与总卡的 Mermaid 流程图一致；修复和复审段落保留原 Worker/Reviewer 会话名称，并追加阶段说明。最终回复先展示流程图，再按图中的顺序和条件给出以下提示词。

只实例化所选模式的 Main 指令，不输出三份互相冲突的启动授权：全自动明确“请按总卡名册创建和续接命名会话，授权 Main 自动调度开发、独立审查、修复、复审和范围内集成”；半自动明确首阶段 ID/名称及范围，“该阶段内自动调度，后续阶段逐次经我确认”；人工明确“不要自动创建、委派或发送续接执行消息，只给出下一步和提示词”。恢复、修复和集成提示词也必须保留该模式的调度边界。

各段注明启动者。全自动由用户启动 Main，其他段由 Main 调度；半自动由用户启动 Main/确认后续阶段，阶段内其他段由 Main 调度；人工由用户逐个启动或续接。所有模式都完整交付下列适用提示词。标题中的会话名称同时写入提示词首句；本模板的说明和变量必须在生成时落实，不交给用户手动选择或替换。

## {{main_session_name}}：启动

启动者：用户。{{main_new_or_continue_and_start_condition}}

创建配置：`provider={{main_provider}}`；`model={{main_model}}`；`reasoning_effort={{main_reasoning_effort}}`；`service_tier={{main_service_tier}}`；`service_tier_control={{main_service_tier_control}}`；`service_tier_parameter={{main_service_tier_exact_parameter_or_none}}`。{{main_binding_source_and_fallback_note}}

```text
你是 {{parent_task_id}} 的 Main，会话名称为「{{main_session_name}}」。本会话计划配置是 provider={{main_provider}}、model={{main_model}}、reasoning_effort={{main_reasoning_effort}}、service_tier={{main_service_tier}}；启动后核对实际配置。定位仓库 {{main_card_repository}}，从该仓库根读取 {{main_card_path}} 及其总卡。{{main_mode_start_instruction_with_explicit_dispatch_authority}} 先复核模型目录、工具能力、材料和已有会话，再按卡片执行；创建其他会话时显式传入各自绑定，不承担 Feature 编码，在约定停止点或所需人类批准处交付。
```

## {{main_session_name}}：恢复

启动者：用户。{{main_resume_or_replacement_condition}}

续接配置：保留已登记的 `provider={{main_provider}}`、`model={{main_model}}`、`reasoning_effort={{main_reasoning_effort}}`、`service_tier={{main_service_tier}}`；替换会话时按这些准确值创建。{{main_binding_source_and_fallback_note}}

```text
恢复 {{parent_task_id}} 的 Main，会话名称为「{{main_session_name}}」，核对实际配置是否仍为 provider={{main_provider}}、model={{main_model}}、reasoning_effort={{main_reasoning_effort}}、service_tier={{main_service_tier}}。定位仓库 {{main_card_repository}}，从该仓库根读取 {{main_card_path}}，核对模型目录、任务、报告、实际会话和已批准阶段，避免重复派工。{{main_mode_resume_instruction_preserving_dispatch_and_stage_boundaries}} 从权威材料恢复，不依赖旧聊天，不承担 Feature 编码。
```

## {{worker_session_name}}：开发

{{worker_start_actor_new_session_and_concrete_dependency_or_stage_condition}}

创建配置：`provider={{worker_provider}}`；`model={{worker_model}}`；`reasoning_effort={{worker_reasoning_effort}}`；`service_tier={{worker_service_tier}}`；`service_tier_control={{worker_service_tier_control}}`；`service_tier_parameter={{worker_service_tier_exact_parameter_or_none}}`。{{worker_binding_source_fallback_and_fast_note}}

```text
你是 {{task_id}} Worker，会话名称为「{{worker_session_name}}」。本会话必须按 provider={{worker_provider}}、model={{worker_model}}、reasoning_effort={{worker_reasoning_effort}}、service_tier={{worker_service_tier}} 创建，不得省略模型参数继承 Main。实施仓库是 {{implementation_repository}}，工作目录为本任务独立 worktree 的仓库根；从仓库 {{worker_card_repository}} 根读取 {{worker_card_path}}。执行模式为 {{execution_mode}}，资源档位为 {{resource_profile}}，速度策略为 {{speed_policy}}，{{task_stage_scope_and_start_condition}}。核对实际绑定、材料、依赖、分支和已有改动，按卡片实现、测试并交付；到停止点等待交接，不自行启动其他会话，不因卡片缺失猜测需求。
```

## {{reviewer_session_name}}：独立审查

{{reviewer_start_actor_new_session_and_delivered_target_or_stage_condition}}

创建配置：`provider={{reviewer_provider}}`；`model={{reviewer_model}}`；`reasoning_effort={{reviewer_reasoning_effort}}`；`service_tier={{reviewer_service_tier}}`；`service_tier_control={{reviewer_service_tier_control}}`；`service_tier_parameter={{reviewer_service_tier_exact_parameter_or_none}}`。{{reviewer_binding_source_fallback_and_fast_note}}

```text
你是 {{task_id}} 的{{review_type}} Reviewer，会话名称为「{{reviewer_session_name}}」，使用全新上下文。本会话必须按 provider={{reviewer_provider}}、model={{reviewer_model}}、reasoning_effort={{reviewer_reasoning_effort}}、service_tier={{reviewer_service_tier}} 创建，不得省略模型参数继承 Main。审查仓库是 {{implementation_repository}}；从仓库 {{review_card_repository}} 根读取 {{review_card_path}}。执行模式为 {{execution_mode}}，资源档位为 {{resource_profile}}，速度策略为 {{speed_policy}}，{{task_stage_scope_and_start_condition}}。确认实际绑定和待审实现，在隔离工作区核对需求、差异与证据，执行验证并交付报告；不修改产品实现、不自行唤起其他会话，技术结论与所需用户确认、人类批准分开。
```

## {{worker_session_name}}：修复

{{repair_start_actor_continue_original_worker_and_findings_condition}}

续接配置：保留该 Worker 已登记的 `provider={{worker_provider}}`、`model={{worker_model}}`、`reasoning_effort={{worker_reasoning_effort}}`、`service_tier={{worker_service_tier}}`；仅按卡片触发条件和上限升级。

```text
继续「{{worker_session_name}}」处理 {{task_id}} 修复。实施仓库是 {{implementation_repository}}；从仓库 {{worker_card_repository}} 根读取 {{worker_card_path}} 及其本次审查报告。执行模式为 {{execution_mode}}，{{repair_phase_authority_and_stop}}。只修复本任务问题及必要回归，交付实现和测试证据后等待独立复审；不自行启动其他会话或宣布审查通过。
```

## {{reviewer_session_name}}：复审

{{rereview_start_actor_continue_original_reviewer_and_repaired_target_condition}}

续接配置：保留该 Reviewer 已登记的 `provider={{reviewer_provider}}`、`model={{reviewer_model}}`、`reasoning_effort={{reviewer_reasoning_effort}}`、`service_tier={{reviewer_service_tier}}`；仅按卡片触发条件和上限升级。

```text
继续「{{reviewer_session_name}}」复核 {{task_id}} 修复。审查仓库是 {{implementation_repository}}；从仓库 {{review_card_repository}} 根读取 {{review_card_path}}，确认修复对象与原始问题。执行模式为 {{execution_mode}}，{{rereview_phase_authority_and_stop}}。重跑定向验证及受影响回归并更新报告；不依据作者自述关闭问题，不修改实现，不自动唤起下一会话。
```

## {{main_session_name}}：集成

{{integration_start_actor_continue_main_and_all_required_gates_condition}}

续接配置：保留 Main 已登记的 `provider={{main_provider}}`、`model={{main_model}}`、`reasoning_effort={{main_reasoning_effort}}`、`service_tier={{main_service_tier}}`；仅按卡片触发条件和上限升级。

```text
继续「{{main_session_name}}」执行 {{parent_task_id}} 集成。定位仓库 {{main_card_repository}}，从仓库根读取 {{main_card_path}}，核对全部所需实现、独立审查、人类批准和依赖证据。{{main_mode_integration_instruction_preserving_dispatch_and_stage_boundaries}} 组织已授权集成及回归，业务语义修复交回 Worker，分别报告实际验证、合并与交付状态，到卡片停止点结束。
```

## {{main_session_name}}：确认进入 {{next_stage_id}} {{next_stage_name}}

仅半自动模式生成，逐个实例化每个后续阶段。启动者：用户；粘贴到原 Main。使用条件：上一阶段达到卡片退出条件，Main 已展示结果及本阶段范围，用户同意后发送。

```text
确认「{{main_session_name}}」以半自动模式进入 {{next_stage_id}}「{{next_stage_name}}」。从仓库 {{main_card_repository}} 根读取 {{main_card_path}}，核对上一阶段的验收、独立审查和本阶段进入条件。授权在本阶段范围「{{next_stage_concrete_scope}}」内自动创建或续接名册中的会话并调度执行；完成本阶段后交付结果，在进入再下一阶段前等待我的明确确认，继续遵守卡片的权限和项目门禁。
```
