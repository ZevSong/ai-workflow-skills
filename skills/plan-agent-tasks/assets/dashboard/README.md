# 任务包只读进度面板工具

将本目录完整复制为任务包的 `dashboard/`，保留 `panel_core/`（包含私有模块）和 `resources/`。工具使用 Python 3.11+ 标准库；查看已导出的 `dashboard/index.html` 不需要 Python。以下命令从目标仓库根执行，`docs/task-packets/DEMO` 替换为实际包路径。工具根据复制后的入口位置定位任务包，不依赖当前工作目录。

```sh
python docs/task-packets/DEMO/dashboard/panel.py init --input plan.json
python docs/task-packets/DEMO/dashboard/panel.py publish --input event.json
python docs/task-packets/DEMO/dashboard/panel.py status
python docs/task-packets/DEMO/dashboard/panel.py export
python docs/task-packets/DEMO/dashboard/panel.py start --open
python docs/task-packets/DEMO/dashboard/panel.py stop
```

旧包使用 `import --input snapshot.json` 导入 Main 已核对的完整 v1 快照，保留实际轮次、完成状态、历史和证据引用。`init` 只接受 planned 初始计划。两者都拒绝覆盖现有目标，且不启动服务。配置已存在但状态尚未写入时，只有完全匹配的包身份及来源配置可以继续创建。

`publish` 先发布状态，再导出 HTML；相同事件原样重试不会重复事件或增加序号。`export` 从当前有效状态修复快照，不修改执行状态和 Main 核对时间。`status` 返回包身份、格式/工具版本、序号、来源及其时间、服务身份/运行状态、`snapshot_exists`。该快照标记只说明文件存在，不代表它已经同步到当前 seq。

每个命令在 stdout 输出一份 JSON，诊断写入 stderr。输入文件路径相对于命令的工作目录；角色文字只写入 JSON 文件。命令不提供浏览器写入或角色调度。

| 退出码 | 含义 |
| --- | --- |
| 0 | 命令成功；`start --open` 另返回 `browser_opened`，打开浏览器失败时服务仍可通过 URL 访问 |
| 2 | 输入文件、命令参数或状态/事件契约错误 |
| 3 | 序号、事件身份、任务包配置或服务实例冲突；包括 OS 锁忙 |
| 4 | 来源/状态 I/O 错误；检查 `state_published` 和已知的 `seq` |
| 5 | 预览故障或独立 `export` 的渲染故障 |
| 6 | 状态操作已成功返回，但后续 HTML 导出失败；检查真实提交标记 |

code 4 的 `WriteError` 可能发生在状态替换之前，也可能发生在替换成功后的锁清理阶段：后者返回 `state_published=true` 和实际接受的 seq，不能认为写入失败而盲目重发。code 6 返回 `state_published=true`；通常 `snapshot_updated=false`，但 HTML 已替换、随后清理失败时它为 true，并附已知的 `snapshot_seq`。导出失败不回滚状态。修复资源后运行 `export`，必要时通过 `status` 核对状态。并发发布可以在返回后继续推进序号。

## 本地服务边界

`start` 仅绑定 `127.0.0.1:0`，返回实际分配的端口、URL、包 ID、工具版本、实例 UUID 和 `reused`。复用和停止之前，通过固定 `/api/identity` 核对完整身份；不会使用 PID 猜测、进程名称终止、代理或重定向。身份 UUID 只表示预览实例，不是凭据或执行授权。启动在 10 秒内核对就绪；未就绪时返回故障并回收自己启动的子进程。

Windows 使用 `CREATE_NO_WINDOW` 和隐藏窗口的 `STARTUPINFO` 后台启动。内部入口 `serve`（或 `serve --instance <UUID>`）持有独立的 `runtime/.service.lock` OS 锁。`runtime/service.json` 保存身份及端口。`stop` 写入包含匹配身份的 `runtime/stop-<UUID>.json`；服务读到匹配请求后关闭监听器和请求连接，清理自己的描述文件及控制文件并释放锁。持久锁文件本身可以保留；它不代表服务仍在运行。服务故障不改变任务结果。

HTTP 只有 `/`、`/index.html`、`/api/status`、`/api/identity`、`/evidence/<id>` 的 GET/HEAD 路由。没有目录列表、任意路径参数、CORS、HTTP 控制或写入接口。`/api/status` 保持固定响应 `{state, sync_error}`：读取失败时保留本进程最近有效状态；从未读到有效状态时返回 503 和 `state=null`。读取不刷新 Main 的观察时间。

## 包内证据入口

证据仍是 v1 登记的 repository/path 或 HTTP(S) URL。只为 `source.mode=local` 且权威引用以 `runtime/state.json` 结束的状态推导包前缀。例如权威引用 `demo / docs/task-packets/DEMO/runtime/state.json`，同仓库证据 `docs/task-packets/DEMO/reports/result.md` 映射到实际任务包的 `reports/result.md`；搬迁整个任务包后仍按这个虚拟前缀映射，不重复拼接前缀、不探测仓库根。

服务还会检查解析后的真实路径留在任务包内。只有登记 ID 可请求；缺失文件、跨仓库、包外路径、目录、非 UTF-8 文本或超过 2 MiB 的内容返回明确不可用信息。文本按 `text/plain` 和 `nosniff` 返回，HTML-looking 证据不会执行。读源失败时不根据旧证据登记读取文件。

面板上的“尝试查看包内文本”是候选入口，实际可读性由服务核对。离线快照、投影来源、`packet.md` 等不明确的权威锚点、跨仓库引用和历史记录保留定位文本；HTTP(S) 证据保持真实远程链接。事件当时登记的引用与当前同 ID 引用不同时，不链接到当前文件冒充历史证据。本工具不增加来源映射配置或状态字段。

## 已验证范围

本次在 Windows、Python 3.11、Chromium 中使用中文及空格路径的临时包，完成真实回环路由、隐藏子进程启动/复用/停止、并发启动、错误实例拒绝、超时子进程回收、导入保留、写入/导出部分成功和实际证据入口检查。Unix 生命周期分支尚未执行。这里的工具验证不代表角色会话、业务验收、CI、发布或部署完成。

实现接口依据 Python 官方 [HTTP 服务文档](https://docs.python.org/3/library/http.server.html) 与 [子进程文档](https://docs.python.org/3/library/subprocess.html)。
