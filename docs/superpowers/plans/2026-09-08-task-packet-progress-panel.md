# Task Packet Progress Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为每个任务包提供独立、可自动更新和离线回看的 HTML 面板，执行 Agent 只提交结构化数据。

**Architecture:** 固定网页资源与 Python 工具随 Skill 分发，再完整复制到生成的任务包。Main 是唯一状态决定者，通过工具发布结构化增量；工具负责校验、持久化、离线导出和只读预览，浏览器负责图形展示。

**Tech Stack:** Python 3.11+ 标准库；HTML、CSS、原生 JavaScript 和 SVG；现有 unittest 与 PyYAML 维护校验。运行时不增加第三方 Python 包或 Node.js 依赖。

**Spec:** [已确认的面板设计](../specs/2026-09-08-task-packet-progress-panel-design.md)。执行者须同时阅读设计和本计划。

## Global Constraints

- 每个任务包拥有独立 HTML 面板，展示本任务包的完成情况、活跃工作和执行流程。
- Main 统一维护共享状态，Worker 和 Reviewer 分别提供自己的进展与证据。
- Main 在关键执行事件后更新，等待期间目标每 30 秒核对一次；浏览器每 2 秒检查新数据，实际采集频率受宿主能力约束。
- 默认主动作业状态超过 120 秒未获 Main 核对时，显示“状态未及时同步”和实际时间差。
- Worker 交付、独立审查通过、任务完成分别记录。
- Main 恢复时延续原面板；结束后保留可离线打开的最终快照。
- 验证结论使用 `PASS`、`FAIL`、`UNRUN`、`BLOCKED`，只在相应验证维度使用。
- 单独查看已经生成的 HTML 快照不需要 Python。
- 生成任务包的 Agent 和执行中的 Main 均不重新编写 HTML、CSS、JavaScript 或图布局代码。
- Windows 后台进程采用隐藏窗口方式启动。
- 本计划不启动业务会话、不修改用户记忆、不执行 SHA 检查；未来执行者保留相同约束。
- 本次只形成实现计划。执行方式按用户后续选择；不因计划推荐子 Agent 而自动委派。
- 实施开始时按 using-git-worktrees 技能准备隔离工作区，并遵守 CONTRIBUTING.md 的分支、PR 与 CI 规则。不得覆盖已有改动；本计划不授权发布或合并。

## 1. 文件与职责

以下均为计划创建，已有文件的修改在各任务单列。

| 路径 | 责任 |
| --- | --- |
| `skills/plan-agent-tasks/references/progress-panel.md` | Agent 调用流程、角色责任、运行依赖、恢复与降级规则 |
| `skills/plan-agent-tasks/references/progress-state-contract.md` | JSON 字段、状态、增量操作和错误约定 |
| `skills/plan-agent-tasks/assets/dashboard/panel.py` | 命令行入口，只调用 core 模块 |
| `skills/plan-agent-tasks/assets/dashboard/panel_core/__init__.py` | 本地包入口和工具版本 `0.1.0` |
| `skills/plan-agent-tasks/assets/dashboard/panel_core/contract.py` | 数据与引用校验、纯函数增量应用、完成条件检查 |
| `skills/plan-agent-tasks/assets/dashboard/panel_core/store.py` | 单包写锁、序号检查、状态持久化和历史 |
| `skills/plan-agent-tasks/assets/dashboard/panel_core/render.py` | 固定资源内联、安全嵌入 JSON、原子导出 HTML |
| `skills/plan-agent-tasks/assets/dashboard/panel_core/server.py` | 只读 HTTP、每包进程身份、启动、复用与停止 |
| `skills/plan-agent-tasks/assets/dashboard/panel_core/cli.py` | 参数、输入输出、错误码和模块调用顺序 |
| `skills/plan-agent-tasks/assets/dashboard/resources/panel-template.html` | 语义布局骨架和资源插入点 |
| `skills/plan-agent-tasks/assets/dashboard/resources/panel.css` | 页面布局、状态样式和无障碍表现 |
| `skills/plan-agent-tasks/assets/dashboard/resources/panel.js` | 状态展示、轮询、筛选、详情、视图保留和 SVG 任务图 |
| `skills/plan-agent-tasks/assets/dashboard/README.md` | 复制后的工具使用说明 |
| `tests/panel_fixtures.py` | 可组合的虚构状态及临时包辅助函数 |
| `tests/test_panel_contract.py`、`tests/test_panel_store.py` | 数据语义与故障/并发验证 |
| `tests/test_panel_render.py`、`tests/test_panel_server.py` | 导出安全性与真实本地 HTTP/进程验证 |
| `tests/test_panel_integration.py` | CLI、复制迁移及分发闭环 |
| `skills/plan-agent-tasks/examples/progress-panel/` | 明确标注模拟数据的演示包和验证说明 |

生成包的 `dashboard/` 完整复制上述 `assets/dashboard/`；不依赖维护仓库的 `tests/` 或 `scripts/`。前端源资源分文件维护，导出的 `index.html` 内联其全部内容，满足独立 HTML 要求。

## 2. 冻结的技术接口

### 2.1 JSON v1

全部时间为带时区的 ISO 8601 UTC 字符串；尚未观察到的时间为 `null`。采用增量整数 `seq`、`run_number`、`plan_revision` 和任务 `round`，不用内容哈希标识版本。

初始化输入由下表中的 `packet`、`source`、`main`、`tasks`、`sessions`、`stages`、`checks`、`evidence`、`dependencies` 构成；工具补充格式版本、工具版本、`seq=0`、生成时间、空事件和历史。生成任务包时只接受 planned 状态；旧包导入使用单独的 import 命令，提交已核对的完整 v1 快照，不能虚构实际会话 ID 或已执行结果。演示数据在复制出的测试包中通过后续模拟事件构造，并明确标为 fixture。

| 字段 | 类型与约束 |
| --- | --- |
| `schema_version`、`tool_version`、`seq` | 分别为整数 `1`、字符串 `0.1.0`、非负整数 |
| `packet` | `id`、`title`、`mode`、`run_number`、`plan_revision`、`lifecycle`、`stage_id`、`stop_condition`；模式为现有三种，初始运行次数与计划编号为 1 |
| `source` | `mode: local/projection`、`reference`、`available: bool`、`checked_at`；引用为明确的仓库加相对路径或 HTTP(S) URL |
| `generated_at`、`observed_at` | 工具成功生成时间与 Main 最近核对时间；HTTP 读取不修改二者 |
| `main` | `logical_id`、`session_id`、`status`、`observed_at`；初始实际 ID 为空 |
| `tasks` | 以 Task ID 为键；每项包含 `id/title/stage_id/status/round/progress/progress_at/blocker/next_action/session_ids/required_check_ids`；完成条件列表不可为空 |
| `sessions` | 以逻辑角色 ID 为键；每项包含 `task_id/role/planned_name/actual_name/actual_id/host_status/observed_at/round/planned_model/actual_model/replaces`；模型为对象或未知值，实际宿主值未取得时不复制计划值冒充实际值 |
| `stages` | 以阶段 ID 为键；包含 `title/task_ids/status/approved/approval_evidence_ids`；没有阶段时为空对象 |
| `checks` | 以检查 ID 为键；包含 `task_id/kind/role_id/round/applicable/result/evidence_ids/not_applicable_reason`；种类含 delivery/review/approval/test/integration/acceptance |
| `evidence` | 以证据 ID 为键；包含 `title/reference`，引用形式同 source；不保存凭据或原始聊天 |
| `dependencies` | 列表，每条为 `from/to/required_check_ids`；检查须属于前置任务，空检查列表表示该前置任务必须 done |
| `events` | 已接受事件的编号、来源时间、接收时间、摘要和完整原始更新体，供去重与动态查看 |
| `history` | 已结束执行轮次的完整快照列表，归档项不再包含嵌套 history；显示时可选择历史轮次 |

`reference` 只接受 `{"repository": "demo", "path": "reports/a.md"}` 或 `{"url": "https://example.com/report"}` 两种形式。包内证据查看必须额外核对引用位于本包允许读取的文件范围；其他引用仅展示定位信息或真实远程链接。

`runtime/panel.json` 是工具运行配置，保存 packet_id、source_mode、权威引用和目标状态文件名；read_state 据此选择 state.json 或 view.json，不通过“哪个文件较新”猜测权威。它不保存任务进度。目标文件已存在时 init/import 拒绝覆盖；旧版同名权威文件可保留为原来源，采用 projection 模式写 view.json。

`packet.lifecycle` 使用 `planned/running/waiting_user/blocked/finished`；任务状态沿用设计第 6 节。检查不适用时 `applicable=false`、`result=null` 并填写原因，不能伪造 PASS。过期检查保留原结果，通过检查轮次与任务轮次的不同标为失效。

### 2.2 增量与一致性

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

允许的操作为 `task.set`、`session.set`、`stage.set`、`check.set`、`evidence.put`、`main.set`、`source.set`、`packet.set`、`plan.replace`、`run.start`。前五种按上述对象的已知字段更新；其余分别更新 Main、来源、当前阶段指针、完整计划或开始明确的新一轮执行。`packet.set` 的 changes 只允许 stage_id，值为已登记阶段 ID 或 null，仅更新当前阶段展示，不改变批准或执行授权；身份、模式、lifecycle、运行号、计划修订号及来源均不可通过该操作修改。不存在的任务/角色/检查只能通过 `plan.replace` 登记，不能被拼写错误隐式创建。

`task.set` 不允许改身份或完成要求；改轮次必须增加并在事件中附原因。`source.set` 只更新可用性和核对时间，不切换权威模式或目标位置。`plan.replace` 一次替换任务、角色、阶段、检查、依赖定义，增加 `plan_revision`，保留已有运行证据；移除已经执行的对象改为取消或历史记录，不能静默删除。要求已变化的受影响结果须重新核对。`run.start` 只在终止或显式停止后使用，归档旧轮次，再按完整初始化数据创建下一轮；恢复不调用它。

一次更新先在副本上应用所有操作，再校验全部状态，全部成功后才发布。相同事件编号、相同更新体重试返回原接受结果；同编号不同内容拒绝。去重先于 expected_seq 判断，支持响应丢失后的安全重试；其余旧序号报冲突。Main 核对时间不能倒退；较旧报告可以作为有原时间的历史事件接收，不能覆盖更新的会话观察或任务轮次。

所有适用 required_check_ids 均须为当前任务轮次、PASS 且具有证据，才允许 done；完成只是对 Main 已提交结构化结论的校验，不是工具代替审查。批准字段需证据引用；满足批准也不能让展示工具创建会话。

### 2.3 命令接口

下表中的 `panel.py` 指任务包内 `dashboard/panel.py`；命令从目标仓库根以该文件的明确相对路径运行。状态目录由脚本相对所属任务包解析；不接受浏览器传来的任意文件路径。

| 命令 | 行为 |
| --- | --- |
| `init --input plan.json` | 读取结构化初始数据；创建状态与首份 HTML；已有状态时拒绝覆盖，不启动服务 |
| `import --input snapshot.json` | 为旧任务包导入 Main 核对后的完整 v1 快照及原始证据引用；不覆盖已有目标、不重置工作轮次、不启动服务 |
| `publish --input event.json` | 校验增量并发布状态，再导出 HTML；本地权威与外部投影模式使用各自目标文件 |
| `status` | 只读返回版本、任务包身份、序号、来源时间、服务与快照状态 |
| `export` | 从现有有效状态重新生成独立 HTML，不修改执行状态或 observed_at |
| `start --open` | 在后台启动或复用本包服务，可选打开浏览器，返回真实 URL 与实例身份 |
| `serve` | 供 start 使用的服务进程入口，持有本包服务锁；不承担采集或调度 |
| `stop` | 按本包实例身份请求关闭预览服务，不修改任务结果 |

输入 JSON 通过文件传递，避免把角色文字拼进 shell。每个命令向 stdout 输出一份 JSON 结果，诊断写 stderr；成功退出 0，输入错误 2，序号/实例冲突 3，来源读取错误 4，预览故障 5。状态成功发布但 HTML 导出失败退出 6，并返回 `state_published=true`、实际 seq 和 `snapshot_updated=false`，防止 Main 误以为整次写入没有发生。

HTTP 只提供 `/`、`/index.html`、`/api/status`、`/api/identity` 及 `/evidence/<id>` 的 GET/HEAD。状态响应为 `{"state": ..., "sync_error": null}`；读源出错时携带上次有效 state 和错误，启动即无有效数据时返回 503。identity 包含 packet_id、工具版本及启动时生成的实例 UUID；它不是执行授权或用户凭据。

服务仅绑定 `127.0.0.1`，由端口 0 分配可用端口。拒绝写方法，不启用目录列表、不反射 CORS。stop 通过本包本地控制文件传递匹配的实例 ID，由服务循环读取后退出，不增加 HTTP 控制接口。

## 3. 实施任务

按 Task 1 → 2 → 3 → 4 → 5 执行。Task 6 在全链路就绪后验收；不得用模拟验收替代真实运行证据。

### Task 1：结构化状态契约与完成校验

**Files:** 创建 `references/progress-state-contract.md`、`assets/dashboard/panel_core/__init__.py`、`assets/dashboard/panel_core/contract.py`（均在 Skill 目录中）；创建 `tests/panel_fixtures.py`、`tests/test_panel_contract.py`。

**Interfaces:** 产出 `ContractError(ValueError)`、`validate_state(state: dict) -> None`、`initial_state(plan: dict, now: str) -> dict`、`apply_event(state: dict, event: dict, received_at: str) -> dict`、`ensure_done_allowed(state: dict, task_id: str) -> None`。不访问文件、网络或系统时间，时间从参数传入。

- [ ] 创建测试 fixture：`make_state() -> dict` 返回完整有效状态，含 DEMO-001 和 DEMO-002 两任务，后者依赖前者；DEMO-001 有 delivery 和两个独立 review 检查，初始均 UNRUN。`make_event(event_id: str, seq: int, ops: list[dict]) -> dict` 固定使用上述示例时间并填入摘要。测试辅助模块将 Skill 的 `assets/dashboard` 加到导入路径。
- [ ] 先写以下失败测试，并补充错误引用、循环依赖、轮次变化、多 Reviewer 缺一个结果、阶段批准缺证据、合法不适用检查以及逐维度不混淆的案例。

```python
import unittest
from panel_fixtures import make_state, make_event
from panel_core.contract import ContractError, apply_event

class ContractTests(unittest.TestCase):
    def test_delivery_cannot_imply_done(self):
        state = make_state()
        event = make_event("premature-done", 0, [
            {"type": "task.set", "id": "DEMO-001", "changes": {"status": "done"}}
        ])
        with self.assertRaises(ContractError):
            apply_event(state, event, "2026-09-08T08:00:00Z")
        self.assertEqual(state["seq"], 0)
        self.assertEqual(state["tasks"]["DEMO-001"]["status"], "pending")
```

- [ ] 运行 `python -m unittest discover -s tests -p test_panel_contract.py -v`，记录首次预期失败。
- [ ] 实现全部字段类型、枚举、唯一身份、引用存在性、DAG 与时间格式校验；Task ID、检查 ID 和角色 ID 不以标题推断。拒绝未知字段及未知 schema_version。用以下核心校验约束 done，其余字段约束按第 2 节逐项实现。

```python
class ContractError(ValueError):
    pass

def ensure_done_allowed(state, task_id):
    task = state["tasks"][task_id]
    for check_id in task["required_check_ids"]:
        check = state["checks"][check_id]
        if not check["applicable"]:
            if not check["not_applicable_reason"]:
                raise ContractError(f"Missing exemption reason: {check_id}")
            continue
        if check["round"] != task["round"] or check["result"] != "PASS":
            raise ContractError(f"Incomplete current-round check: {check_id}")
        if not check["evidence_ids"]:
            raise ContractError(f"Missing evidence: {check_id}")
```

- [ ] 实现纯函数更新：深复制 → 逐个应用允许操作 → 校验全状态 → 添加事件与收到时间 → seq 加一；不接受客户端写 seq。plan.replace/run.start 按第 2.2 节保留或归档证据；相同事件重试不产生新序号。
- [ ] 重跑本任务测试，确认所有失败、返修和不变性案例通过；提交本任务相关文件，提交输出使用 `git commit --quiet`。

### Task 2：原子存储与固定 HTML 导出

**Files:** 创建 `assets/dashboard/panel_core/store.py`、`render.py`；创建 `tests/test_panel_store.py`、`tests/test_panel_render.py`。各 assets 路径均相对于 Skill 根。

**Interfaces:** 消费 Task 1 全部函数。产出 `read_state(packet_dir: Path) -> dict`、`initialize(packet_dir: Path, plan: dict, now: str) -> dict`、`import_snapshot(packet_dir: Path, state: dict) -> dict`、`publish(packet_dir: Path, event: dict, now: str) -> dict`、`render_html(state: dict, resources_dir: Path) -> str`、`export_snapshot(packet_dir: Path) -> Path`。initialize/import_snapshot 同时建立 panel.json，配置与目标均需校验；半成品初始化恢复先核对身份，不覆盖已有状态。

- [ ] 先写真实临时目录测试：不同 expected_seq、相同事件重试、同编号不同内容、两个并发进程更新、写入异常后旧文件仍完整、两包互不影响、外部来源模式只写 view.json。
- [ ] 为 JSON 安全嵌入写失败测试；本任务使用测试临时目录内的最小模板资源，固定插入标记为 `PANEL_DATA`、`PANEL_STYLES`、`PANEL_SCRIPT` 三个 HTML 注释，每个必须且只能出现一次。

```python
def test_embedded_data_cannot_close_script(self):
    state = make_state()
    attack = '</script><script>alert("x")</script>'
    state["tasks"]["DEMO-001"]["title"] = attack
    html = render_html(state, self.resources_dir)
    self.assertNotIn(attack, html)
    self.assertIn("\\u003c/script", html)
```

该测试类 setUp 创建临时资源目录；模板在 `type="application/json"` 的脚本元素内放 PANEL_DATA 注释，另有独立样式和脚本插入点，CSS/JS 文件写入固定空布局和初始化语句。

- [ ] 分别运行 `python -m unittest discover -s tests -p test_panel_store.py -v` 与 `python -m unittest discover -s tests -p test_panel_render.py -v`，记录预期失败。
- [ ] 存储使用本包 `.writer.lock` 操作系统文件锁，锁内重新读取序号、判重、应用并校验事件、写同目录临时文件，然后替换目标。锁在进程退出时释放，不通过删除一个陈旧 PID 文件宣称获得跨进程互斥。Windows 与 Unix 分支分别使用标准库 [msvcrt.locking](https://docs.python.org/3/library/msvcrt.html#msvcrt.locking) 和 [fcntl.flock](https://docs.python.org/3/library/fcntl.html#fcntl.flock)。
- [ ] 同文件系统替换采用 [os.replace](https://docs.python.org/3/library/os.html#os.replace)。跨进程锁包围读到写的全过程；异常不留下半份目标状态。render_html 用下面的序列化方式，将固定资源内联并替换上述插入点；对状态文本不执行模板表达式。

```python
payload = json.dumps(state, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
payload = payload.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
```

- [ ] 状态发布和 HTML 导出分别记录结果，HTML 故障不回滚已生效状态；导出失败可重试 export，同一事件重试仍不增加计数。未知来源格式不得自动创建另一份权威状态。
- [ ] 重跑两个测试文件并提交本任务；此时只有工具与临时模板验证，不宣称真实页面完成。

### Task 3：独立页面、任务图与自动刷新

**Files:** 创建 `assets/dashboard/resources/panel-template.html`、`panel.css`、`panel.js`；补充 `tests/test_panel_render.py`；创建 `examples/progress-panel/README.md`、`plan.json`、`events.json`（均在 Skill 目录中）。

**Interfaces:** 消费第 2 节状态与 Task 2 render_html。JavaScript 在单一 `window.Panel` 对象上公开 `projectState(state, nowMs)`、`layoutGraph(state)`、`renderState(state, nowMs)`、`refreshOnce()`。projectState 返回 counts、activeSessions、freshness 和 labels；layoutGraph 返回 nodes、edges、stageBounds、width 和 height，两者为纯函数。renderState 保留 UI 状态；后续服务器返回第 2.3 节状态 envelope。

- [ ] 先创建含 6 个任务、2 个阶段、并行分支、双 Reviewer、返修和等待门禁的示例输入。标明全部会话与事件为模拟材料。测试图数据保留跨阶段依赖；有效重排输入后节点位置按稳定 Task ID 一致。
- [ ] 为顶部分类、done 分母排除 cancelled、过期时间与等待用户区别写可在浏览器执行的断言；先在尚未实现相应导出时观察失败。例如，状态标题、状态和 seq 更新不得修改选中 Task ID。

```javascript
const before = JSON.parse(document.getElementById("panel-data").textContent);
before.packet.lifecycle = "running";
before.observed_at = "2026-09-08T08:00:00Z";
const view = window.Panel.projectState(before, Date.parse("2026-09-08T08:02:01Z"));
if (view.freshness !== "stale") throw new Error("Expected stale source data");
if (before.tasks["DEMO-001"].status === "failed") throw new Error("Freshness changed task outcome");
```

- [ ] 实现静态布局：顶部身份/阶段/统计/同步时间，中部任务图与活跃列表，点击后右侧详情，下方最近动态；窄屏改为上下排列。浅色底、清晰文字、状态颜色配标签；节点支持键盘选中，缩放提供按钮，减少动画模式下不使用闪烁或脉冲。
- [ ] 实现原生 SVG 图：对任务依赖做拓扑排序，rank 取前置最大 rank 加一；同 rank 按阶段次序和 Task ID 稳定排列，使用固定节点尺寸和折线路径。渲染数据在多前置汇合和阶段批准处插入 gate 类型菱形节点，明确标注全部条件，gate 不计入任务统计。阶段边界和条件边加标签；过滤只淡化无关节点，不改变真实依赖。任务详情展示各角色和返修轮次，独立会话 Mermaid 图继续作为包内既有材料。
- [ ] 实现 projectState：状态分类严格来自任务枚举，角色活跃名单来自有时间标注的 host_status；布局只由拓扑和计划修订变化触发。runtime 更新用 DOM textContent 与 SVG text，禁止把角色文本交给 innerHTML。选中、缩放、平移、筛选和滚动保存在 UI 对象中。
- [ ] 实现实时与离线入口。file 协议只读取嵌入数据；HTTP 模式在上次请求结束后等待 2 秒，再请求 status，避免并发轮询。5 秒请求超时与服务错误显示连接状态，旧数据仍保留；收到同 seq 时不重绘，但新鲜度标签继续随时间变化。

```javascript
async function refreshOnce() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch("api/status", { cache: "no-store", signal: controller.signal });
    if (!response.ok) throw new Error(`Preview HTTP ${response.status}`);
    const envelope = await response.json();
    window.Panel.renderState(envelope.state, Date.now());
    document.getElementById("sync-error").textContent = envelope.sync_error || "";
  } finally {
    clearTimeout(timeout);
  }
}
```

外层循环捕获异常并只改变连接提示；renderState 必须核对 schema、packet_id、run_number、seq，拒绝倒退或串包数据。页面最近读服务时间独立于 Main observed_at。文件协议下不调用 refreshOnce。

- [ ] 通过实际浏览器检查 1440×900 与 390×844 布局，覆盖选中、过滤、缩放、并行线、长中文标题、双 Reviewer、旧 PASS 失效和历史轮次查看；保存截图及观察记录到示例的验证说明中。运行本任务渲染测试后提交。

### Task 4：每包只读预览进程与 CLI

**Files:** 创建 `assets/dashboard/panel.py`、`panel_core/server.py`、`panel_core/cli.py`、`README.md`；创建 `tests/test_panel_server.py`、`tests/test_panel_integration.py`。

**Interfaces:** 消费 read_state/initialize/import_snapshot/publish/export_snapshot。产出 `make_server(packet_dir: Path, instance_id: str) -> ThreadingHTTPServer`、`start_service(packet_dir: Path, open_browser: bool) -> dict`、`stop_service(packet_dir: Path) -> dict`、`main(argv: list[str] | None = None) -> int`。make_server 构造监听套接字但不启动服务线程；serve 进程控制其请求循环与本地停止文件。

- [ ] 先写真实回环 HTTP 测试：GET identity/status、HEAD、未知路由、POST 拒绝、路径逃逸、非法 evidence ID、错误状态保留最近有效值、两包身份及端口不同。使用临时目录，测试结束关闭服务和套接字。

```python
def test_preview_is_read_only(self):
    request = urllib.request.Request(self.base_url + "/api/status", data=b"{}", method="POST")
    with self.assertRaises(urllib.error.HTTPError) as result:
        urllib.request.urlopen(request, timeout=2)
    self.assertEqual(result.exception.code, 405)
    with urllib.request.urlopen(self.base_url + "/api/identity", timeout=2) as response:
        self.assertEqual(json.load(response)["packet_id"], "DEMO-PANEL")
```

测试类 setUp 在临时包 initialize 后调用 make_server，并在测试线程处理请求；base_url 从实际 server_address 构造。tearDown 结束请求循环并 join，不能遗留后台进程。

- [ ] 运行 `python -m unittest discover -s tests -p test_panel_server.py -v`，记录预期失败。
- [ ] 使用 [Python HTTP 服务接口](https://docs.python.org/3/library/http.server.html) 编写固定路由处理器，不能直接用整个仓库作为 SimpleHTTPRequestHandler 根目录。证据 resolve 后必须仍在登记包内，文本读取以纯文本响应；禁目录列表、跨域、写请求和任意路径参数，响应禁止缓存旧状态。
- [ ] 服务持有与 writer lock 分开的 `.service.lock`。将 packet_id、instance_id、真实端口和工具版本写入 `runtime/service.json`；start 在复用前请求 identity 核对全部身份，不能仅凭 PID 重用或终止进程。进程内的实例 ID 每次随机生成，不进入任务执行证据。
- [ ] 实现隐藏后台启动、10 秒内的身份就绪核对、实例匹配的本地 stop 请求，以及请求循环退出后的 descriptor 清理。超过启动期限返回明确故障，不声称可访问；stop 只影响自己验证过的服务，不使用宽泛的进程名终止。具体 Windows 启动方式须在该平台实际验证。
- [ ] 按第 2.3 节实现 CLI，先用下面的真实子进程调用覆盖 init/export/status，再覆盖 publish 的冲突、重复事件与部分失败；新包初始文件模板从 assets/dashboard 完整复制。

```python
completed = subprocess.run(
    [sys.executable, str(packet_dir / "dashboard" / "panel.py"), "status"],
    check=False, capture_output=True, text=True, encoding="utf-8", timeout=10,
)
self.assertEqual(completed.returncode, 0, completed.stderr)
result = json.loads(completed.stdout)
self.assertEqual(result["packet_id"], "DEMO-PANEL")
```

- [ ] CLI 测试新增“状态写入成功、导出失败”退出 6，再执行 export 恢复；重复 publish 不能重复事件。import 测试须保留已完成任务和历史证据，并拒绝覆盖已有目标及半成品身份冲突。全部通过后执行 start → status → stop → status 的实际子进程验证，确认服务退出，提交本任务。

### Task 5：接入 Skill、角色模板与独立分发

**Files:** 创建 `skills/plan-agent-tasks/references/progress-panel.md`。修改同目录的 `SKILL.md`、`README.md`、`references/execution-modes.md`、`references/packet-contract.md`、`assets/packet.md`、`assets/main.md`、`assets/worker.md`、`assets/reviewer.md`、`assets/prompts.md`、`examples/README.md`、`examples/validation.md`；修改根 `README.md`、`tests/test_distribution.py`，补充 `tests/test_panel_integration.py`。

**Interfaces:** 消费第 2.3 节全部 CLI。产出实例化的面板路径、来源模式、角色进展报告入口和 Main 操作规则；维护根 scripts 仍不属于运行依赖。

- [ ] 在真实 ZIP 迁移测试中增加面板闭环：打包 Skill，解压到中文及空格目录，将其 dashboard 复制进新的虚构任务包，提供合法 plan.json，然后执行 init/export/status。测试进程 cwd 切到迁移目录，确保不从原仓库导入模块。

```python
with zipfile.ZipFile(archive) as bundle:
    bundle.extractall(relocated)
source = relocated / "plan-agent-tasks" / "assets" / "dashboard"
shutil.copytree(source, packet_dir / "dashboard")
completed = subprocess.run(
    [sys.executable, str(packet_dir / "dashboard" / "panel.py"), "init", "--input", str(plan_path)],
    cwd=relocated, capture_output=True, text=True, encoding="utf-8", timeout=10,
)
self.assertEqual(completed.returncode, 0, completed.stderr)
self.assertTrue((packet_dir / "dashboard" / "index.html").is_file())
```

其中 archive 来自现有 package_skill，packet_dir 与 plan_path 为测试临时路径，plan_path 内容来自 make_state 对应的合法初始化输入，均由 setUp 创建。

- [ ] 运行 `python -m unittest discover -s tests -p test_panel_integration.py -v`，先确认迁移与初始化缺口被测试发现，再补齐分发或资源定位。
- [ ] 写入以下 Main 调用规则，并在三个模式的生成提示词中实例化具体文件入口。普通运行更新使用 publish；返回 seq 冲突则先 status、核对事件与报告再提交，不能盲目修改 expected_seq 重试。

```text
启动时核对任务卡、权威状态与实际会话，初始化或恢复本任务包面板，调用 start 并提供已验证入口。
你是本任务包状态的唯一维护者；根据 Worker/Reviewer 报告和宿主状态，通过 publish 提交结构化更新。
关键事件后更新；可执行的等待期间目标每 30 秒核对一次，不把工具等待或页面请求伪装为执行心跳。
遵守当前执行模式及批准范围；面板不创建会话、不授予批准。结束时 export 并核对快照，再 stop 本包预览。
```

- [ ] Worker/Reviewer 卡分别增加具名报告路径、工作轮次、里程碑摘要、阻塞与证据的交付约定；不准写共享 state/view，不要求访问 Main 工作区。Main 通过已有报告交付渠道读取，路径必须有仓库锚点。
- [ ] 总卡和 Main 卡增加面板入口、状态来源及已知运行依赖。修改根 README 的“Skill 本身不要求安装 Python”表述：离线 HTML 查看无需 Python；初始化、状态工具和实时预览要求 Python 3.11+。旧包没有面板时，先核对报告再调用 import 导入；不能清空历史或伪造未观察状态。
- [ ] SKILL.md 保持显式调用与只生成材料的边界，要求复制固定资源而非写网页代码。新增命令使用相对路径与 JSON 文件参数，所有运行依赖保留在 Skill 中。功能就绪后将 metadata.version 更新为 `0.3.0`，工具版本仍单独记录。
- [ ] 运行根仓库静态校验、完整 unittest 和 package_skill；将实际结果写入 validation.md，保持 UI、真实调度与多机器范围分开，再提交本任务。只因新增测试改变总数时如实更新，不能预先编造通过数量。

### Task 6：页面、恢复、离线与真实执行验收

**Files:** 补充 `skills/plan-agent-tasks/examples/progress-panel/README.md`、`verification.md` 和 `skills/plan-agent-tasks/examples/validation.md`；截图只保存脱敏示例。真实任务材料放入已授权测试任务包，不能混入公开 fixture。

**Interfaces:** 消费完整生成包与 CLI；产出按证据等级分开的验收报告，不增加调度 API。

- [ ] 执行正常模拟链：init → start → Worker 运行 → 交付 → Reviewer 运行 → 返修 → 双 Reviewer 当前轮通过 → done → export → stop。记录每次数据 seq、来源时间、页面文字及实际可见时间，不借图形变绿宣称真实工作已执行。
- [ ] 同时启动第二个不同任务包：核对名称、数据与端口，停止第一个后第二个仍可读取。保持一个任务处于 running，将 observed_at 设为已过期，确认浏览器连接成功但来源过期，且任务状态仍 running 对应的原状态。
- [ ] 选中节点并缩放、过滤后发布更新，确认视图不跳回初始；模拟格式错误与旧 seq，确认保留最后有效数据和错误提示。等待用户与正常结束不误报工作失败。
- [ ] 关闭服务、断开页面网络后直接打开 index.html，验证所有样式、图、统计、角色与证据定位可读；复制到另一中文及空格目录再验证一次。记录跨仓证据仅可定位的实际边界。
- [ ] 用当前宿主和一个已授权的真实任务包完成 Main/Worker/Reviewer 最小闭环。角色载体沿用用户选择；没有授权创建真实会话时不自动启动，将该项记为 UNRUN。记录真实报告何时可见、Main 何时核对、publish 何时成功、页面何时反映，分别评估 30 秒采集目标与 5 秒显示验收。
- [ ] 中断并恢复真实 Main，核对旧会话和批准范围后复用面板；观察是否发生重复派工、重复事件或旧审查覆盖。外部来源模式如没有真实连接条件，只报告本地投影机制测试，不宣称平台端到端成功。
- [ ] 提交实测报告。只有工具、浏览器、迁移和适用真实验收均有证据后，才描述对应能力可用；GitHub CI、合并、发布保持单独状态。

## 4. 计划核对与完成边界

| 设计要求 | 实施覆盖 |
| --- | --- |
| 固定工具和模板、只传数据 | Task 2、3、4、5 |
| 单一权威、角色隔离、增量与去重 | Task 1、2、5 |
| 完成口径、多 Reviewer、返修、阶段门禁 | Task 1、3、5、6 |
| 三种时间、自动更新、停更及错误保留 | Task 3、4、6 |
| 独立包、进程、原子写入和恢复 | Task 2、4、6 |
| 离线 HTML、资源随包、相对路径 | Task 2、3、5、6 |
| 真实宿主、模拟与跨机器证据区分 | Task 5、6 |

产品层面无需新增决定。页面字号、间距、字段校验代码、文件内部拆分由实现者按上述契约处理；真实浏览器与执行验收发现的问题在既定范围内修正。若需要扩大到远程访问、控制面板派工或跨机器采集，另行调整设计，不能作为本计划的隐含工作。

本文件是实现计划；复选框尚未完成，命令和测试片段描述未来执行步骤。文档自查通过或原有测试通过，不代表这些新增模块已经存在或已通过验收。
