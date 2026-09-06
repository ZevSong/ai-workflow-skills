# 模型资源与 Fast 选择

材料类型：手工编写的输入与预期行为。示例中的提供方和型号均为虚构目录项，不代表当前产品清单或价格。

## 输入条件

用户明确调用 `$plan-agent-tasks`，需求已经可执行，并选择：

```yaml
execution_mode: auto
resource_profile: balanced
speed_policy: critical-path
```

Main 当前运行在高成本模型。宿主目录同时包含 `provider-a/model-capable`、`provider-a/model-efficient` 和第三方 `provider-b/model-code`。依赖图中，契约 Worker 及其 Reviewer 阻塞两个下游任务；其他两个 Worker 可并行且不在关键路径。宿主的会话创建接口支持准确 `model` 与 `reasoning_effort`，但 Fast 只有宿主全局开关，不支持单会话 `service_tier`。

## 预期行为

- 记录目录来源、检查时间、宿主范围、能力与计价未知项；不从型号名称推断第三方价格或 Fast。
- Main、每个 Worker 和每个 Reviewer 都有准确 `provider`、`model`、`reasoning_effort`、`service_tier`、有序回退和有限升级次数。
- 常规 Worker 可显式绑定 `provider-a/model-efficient`，复杂契约及其 Reviewer 可绑定 `provider-a/model-capable`；没有任何会话因省略参数而继承 Main。
- 第三方候选只有在当前创建接口接受且能力足够时进入回退清单；计价未知时不宣称它更便宜。
- `critical-path` 原本只应给契约 Worker 和对应 Reviewer 标 `⚡`。由于宿主不能按会话设置 Fast，Main 不打开全局 Fast；所有会话使用 `standard`，模型绑定保持不变，并报告这个服务层限制。
- 自动调度仍按 `auto` 执行。速度回退不切换执行模式，也不触发模型升级。

## 预期绑定片段

```yaml
session_name: DEMO-01 · Worker · 契约实现
provider: provider-a
model: model-capable
reasoning_effort: high
service_tier: standard
service_tier_control: host-global
service_tier_parameter: none
selection_reason: 契约变更阻塞下游，且需要处理跨模块边界
fallbacks:
  - provider: provider-b
    model: model-code
    reasoning_effort: high
    service_tier: standard
escalation_trigger: 主选出现已验证的上下文或能力限制
dispatch_retry_limit: 1
model_escalation_limit: 1
binding_status: resolved
```

此片段只展示结构。真实任务包必须为全部会话实例化准确值，并用当前目录验证这些值后才能标记 `ready_for_dispatch`。

## 验收要点

- 三个轴没有互相推导；`balanced + critical-path` 不等于高价模型全开 Fast。
- 当前 Main 的模型没有成为未声明的默认值。
- 单会话 Fast 缺失时只回退 `standard`，没有全局扩大、换模型或换提供方。
- 主选不可用时只走卡片中的有序回退；没有可用候选则停止受影响派工。
- 所有自动重试、升级和返修回路有有限上限。
