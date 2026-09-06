# 模型资源与速度策略

本约定把“谁来推进”“使用多少模型资源”“是否请求加速”拆成三个独立轴。将最终选择和每个会话的实际绑定写入任务包，不能让新会话靠宿主默认值猜测。

```yaml
execution_mode: manual | semi-auto | auto
resource_profile: fixed-main | economy | balanced | assured | maximum
speed_policy: standard | critical-path | fast-all
```

默认组合是 `manual + balanced + standard`。执行模式仍按 [执行模式约定](execution-modes.md) 选择；资源档位默认 `balanced`，速度默认 `standard`。任务多且需要阶段门禁时可以建议 `semi-auto`，期限明确且关键路径值得加速时可以建议 `critical-path`。`fast-all` 只能由用户明确选择。三个轴互不隐含：例如 `maximum + standard` 完全有效，选择 `maximum` 不自动开启 Fast。

## 运行时目录与解析

模型名称、可选推理强度、提供方和优先服务能力会变化，不能在本 Skill 中保存一个永久型号榜单。生成任务包时先从当前宿主的会话创建工具契约、可读取的模型/提供方配置和用户指定的可用清单建立“本次目录快照”；必要时查当前官方资料。只做目录与能力读取，不发送付费推理探针、不读取或复制密钥。

目录快照至少登记：

| 字段 | 含义 |
| --- | --- |
| `catalog_source` | 宿主工具、项目配置、用户清单或官方资料的明确来源 |
| `checked_at` | 带时区的检查时间 |
| `host_scope` | 该目录适用的宿主或执行环境；不写机器绝对路径 |
| `provider` / `model` | 创建会话时可实际传入的准确标识 |
| `reasoning_efforts` | 当前接口声明支持的值 |
| `service_tiers` | 是否能对单会话明确设置 `standard`、`fast` 或等价优先级 |
| `cost_basis` | 已知计价来源与时间；未知时写 `unknown`，不能假称最便宜 |

生成时尽量完成所有会话的准确绑定。Main 启动时在实际调度宿主上做一次轻量复核；提供方、宿主或配置发生变化，主选不可用，或目录来源明确过期时刷新。无需调用第二个 Skill。若生成环境看不到实际目录，则将任务包标为 `MODEL_BINDING_BLOCKED`，记录选择约束，并要求 Main 在启动后先解析和写回准确绑定；在此之前不得创建 Worker 或 Reviewer，也不得把未含准确配置的段落交付为“可启动提示词”。任务包只有在每个待创建会话都有准确绑定、对应提示词已经更新后才可标为 `ready_for_dispatch`。

第三方 API 只使用当前宿主明确暴露且会话创建接口实际接受的提供方与模型。仅有 Base URL 或配置名称不等于模型、价格、推理强度或优先服务已知。未知字段如实记录；候选均无法核实时，报告能力缺口，不把第三方模型映射成一个猜测的 OpenAI 型号。

## 资源档位

先按任务的业务风险、改动范围、架构影响、推理复杂度、上下文规模和验收难度筛选“能力足够”的候选，再按资源档位排序。价格只能在计价口径可比较时参与排序。用户对具体会话的明确指定高于档位默认规则，并在任务包中记录来源。

| 档位 | 选择规则 | 审查与自动升级 |
| --- | --- | --- |
| `fixed-main`（固定同 Main） | 所有新会话显式填写与 Main 相同的 `provider`、`model` 和 `reasoning_effort`；这是有意绑定，不是省略参数后的继承 | 不自动升级型号；仍保留独立 Reviewer 上下文 |
| `economy`（节省优先） | 从能力足够且价格可比较的候选中选预期成本较低者；关键契约、安全和复杂集成不得为省钱降到能力不足 | 验收失败或 Reviewer 给出有证据的能力不足时，最多按卡片升级一次 |
| `balanced`（自适应均衡，默认） | 常规、边界清楚的实现使用合适的低成本模型；Main、复杂契约、跨仓集成和高风险审查使用更强候选 | 每个会话最多自动升级一次；升级后仍须原定独立审查 |
| `assured`（质量保障） | 关键任务使用当前已验证的高能力模型和较高推理强度；常规任务仍按复杂度分配 | 关键任务安排两个不同会话的独立 Reviewer；每个会话最多自动升级一次 |
| `maximum`（极致保障） | Main、每个 Worker 和 Reviewer 使用当前目录中满足工具与上下文约束的最高能力模型及其最高合适推理强度 | 每个叶子任务安排两个 Reviewer，其中一个执行对抗性边界/安全审查；已是最高档时不再升级 |

`maximum` 也必须受边界约束：同配置的调度重试、模型升级、返修/复审轮数都写成有限数字；达到上限后 Main 汇总证据和阻塞，不无限创建会话。默认建议每次创建失败同配置重试最多 1 次、单会话模型升级最多 1 次（`fixed-main` 与已到最高候选为 0 次）；返修轮数按任务风险与项目规则实例化，不能把一次失败直接解释为需要更贵模型。

模型升级只用于证据表明当前模型能力或上下文限制阻碍任务的情况。测试失败、需求冲突、权限缺失、工具故障和外部服务不可用先按其真实原因处理。降级、升级和切换提供方都只能使用任务卡预先列出的准确候选，并记录原因与实际绑定。

## 每个会话必须显式绑定

任务包为 Main、每个 Worker 和每个 Reviewer 分别登记：

```yaml
provider: <exact provider id>
model: <exact model id>
reasoning_effort: <exact supported value>
service_tier: standard | fast | <verified equivalent>
service_tier_control: per-session | host-global | unavailable
service_tier_parameter: <exact key/value passed, or none>
selection_reason: <why this is sufficient for this task>
fallbacks:
  - provider: <exact provider id>
    model: <exact model id>
    reasoning_effort: <exact supported value>
    service_tier: <exact supported value>
escalation_trigger: <evidence required before switching>
dispatch_retry_limit: <finite integer>
model_escalation_limit: <finite integer>
binding_status: resolved | MODEL_BINDING_BLOCKED
```

不得通过省略模型参数让 Worker 或 Reviewer 隐式继承 Main。创建或续接工具支持的字段必须显式传入。`service_tier` 记录该会话最终采用的标准化服务层；`service_tier_control` 只使用 `per-session`、`host-global` 或 `unavailable`，`service_tier_parameter` 记录实际传入的准确参数，不传时写 `none`。若主选不可用，Main 只可显式选择有序 `fallbacks` 中第一个仍合格的候选并登记实际值；没有可用回退则停止该会话的派工并报告，不能静默继承、任意降级或切换提供方。

续接原会话通常保留该会话已解析的模型设置。若宿主允许续接时换模型，只有达到卡片中的升级触发条件和次数上限才可切换，并在状态中记录；新 Reviewer 仍是独立会话。

## 速度策略与 Fast

Fast 是服务优先级/延迟策略，不表示模型更聪明，也不替代 `resource_profile`。任务包使用以下策略：

| 策略 | 行为 |
| --- | --- |
| `standard`（默认） | 所有会话使用标准服务层；宿主仅有全局控制时保持其已确认的标准设置 |
| `critical-path` | 仅对当前阶段依赖图中会推迟最终交付或下一阶段门禁的会话请求 Fast，包括阻塞下游的 Worker、Reviewer 或 Main 集成步骤 |
| `fast-all` | 所有可支持的计划会话请求 Fast；仅在用户明确选择后使用 |

关键路径从实际依赖图计算并在总卡标注，不能把所有高优先级任务都叫关键路径。计划变化后 Main 重新计算后续未启动会话；已经运行的会话不为追求标签而重建。Mermaid 可在实际请求 Fast 的会话标签后加 `⚡`，图例说明符号含义。

只有会话创建接口明确支持单会话服务层时，Main 才为该会话传入 `service_tier: fast` 或经验证的等价参数，并登记 `service_tier_control: per-session`。若宿主只有全局 Fast 开关，登记 `host-global`；`critical-path` 不能静默扩大为全局加速，除非用户已明确授权 `fast-all`，否则使用 `service_tier: standard`，报告宿主限制。完全没有 Fast 能力时登记 `service_tier: standard`、`service_tier_control: unavailable`、`service_tier_parameter: none`。第三方提供方只有在其当前接口与计价资料明确支持等价优先服务时才启用。

Fast 不可用时回退到 `standard`，不得因此更换模型、提高推理强度或切换提供方。实际计费倍率和支持范围以生成或启动时查到的当前资料为准，任务包记录来源与时间，不在本 Skill 中固化可能过期的数字。

OpenAI Codex 环境优先核对当前 [Fast Mode 文档](https://learn.chatgpt.com/docs/agent-configuration/speed) 和 [配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)；ChatGPT 登录与 API Key 的计费口径可能不同，任务包不得混用。其他提供方使用其自己的当前官方资料。

## 任务包校验

交付前额外检查：

- 三个轴各有值、选择来源和默认使用说明；`fast-all` 有用户明确选择证据。
- Main 和每个计划创建的 Worker/Reviewer 都有准确模型绑定，或整个包清楚标为 `MODEL_BINDING_BLOCKED` 且禁止派工。
- 主选、回退和推理强度存在于同一份当前目录快照；成本未知时没有“最便宜”之类结论。
- `critical-path` 的 Fast 标记与依赖图一致；宿主不支持单会话 Fast 时没有悄悄扩大范围。
- 每个自动重试、升级和返修回路都有有限上限；资源升级不替代修复、测试和独立审查。
- 实际创建参数、宿主不支持字段、所用回退和目录刷新写入活动状态来源，计划值与实际值分开。
