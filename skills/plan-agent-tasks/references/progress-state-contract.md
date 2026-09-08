# Progress state contract v1

本契约供 Main 提交结构化状态，供存储、服务与 HTML 渲染器消费。Python 核心位于 `assets/dashboard/panel_core/contract.py`，仅使用标准库，不读写文件、不访问网络、不读取系统时间。它校验 Main 的结论，不代替 Worker 交付、独立审查或实际验收。

## Public Python interface

```python
class ContractError(ValueError): ...
validate_state(state: dict) -> None
initial_state(plan: dict, now: str) -> dict
apply_event(state: dict, event: dict, received_at: str) -> dict
ensure_done_allowed(state: dict, task_id: str) -> None
```

调用方将 Skill 的 `assets/dashboard` 放入模块搜索路径后，从 `panel_core.contract` 导入以上五个接口。`_schema.py` 是私有校验实现，调用方不依赖其内部符号。

- `validate_state` 接受完整快照，错误抛出 `ContractError`；不修改输入。
- `initial_state` 接受下述九个计划字段，深复制后添加元数据。只接受 planned 初始化；已核对旧状态通过未来 import 命令直接调用 `validate_state`，不能用初始化伪造执行历史。
- `apply_event` 深复制、应用全部操作、校验、追加记录，成功后返回新快照。错误时输入不变。
- `ensure_done_allowed` 的前提是完整状态已通过结构校验，单独检查指定任务的全部完成条件。

## Snapshot fields

对象必须包含列出的全部字段，不接受额外字段。所有 ID 为非空字符串；对象键是身份，标题不作为身份。字符串列表不允许重复 ID。整数不接受布尔值。未观察到的时间或实际值使用 `null`。

时间使用带时区的 ISO 8601 UTC，接受 `2026-09-08T08:00:00Z`、`2026-09-08T08:00:00+00:00` 及小数秒；拒绝无时区、非零偏移及无效日期。

| 顶层字段 | 值 |
| --- | --- |
| `schema_version` | 整数 `1` |
| `tool_version` | 字符串 `0.1.0` |
| `seq` | 非负递增整数；只由工具写入，跨 run 继续递增 |
| `packet`、`source`、`main` | 见下表 |
| `tasks`、`sessions`、`stages`、`checks`、`evidence` | 以对应身份为键的对象；没有阶段时 `stages={}` |
| `dependencies` | 前置条件列表，无环且同一 from/to 不重复 |
| `generated_at` | 工具成功生成时间，必填 UTC 时间 |
| `observed_at` | Main 最近核对时间或 null；HTTP 读取不更新 |
| `events` | 本轮已接受事件记录列表 |
| `history` | 按运行顺序存放的旧轮次完整快照，每项去掉 `history` 字段，禁止嵌套历史 |

### Packet, source, Main

| 对象 | 全部字段及约束 |
| --- | --- |
| `packet` | `id/title/stop_condition` 非空字符串；`mode` 为 `auto/semi-auto/manual`；`run_number/plan_revision` 为正整数；`lifecycle` 为 `planned/running/waiting_user/blocked/finished`；`stage_id` 为已登记阶段 ID 或 null |
| `source` | `mode` 为 `local/projection`；`reference` 见引用格式；`available` 为布尔值；`checked_at` 为 UTC 时间或 null |
| `main` | `logical_id` 为非空字符串且不与角色 ID 重复；`session_id` 为真实 ID 或 null；`status` 为 `planned/running/waiting_user/blocked/finished/stopped/unknown`；`observed_at` 为 UTC 时间或 null |

`main.set` 设置五种 lifecycle 同名状态时同步 `packet.lifecycle`；设置 `stopped` 时将 lifecycle 设为 `blocked`，表示明确停止，允许下一次显式 `run.start`。`unknown` 不改变已知 lifecycle。面板不能因此创建任何会话。阶段指针在初始化/导入时登记，也可用 `packet.set` 切换到已登记阶段或清为 null；它只更新当前阶段展示，不改变任何阶段批准或执行授权，计划替换须保持其引用有效。

### Task, session, stage, check, evidence

| 对象 | 全部字段及约束 |
| --- | --- |
| Task | `id` 等于对象键；`title` 非空；`stage_id` 为阶段 ID 或 null；`status` 见下文；`round` 正整数；`progress/next_action` 为字符串，可为空；`progress_at` 为时间或 null；`blocker` 为非空说明或 null，blocked 必须有说明；`session_ids` 为本任务逻辑角色 ID 列表；`required_check_ids` 为本任务非空检查 ID 列表 |
| Session | `task_id` 存在；`role` 为 `worker/reviewer`；`planned_name` 非空；`actual_name/actual_id` 为非空字符串或 null；`host_status` 为 `planned/running/idle/waiting_user/blocked/completed/failed/stopped/unknown`；`observed_at` 为时间或 null；`round` 为不超过所属任务轮次的正整数；`planned_model/actual_model` 见下文；`replaces` 为同任务、同角色的另一个逻辑角色 ID 或 null，替换关系不得形成环 |
| Stage | `title` 非空；`task_ids` 为成员任务 ID 列表，与 Task.stage_id 双向一致；`status` 为 `pending/active/waiting_approval/blocked/done/cancelled`；`approved` 布尔值；`approval_evidence_ids` 引用已有证据，approved=true 时非空 |
| Check | `task_id` 存在；`kind` 为 `delivery/review/approval/test/integration/acceptance`；`role_id` 为本任务角色 ID 或 Main.logical_id，review 必须是 reviewer；`round` 为不超过任务轮次的正整数；`applicable` 布尔值；`result` 见下文；`evidence_ids` 引用已有证据；`not_applicable_reason` 非空字符串或 null |
| Evidence | `title` 非空；`reference` 见引用格式 |

Task.status 为 `pending/ready/implementing/fixing/validating/awaiting_review/reviewing/waiting_approval/blocked/failed/done/cancelled`。状态与验证结论不混用。

模型为 `null` 或含 `provider/model/reasoning_effort/service_tier` 四个字段的对象，每个字段为非空字符串或 null。未知实际模型保持 null，禁止拿计划模型当实际观察。Main 与所有 Session 的非空实际 ID 必须唯一；Worker 与 Reviewer 不能共用同一个实际会话。

适用 Check.result 为 `PASS/FAIL/UNRUN/BLOCKED`，且 exemption reason 必须为 null。不适用检查必须 `applicable=false/result=null`，并提供 `not_applicable_reason`。批准检查 PASS 须有证据。

`done` 仅当所有适用 required_check_ids 都属于任务当前轮次、result=PASS 且 evidence_ids 非空并存在时允许；有明确原因的不适用检查可满足条件。不适用检查沿用显式豁免，不额外要求轮次相同。交付、多个 Reviewer、测试、集成、批准与验收各自独立，任何一项不能自动推导其他维度。

### References and dependencies

引用只有两种形式：

```json
{"repository": "demo", "path": "reports/result.md"}
```

```json
{"url": "https://example.com/report"}
```

仓库路径必须为相对路径，不含根路径、盘符、空路径段或 `.`/`..`；接受普通反斜杠分隔但不改变原字符串。URL 必须为 HTTP(S)，包含主机，不嵌入用户名/密码。状态中不放凭据或原始聊天。契约不检查文件存在性；包内证据读取还须由服务核对允许读取范围，其他引用仅展示定位信息或真实远程链接。

每个依赖为 `{"from": "DEMO-001", "to": "DEMO-002", "required_check_ids": []}`。两端任务必须存在；非空检查列表只能引用前置任务的检查；空列表表示前置任务必须 done。契约校验引用与 DAG；就绪状态的计算由后续展示/调度层按该约定完成，工具本身不派工。

## Initialization

初始化计划只包含 `packet/source/main/tasks/sessions/stages/checks/evidence/dependencies`。初始 run_number、plan_revision 和任务/角色/检查 round 均为 1；packet.lifecycle 与 Main.status 为 planned；Task.status 为 pending；Session.host_status 为 planned；Stage.status 为 pending 且未批准；适用检查为 UNRUN，不适用检查允许有明确豁免。实际会话/模型/观察值、任务 progress_at、blocker、session.replaces 均为空，证据对象和所有证据列表为空。source 可记录已有来源检查时间。

工具添加 schema_version、tool_version、seq=0、generated_at=now、observed_at=null、events=[]、history=[]。展示 fixture 应在复制的测试包中经后续事件模拟，不作为真实执行证据。

## Events and operations

```json
{
  "event_id": "DEMO-001-start",
  "expected_seq": 0,
  "occurred_at": "2026-09-08T08:00:00Z",
  "observed_at": "2026-09-08T08:00:00Z",
  "summary": "开始实施 DEMO-001",
  "ops": [
    {"type": "task.set", "id": "DEMO-001", "changes": {"status": "implementing", "progress": "编写文档", "next_action": "完成首稿"}}
  ]
}
```

`event_id/summary` 非空，`expected_seq` 非负整数，`occurred_at` 必填 UTC，`observed_at` 为本次 Main 核对时间或 null。允许 `ops=[]` 作为 Main 核对心跳或纯历史报告。

| 操作 | 形式与限制 |
| --- | --- |
| `task.set` | `type/id/changes`，可带非空 `reason`；不可改 `id/stage_id/session_ids/required_check_ids`。round 必须增加且 reason 必填。进度、状态、阻塞或轮次改变时，缺省 progress_at 使用 occurred_at |
| `session.set` | `type/id/changes`；不可改 `task_id/role/replaces`；轮次不能倒退；缺省 observed_at 使用 occurred_at |
| `stage.set` | `type/id/changes`；不可改 task_ids；批准仍须有已有证据 |
| `check.set` | `type/id/changes`；不可改 `task_id/kind/role_id`；轮次不能倒退；提高轮次必须显式提供 result 和 evidence_ids，不能把旧 PASS 自动抬到新轮次 |
| `evidence.put` | `type/id/evidence`；可登记新证据，已有 ID 仅接受完全相同内容，防止覆盖历史定位 |
| `main.set` | `type/changes`；不可改 logical_id；观察时间不能倒退；状态到 lifecycle 映射见前文 |
| `source.set` | `type/changes`；只允许 available、checked_at，核对时间不能倒退 |
| `packet.set` | `type/changes`；changes 只允许 stage_id，值为已登记阶段 ID 或 null；只更新当前阶段展示，不改变批准/授权。不可改身份、标题、模式、lifecycle、运行号、计划修订号、停止条件或来源 |
| `plan.replace` | `type/plan`；plan 必须完整包含 tasks/sessions/stages/checks/dependencies 五项；规则见下文 |
| `run.start` | `type/plan`；plan 为完整初始化计划，必须单独占用一个事件 |

不存在的任务、角色、阶段、检查不能通过 set 隐式创建，只能通过 plan.replace 登记。检查与证据可在同一原子事件内按任意顺序登记，最终快照统一校验。

Main 的顶层核对时间不能倒退，非空 event.observed_at 同时更新 Main.observed_at。较旧报告可用原 occurred_at 与当前 Main observed_at 接受：比已有 task.progress_at 或 session.observed_at 更旧的操作只记录原文，不覆盖当前观察；任务轮次倒退仍拒绝。来源时间和接收时间分别保留，不以接收时间冒充报告发生时间。

接受后追加记录：

```json
{
  "event_id": "DEMO-001-start",
  "seq": 1,
  "occurred_at": "2026-09-08T08:00:00Z",
  "received_at": "2026-09-08T08:00:01Z",
  "summary": "开始实施 DEMO-001",
  "body": {"event_id": "DEMO-001-start", "expected_seq": 0, "occurred_at": "2026-09-08T08:00:00Z", "observed_at": "2026-09-08T08:00:00Z", "summary": "开始实施 DEMO-001", "ops": []}
}
```

上例 body 为结构示意；实际记录始终深复制完整原始事件，不改写 ops。record.seq 等于 body.expected_seq+1；事件记录按序递增。generated_at 使用 received_at；HTTP 读取不修改这些字段。

相同 event_id 与完全相同更新体先于 expected_seq 去重，返回当前快照的独立副本，保留原接受记录的 seq/received_at；即使之后已有其他更新，也不回滚当前状态。同 ID 不同内容拒绝；其他旧 expected_seq 冲突。去重范围包含已归档轮次。返回值是快照，不是独立的 HTTP 接受回执。

### Plan replacement and new runs

plan.replace 一次替换全部五项定义、plan_revision 加一，保留 evidence、events、history 和运行编号。已执行对象不得移除：执行过的任务保留并按范围决定设为 cancelled，检查/会话/阶段保留其身份供历史查看。已有会话身份与实际观察保持一致；已有检查 round/result/evidence_ids 原样保留，之后通过 check.set 另行提交复核结果。

完成要求列表、所属阶段、入站依赖或所需检查语义改变时，受影响任务必须提高 round；旧检查结果保持原轮次。改变后不能凭旧 PASS 保持 done，需先回到 fixing 等状态。新增角色/检查使用新逻辑 ID；删除未执行对象仍须满足所有引用约束。保留的检查定义若要从适用转为豁免并改变结果，可在已登记对象上通过后续 check.set 显式提交；改变完成要求的计划应先提升任务轮次。

run.start 只允许 lifecycle=finished 或 Main.status=stopped；packet.id、source.mode/reference 不变，run_number 必须恰好加一。新计划的 plan_revision 重新为 1，其余遵循 planned 初始化约束。工具先将旧快照去掉 history 后追加到历史，保留更早历史，再开始新轮次；seq 跨 run 递增，新轮次 events 从本次 run.start 记录开始。恢复现有 Main 继续使用当前快照，不调用 run.start。

## Storage boundary

后续存储层的 `runtime/panel.json` 保存 packet_id、source_mode、权威引用与目标状态文件名，不保存任务进度。read_state 按配置选择 state.json 或 view.json，不能按修改时间猜测权威；init/import 必须拒绝覆盖现有目标。旧版权威文件可保持为来源并通过 projection 写 view.json。这些文件操作不属于本纯函数模块。

Worker 交付、独立审查、任务 done 与运行 finished 分开记录。面板显示的 PASS 只证明对应维度有 Main 提交的结构化结果，不证明发布、部署或真实业务验收。轮次、修订号与 seq 使用整数版本，不需要检查任何内容摘要。
