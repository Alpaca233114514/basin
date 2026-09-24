# Basin demo 的边界与接口

依据 2026-09-22「Basin定位总结」：采集层提供原始证据，分析器负责确定性计算，agent 查询具体 run 再调查。Rosetta 是首个应用，范围不限定 seed。

本版选择 **独立进程 + 文件采集 + 模型工具 API**：Rosetta 现有 instrumentation → 原始 trace/report → Basin adapter → history → analyzer → CLI/Python/MCP。HTML 为可选导出，API 细节见 [model-api.md](model-api.md)。无需把 Basin import 写入 Rosetta，也不执行来自 Rosetta 的 Python 文件。以后可由其他解释器输出同一 native envelope；目前未接入 NNsight 或实时 PyTorch hook，不声称任意张量已可采集。

## 数据合同 v1

每个 history 目录代表一个观察单元（通常一个 episode 或一份 Gate 报告）。`source_run` 连接来自同一次实验的多个单元；不会把多个 seed 冒充独立训练。目录包含：

- `run.json`：adapter、source_run、证据类型、状态、参数与原始身份、维度语义、Gate、验证范围。
- `events.jsonl`：`step`、`stage`、`values`、原始 artifact 行号或 JSON Pointer。
- `artifacts/`：导入时的原始字节副本，源文件搬走后仍可取证。
- `manifest.json`：最后写入，每个文件的 SHA-256。缺失或不匹配不当作有效 run。

SHA 只验证字节一致性，不证明作者、测量真实性或签名。可疑输入始终作为数据，不执行。单文件上限 64 MiB，当前实现在内存中处理小型诊断 bundle，不适合全模型张量归档。

### 通用采集器输入

```json
{
  "schema_version": 1,
  "evidence_kind": "synthetic",
  "source_run": "example",
  "status": "complete",
  "parameters": {"seed": 0, "model_revision": "example-only"},
  "dimensions": ["joint_0"],
  "gate": {},
  "events": [
    {"step": 0, "stage": "execution", "values": {
      "action": [0.1], "gradient_norm": 0.3, "activation": [0.2, 0.4]
    }}
  ]
}
```

`evidence_kind` 可选 synthetic / historical_observation / live_observation，是采集者声明，不是 Basin 认证。`(step, stage)` 必须唯一；原始数据结构保留，未观测字段省略或 null，不能填 0。严格 JSON 拒绝 NaN、Infinity、重复键。统计只纳入数值，不把布尔 success 当数字。

## Rosetta 接入

`rosetta.rollout_trace.v1` 接收 `identity.json / trace.jsonl / summary.json / manifest.json`。先核验上游文件 SHA，再检查 schema、episode/seed、prediction → step_started → step 顺序、状态连续性、向量维度、完成计数和基本 outcome。保留 prediction 全部 chunk 的原始证据，但标准执行事件只包含已完成 step，避免把计划当实际动作。未完成 trace 可导入，仍明确为 incomplete；无法解析的半行不静默忽略。

本版不重算原 verifier 的全部 support 指标，也不复验 checkpoint 字节；verification 明确写出这两个缺口。Gate 报告保留原声明，计算导入 SHA，不把它冒充上游 bundle 校验或独立验收。

默认真实 demo 使用保留完整 trace 的 canonical 20260916-005，而不是猜测正在修改的 root-neighborhoods 格式。新实验可用 `import-rosetta` 指定路径；不同格式新增 Basin adapter，不改 Rosetta。

## 比较语义

通过 `(step, stage)` 对齐，JSON Pointer 指定比较字段；报告参数差异、首个观测差异、数值最大绝对差、缺失覆盖和原始证据位置。不同 evidence_kind、adapter、维度语义或 Rosetta Action Contract 拒绝数值比较。跨 seed 的 step 对齐仅作描述性比较，不代表相同物理状态。所有假设列表默认空，因果结论为 null。

## 工程约束

仅用 Python 3.10+ 标准库，无运行时第三方依赖，不需要安装。目录只新增、禁止覆盖；同 ID 同字节可重复导入，冲突拒绝。失败可能留下未发布目录，history 显示 invalid，保留供调查。HTML 转义所有输入，无脚本和网络资源。

推荐把 Rosetta 挂到 Linux 容器 `/rosetta:ro`，Basin 挂到 `/basin`；`--network none`。软件拒绝 source/output 根重叠及 manifest 路径穿越，OS 只读挂载提供额外强制边界。不要让另一个进程同时修改导入文件或 history。读入字节按 manifest 校验，但本版本没有多文件原子源快照或多写者数据库事务。

## 后续共同进步

Rosetta 每次产生同格式新 trace → Basin 用新 ID 导入 → history 查询身份和 Gate → compare 找差异及缺口 → 由人/agent 提出单变量验证计划。需要新张量时扩展采集器，先验证采集是否改变动作、随机流和运行结果；需要模型干预时另行授权。此次 demo 不启动该后续阶段。
