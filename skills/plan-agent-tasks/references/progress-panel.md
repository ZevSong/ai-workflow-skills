# 任务包进度面板接入

生成每个任务包时必读本页和 [v1 状态契约](progress-state-contract.md)。CLI 以 [随包工具说明](../assets/dashboard/README.md) 为准。Skill metadata 版本为 `0.3.0`，状态与 CLI 的 `tool_version` 独立保持 `0.1.0`；这不表示已发布。

## 生成阶段：只生成材料

1. 确定任务包所属仓库、仓库根相对包路径、Main、全部具名 Worker/Reviewer、阶段、依赖和完成检查。生成前检查已有包；已有状态按恢复/修订处理，不能覆盖成新计划。
2. 将 Skill 的 `assets/dashboard/` **完整原样复制**到包的 `dashboard/`，保留 `panel.py`、README、`panel_core/` 的所有模块（包括私有模块）及 `resources/`。不要复制运行缓存。不编写或改写 HTML、CSS、JavaScript、图布局代码，也不运行维护仓库的 scripts 或依赖其模块。生成任务包的 Agent 与 Main 都只写结构化数据、卡片和报告。
3. 将本页的 Main 操作与错误处理规则落实到 `main.md`，把 v1 契约复制到包内 `progress-state-contract.md`，在 Main 卡链接该契约和 `dashboard/README.md`。这些资料随包迁移，执行者不需要已安装 Skill。登记每位角色独占的报告路径和已有交付渠道；报告在执行时才创建。
4. 按 v1 契约生成 `runtime/plan.json`，只包含 `packet/source/main/tasks/sessions/stages/checks/evidence/dependencies` 九项，不带工具生成的元数据。将全部 Task、角色、阶段和依赖逐项实例化；每个任务有非空完成检查列表，分别包含 Worker delivery、每个所需独立 Reviewer review 及适用的测试、集成、批准、验收。检查角色引用确切逻辑 ID，不能合成一个总 PASS。
5. 新计划严格为 planned：packet/Main 为 planned、Task 为 pending、Session 为 planned、阶段为 pending 且未批准，run/plan_revision/各 round 为 1；适用检查为 UNRUN，无实际会话 ID、实际模型、观察时间、证据、阻塞或历史。已计划的模型绑定填入 planned_model；模型未知保持 null 并在卡片保留 MODEL_BINDING_BLOCKED，不能编造值。尚未观察的值用 JSON null，不能用字符串“待创建”。阶段授权仅在真实用户启动/确认之后由 Main 记录。
6. 本地权威使用 `source.mode=local`，`reference={"repository":"实际仓库标识","path":"实际包路径/runtime/state.json"}`，路径必须以 `runtime/state.json` 结尾。工具创建 `runtime/panel.json` 配置和 `runtime/state.json`；不要手写配置，也不要把 packet.md 当成权威锚点。若项目已有 Issue、YAML 等权威来源，使用 `projection` 并保持原引用，工具写 `runtime/view.json`；它只是缓存，不迁移或争夺原来源的权威。
7. 从包所属仓库根调用复制后的入口 `init --input`，再 `status`，核对 seq=0、planned、服务未运行、首份 HTML 已生成。命令参数必须是确定的仓库根相对路径，含空格时分别引用参数；角色文字放 JSON 文件。此阶段**不调用 start/serve，不启动 Main、Worker、Reviewer 或业务服务**。Python 缺失或工具失败时记录面板生成 BLOCKED/FAIL 及实际产物，不手写替代网页、不声称面板已交付。

以下为虚构 `demo` 仓库 `docs/task-packets/DEMO` 的路径示例；生成时把包路径落实到总卡、Main、每个具体角色及全部启动/恢复/修复/复审/集成/阶段确认提示词，不让用户替换变量：

```sh
python docs/task-packets/DEMO/dashboard/panel.py init --input docs/task-packets/DEMO/runtime/plan.json
python docs/task-packets/DEMO/dashboard/panel.py status
```

交付离线入口 `docs/task-packets/DEMO/dashboard/index.html` 和来源定位，说明它是 planned 快照。查看该 HTML 无需 Python；初始化、更新、导出与本地实时预览需要 Python 3.11+ 标准库。浏览器每 2 秒检查新数据，不会采集角色状态；主动作业超过 120 秒没有 Main 核对时显示实际延迟。

## Main：启动、恢复、导入、重跑

- **首次启动已生成包**：读卡片、权威材料、报告及实际宿主状态；先 `status`，复用已有 planned 状态。通过 `publish --input` 登记本 Main 的真实 session_id、状态与本次 UTC 核对时间（`main.set`）；尚不可见的真实身份保持 null 并说明缺口，不能虚构。然后 `start --open`，核对返回的真实 URL、packet_id、tool_version 和 instance_id 与 `/api/identity` 一致；只交付实际验证过的入口。`browser_opened=false` 时如实提供已验证 URL。**不盲目再次 init**。
- **恢复**：先确认旧 Main 已停止维护共享状态，或确认是同一 Main 续接；旧写入者不能确认已停止时只读核对并报告阻塞。读取现有 state/view、事件、历史、角色报告、实际会话和获准阶段，协调未完成动作后 publish。保留 run_number、seq 连续性、history 和已有服务；`start --open` 会核对身份并复用服务，不先 stop 重建。恢复不用 init/import/run.start，不重复创建会话。
- **旧包没有面板**：先复制固定资源与契约；Main 从原权威材料及报告核对完整 v1 快照，保留实际工作轮次、当前任务结果、历史及证据定位，再 `import --input`。已有 YAML/Issue 等权威来源用 projection；不可观测值保持 null，缺失的历史说明缺口，不能伪造成功记录或清空原历史。import 拒绝覆盖已有目标，且不启动服务。完成后按启动规则核对和预览。
- **明确重新执行**：只有用户明确要求新一轮，且旧 lifecycle=finished 或 Main.status=stopped 时，才用单独事件的 `run.start`。新计划 run_number 恰好加一、plan_revision 重回 1，其余遵循 planned；工具归档旧轮次，seq 继续递增。日常恢复、失败重试、Main 换人均不属于重跑。
- **计划调整**：使用完整 `plan.replace`，保留已执行对象、证据和历史，提升受影响任务 round 并重新核对旧检查；不得手改状态文件。`packet.set` 仅切换已登记 stage_id 的展示指针，不构成 stage 批准。

## Main：持续观察与安全提交

Main 是共享状态的唯一维护者；Worker/Reviewer 只写各自报告，通过已有交付渠道向 Main 提交。Main 先核对权威来源和报告，projection 模式先按原渠道维护权威，再 publish 核对后的投影；不能把 view.json、HTML 或浏览器当作独立事实来源。

在真实会话启动/续接/结束、Worker 交付、Review 结论、修复、阻塞解除、批准、阶段切换、集成和结束等关键事件后发布。等待期间在宿主允许执行观察时目标每 30 秒核对一次，使用实际状态工具和报告；宿主暂停/不支持后台观察时明确说明，保留实际时间差，不补造 30 秒记录。只有真实核对才可更新 observed_at；HTTP 请求、工具等待结束、计时器触发本身不等于观察。旧报告保留原 occurred_at 和 round，Main 本次核对另用 observed_at，不能把计划模型复制为实际模型。

在确定的 `runtime/events/` 下为每次更新写独立 JSON 文件（含 event_id、expected_seq、occurred_at、observed_at、summary、ops）。普通更新调用 publish；每个 event_id 与完整更新体一经发送即不可变。响应不确定时原文件原样重试，工具先去重再校验序号；同 ID 不同内容拒绝。发生序号冲突时先 status 并读当前事件、权威状态与报告，识别已接受/过期/新动作；需要提交新的核对结果时生成新 ID 与新事件文件，**不能只改 expected_seq 盲重试**。

```sh
python docs/task-packets/DEMO/dashboard/panel.py publish --input docs/task-packets/DEMO/runtime/events/DEMO-observation-001.json
python docs/task-packets/DEMO/dashboard/panel.py start --open
python docs/task-packets/DEMO/dashboard/panel.py export
python docs/task-packets/DEMO/dashboard/panel.py stop
```

| 退出码 | Main 处理 |
| --- | --- |
| 0 | 读取 JSON 返回值；status.snapshot_exists 只表示文件存在，不能据此认定快照对应当前 seq |
| 2 | 修正输入/参数/契约；不要绕过校验直接编辑状态 |
| 3 | status、核对身份/事件/当前 seq 后协调冲突；不盲改 expected_seq，不抢另一个 Main 的写入权 |
| 4 | 来源/状态 I/O；检查真实 state_published 与 seq，可能写前失败为 false，也可能已写入后清理失败为 true；先核对再恢复 |
| 5 | 预览或独立 export 渲染故障；任务结论不因此改变，修复工具资源/环境后重试相应操作 |
| 6 | 状态已提交，state_published=true；HTML 导出阶段失败，snapshot_updated 通常 false，也可能 HTML 已替换后清理失败而为 true，读取实际 snapshot_seq，不回滚或重复业务动作 |

code 4/6 不确定时用 status 核对状态；恢复资源后 export 修复 HTML，核对导出的 snapshot_seq 与当前状态。CLI 诊断在 stderr，stdout 是 JSON；不通过匹配错误文案推断写入是否发生。结束时先 publish 实际结论，再 export、核对离线快照和 seq、stop 本包预览，保留状态/历史/最终 HTML。预览仅绑定 127.0.0.1，Windows 隐藏后台窗口；无需外部 Orchestrator。

## 角色报告与权限

每位 Worker/Reviewer 独占具名报告路径，如 `demo / docs/task-packets/DEMO/reports/DEMO-001-worker.md`、`.../DEMO-001-review-a.md`。多个 Reviewer 必须有不同文件，不共享一个 review.md。报告记录 Task、逻辑角色/真实会话身份（可观察时）、任务 round、来源 UTC 时间、进度/里程碑、阻塞或无阻塞、下一步、对应维度 result（PASS/FAIL/UNRUN/BLOCKED）及带仓库锚点的证据。续报按轮次/时间追加，保留旧结论，不能无记录覆盖。

角色只在自己的实施/审查工作区写其获准报告，按任务已有报告交付渠道传给 Main；路径相同不表示文件共享，不要求读取 Main 工作区，也不授权额外发送消息。Main 核对接收的材料后更新共享状态，跨仓/包外证据保留原引用；不要为点击方便伪装成包内路径。所有角色卡及提示词写明其报告仓库、相对路径和具体交付渠道，明确禁止 Worker/Reviewer 写共享 runtime/state.json、view.json、panel.json 或调用 publish。

交付、独立审查、任务 done 和运行 finished 分别记录。面板的 PASS 只对应 Main 已提交的该检查维度；工具不审查代码、不创建角色、不授予下一阶段或合并/发布批准。人工、全自动、半自动的调度权限以及模型资源/速度三个独立轴均保持卡片约定。
