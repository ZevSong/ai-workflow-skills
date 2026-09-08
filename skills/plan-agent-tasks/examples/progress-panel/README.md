# 模拟任务进展面板

本目录全部内容均为 **模拟 Fixture**，没有真实 Worker、Reviewer、Main 会话或业务验收。示例中的实际会话 ID 也仅是模拟字符串。任何 `PASS` 只演示一个结构化检查的显示，不是产品执行、部署或发布证据。

[plan.json](plan.json) 是符合 v1 的 planned 初始化输入。[events.json](events.json) 按顺序模拟：停止旧轮次、明确开始第二轮、并行实施与双 Reviewer 观察、提高任务返修轮次。事件必须按顺序通过 `apply_event` 应用，不能把演示状态当成真实初始化计划。

最终模拟状态包含六个任务、两个阶段、跨阶段依赖、两个并行分支、一个汇合门禁与阶段批准门禁。`DEMO-002` 是第 2 轮返修，旧交付和两项审查的第 1 轮 `PASS` 仍保留并标为失效；`DEMO-003` 有两个独立的模拟 Reviewer 观察；`DEMO-004` 等待阶段批准；`DEMO-006` 已取消，完成分母为 5。历史选择器可以查看第 1 轮快照。

## 在独立 Skill 中生成离线示例

在 Skill 根目录运行以下 Python 3.11+ 代码。它只读示例、调用固定契约与渲染器，写出一个 HTML；不启动服务或业务角色。可在临时复制出的 Skill 目录操作。

```python
import json
import sys
from pathlib import Path

assets = Path("assets/dashboard")
example = Path("examples/progress-panel")
sys.path.insert(0, str(assets))
from panel_core.contract import initial_state, apply_event
from panel_core.render import render_html

state = initial_state(json.loads((example / "plan.json").read_text(encoding="utf-8")),
                      "2026-09-08T08:00:00Z")
for event in json.loads((example / "events.json").read_text(encoding="utf-8")):
    state = apply_event(state, event, event["occurred_at"])
Path("simulated-panel.html").write_text(
    render_html(state, assets / "resources"), encoding="utf-8")
```

双击生成的 HTML 即可离线查看，不需要 Python、构建工具、CDN 或浏览器扩展。`file:` 页面不发出状态请求，主要同步提示为“离线快照 · Main 核对记录”；历史轮次显示“历史快照”。示例使用固定来源时间，页面显示的时间差会随打开时间变化。

## 验证说明

2026-09-08 在 Chromium **151.0.7922.34** 实际执行浏览器断言，视口为 **1440×900** 和 **390×844**。浏览器工具仅用于开发验证，不是产品运行依赖。执行结果：**PASS**。

- 顶部显示 Main 登记状态。纯投影统计：完成 `1 / 5`、实施/返修/验证 `1`、独立审查 `1`、等待确认/批准 `1`、受阻 `0`、未开始/就绪 `1`、取消 `1`。失败与取消在发生时另列，门禁不计为任务。
- 固定 Main 时间后 120 秒仍为 fresh，121 秒为 stale；等待用户与已结束各自有标签，不改写任务结果。文件快照使用独立离线提示。
- 默认从上到下按 rank 展示 DAG，节点显示当前轮的 Worker/Reviewer running 观察摘要。插入顺序变化不改变节点位置；跨阶段边、全部前置条件与两个 Reviewer 条件保留。已测示例中的折线不穿过无关节点。活跃、受阻与当前阶段过滤仅淡化节点；“适应画布”将完整图放入内部视口。
- 键盘 Enter 选中，标题和状态更新保留选中任务、筛选、缩放、平移与滚动位置；角色文本作为字面文本展示；实际模型未知时不复制计划模型。
- 同 seq 不重建任务列表或图；Main 与会话观察时间差仍更新。历史查看不覆盖当前数据；拒绝不支持的 schema、串包、旧 run 和倒退 seq。
- 即使 SVG 构造不可用，六个任务仍可在“全部任务”列表选择，任务详情与两个 Reviewer 仍可读取。
- `file:` 下自动启动及显式 `refreshOnce()` 都不 fetch。HTTP 检查使用 **受控路由 Fixture**，覆盖一次请求结束后约 2 秒的下一次自动轮询、请求去重、5 秒超时、503、来源错误与恢复；记录最大并发为 `1`。服务读取不修改 Main 核对时间。

开发仓库中可用 `python tests/panel_preview.py <临时输出HTML>` 生成固定渲染器输出，再运行 `node tests/panel_browser.cjs <临时输出HTML>`。浏览器测试先尝试普通 `require('playwright')`，也接受环境变量 `PANEL_PLAYWRIGHT_MODULE` 指定已安装模块；没有可用 Playwright 或 Chromium 时输出 **UNRUN** 并返回 77，不自动安装。`PANEL_SCREENSHOT_DIR` 可指定截图目录。以上测试助手只存在于开发仓库，不是独立 Skill 的必需文件。

以下截图均由真实浏览器从固定渲染器生成的 HTML 捕获，已人工打开检查；全部身份和内容已模拟：

| 截图 | 检查内容 |
| --- | --- |
| [desktop.png](screenshots/desktop.png) | 1440×900 视口全页，选中返修任务，长中文标题、旧 PASS 失效、双 Reviewer 活跃观察、离线提示可读 |
| [mobile.png](screenshots/mobile.png) | 390×844 视口全页，统计三列，正文与详情上下排列，页面宽度不超过 390px |
| [gates.png](screenshots/gates.png) | 桌面“适应画布”视图，显示并行分支、跨阶段汇合与阶段批准，右侧列出全部条件 |
| [history.png](screenshots/history.png) | 显式第 1 轮历史快照，任务待开始、检查 UNRUN、无实际会话观察 |

任务图保持固定节点尺寸，窄视口中会局部裁切，属于有意的内部滚动视图。图下明确提示滚动、缩小和鼠标拖动；也可直接使用全部任务列表。全页截图会包含视口之外的文档内容，右侧桌面详情另有自身滚动区域。

**范围限制：** HTTP 验证属于浏览器受控路由 Fixture；本任务没有验证后续 Task 4 的真实本地服务、CLI、证据读取边界、跨机器分发、真实角色调度或业务验收。仓库相对证据只展示完整定位信息，不承诺该文件可由面板服务读取；HTTP(S) 引用是远程链接。
