# Basin

面向模型 / agent 的运行证据 **CLI、Python API 和 MCP stdio 服务**。**先查证，再解释。**

采集适配层保存已有观测，分析器完成确定性计算，人和 agent 通过 `history` 查询具体 run、参数、Gate 和差异。Rosetta Reality 是首个接入场景；Basin 独立运行，不修改 Rosetta。

## 直接给模型调用

```bash
# 发现工具及参数 schema
python -m basin tools
python -m basin tools --format functions

# 工具调用：stdin 接收模型给出的 JSON 参数，stdout 返回 JSON
echo '{"run_id":"rosetta-gate4-1002","step":125,"field":"/action"}' | python -m basin --store outputs/rosetta-demo-v2/history call basin_events

# 由模型宿主启动 MCP 子进程
python -m basin --store outputs/rosetta-demo-v2/history mcp
```

默认提供 12 个只读工具，包括 `basin_history`、`basin_get_run`、`basin_events`、`basin_read_artifact`、`basin_analyze`、`basin_analyze_torchlens`、`basin_compare`、`basin_verify`、`basin_check_identity` 和三个双时间轴查询工具。它们共用同一 Python API，返回可分页、有证据位置的结构化结果。需要导入或核对原文件 SHA 时通过 `--source alias=directory` 显式开放来源根。

Canonical training、checkpoint 2500/5000 与 004/005 Gate 的 create-only 历史导入见 [操作记录](docs/canonical-import-2026-09-22.md)；它只读核对既存原始字节，不运行模型。

本机 Rosetta history 的 MCP 宿主应使用 **WSL → Docker** 入口 `scripts/mcp_in_container.sh`。配置示例见 [examples/mcp-client.json](examples/mcp-client.json)，完整 API、Python 用法、返回格式和协议边界见 [docs/model-api.md](docs/model-api.md)。无需启动网页；HTML 仅为保留的可选导出。

## 运行 API demo

已有真实 history 时，从 WSL 中的 Basin checkout 执行：

```bash
bash scripts/verify_in_container.sh --api-demo
```

独立协议客户端逐次调用 MCP，验证历史发现、参数查询、step 125 原始证据回查、分析、比较和哈希校验；保存完整 JSON 请求/响应，不调用收费模型。运行结果写入 `outputs/mcp-api-demo.json`。

## 创建合成 history

Python 3.10+，只用标准库，无需安装依赖。在 Basin 仓库根目录执行：

```bash
python scripts/demo.py --output outputs/demo
python -m basin --store outputs/demo/history history
python -m basin --store outputs/demo/history compare toy-control toy-changed
```

两条合成轨迹第 3 步开始分叉，用于验证 action、loss、gradient_norm 和 activation 的保存与比较。**这是人工构造的采集器输出，不是真实模型实验。**默认只生成 history/JSON；`--html` 才额外生成网页。再次运行请使用新的 output 目录，已有结果不会覆盖。

## 接入隔壁 Rosetta

Windows 上使用 WSL Bash + 已有 Linux Docker 镜像；脚本禁网、固定镜像 SHA、限制 2 CPU/1 GiB、把 Rosetta 挂成只读。不下载模型、数据、镜像，不启动训练或仿真。

从 WSL 进入 Basin checkout 后执行：

```bash
bash scripts/verify_in_container.sh
```

脚本运行测试后导入现有 canonical 20260916-005 的五个 Gate 4 trace 和 Gate 报告，输出 `outputs/rosetta-demo-v2/history`、JSON 分析及只读接入收据。需要这些本地历史文件存在；缺失时失败，不自动下载。迁移后的 runs 会解析实际路径，仅把指定 verified 目录额外挂成 `/evidence:ro`。再次运行可传一个新输出目录作为脚本首个参数。

其他机器或新 run 可在合规运行环境中独立调用：

```bash
python -m basin --store outputs/new/history import-rosetta /rosetta \
  runs/your-run/traces/gate4-1000 --id your-run-seed1000 --gate gate4
python -m basin --store outputs/new/history import-rosetta /rosetta \
  reports/training/your-gate-result.json --id your-gate-report --kind gate-report
```

## 给人和 agent 的查询入口

以下命令针对接入 demo 已生成的 history，均输出 JSON：

```bash
python -m basin --store outputs/rosetta-demo-v2/history history
python -m basin --store outputs/rosetta-demo-v2/history show rosetta-gate4-1002 --pointer /parameters/options
python -m basin --store outputs/rosetta-demo-v2/history events rosetta-gate4-1002 --step 125
python -m basin --store outputs/rosetta-demo-v2/history artifact rosetta-gate4-1002 trace.jsonl --line 378
python -m basin --store outputs/rosetta-demo-v2/history analyze rosetta-gate4-1002
python -m basin --store outputs/rosetta-demo-v2/history compare rosetta-gate4-1000 rosetta-gate4-1002 --field /action
python -m basin --store outputs/rosetta-demo-v2/history verify rosetta-gate4-1002
```

原始 artifact 行号从 `events` / `compare` 的 evidence 字段获取。通用采集器（未来 hooks、NNsight 等）可输出 [native envelope](docs/design.md)，通过 `import-native file.json --id run-id` 接入。实时模型 hook 和自动修改模型仍未实现。

## 训练超参数与训练集身份

新的 Rosetta SmolVLA v2 `train` / `smoke` 启动会在持久 `launch` 目录生成
`<run_name>-training-config/`。其中包含已组装 CLI 对应的超参数、所选训练 episode、
数据集 identifier/revision、训练视图与归一化报告 SHA，以及原始计划、launch manifest
和 runtime experiment 的封存副本。快照状态 `launch_prepared` 只证明启动前登记，
不证明 optimizer 已更新或训练完成。`preflight` 不生成训练快照。

将证据目录以只读来源根提供给 Basin，然后导入新 ID：

```bash
python -m basin --store outputs/new/history import-training-config \
  /evidence experiment/launch/run-001-training-config --id run-001-config
python -m basin --store outputs/new/history show run-001-config \
  --pointer /parameters/training/dataset
```

上例中 `/evidence` 是来源根，余下部分是根内相对路径。已有 v2 原始计划也可单独导入
为 `plan_only`；若同时提供 launch manifest 和 runtime experiment，则核对文件 SHA
并标记 `launch_prepared`：

```bash
python -m basin --store outputs/new/history import-training-config \
  /evidence configs/plan.json --launch runs/launch/run.json \
  --runtime runs/launch/run-runtime-experiment.json --id historical-config
```

旧 v2 YAML 或含 `extends` 的计划须另给 Rosetta 解析后的 JSON：
`--resolved-plan configs/resolved-plan.json`。Rosetta 提供文件级
`scripts/export_smolvla_v2_resolved_plan.py --plan <原计划> --output <新JSON>`；
Basin 保存原计划字节并核对 launch 中的原计划 SHA，但将解析结果标记为
`operator_supplied`，不把 Basin 未独立解析的 YAML 说成已复验。

模型入口为 `basin_import_training_config`，只有配置 `--source alias=directory` 后才开放；
所用路径必须在该别名之内。所有导入 create-only，保留原始字节，按 `source_run` 关联其他证据。
超参数位于 `/parameters/training`，身份位于 `/parameters/identity`；未知值为 `null`。

## TorchLens JSON 离线导入与分析

现有可选采集器生成的 `native.json` 可由专用适配器导入。输入只作为 JSON 数据读取，不加载 TorchLens 对象、权重或模型代码；导入后保留原始字节、SHA 和事件指针。

```bash
python -m basin --store outputs/new/history import-torchlens /path/to/capture/native.json --id capture-001
python -m basin --store outputs/new/history analyze-torchlens capture-001
```

模型工具对应 `basin_import_torchlens`（仅在配置 `--source alias=directory` 后开放）和只读 `basin_analyze_torchlens`；后者以 `section=modules|edges|issues` 分页。分析从已保存的 JSON 激活重新计算模块及总体的最小值、最大值、均值、RMS、L2 和覆盖数量。图分析只解析标签唯一的父引用，并报告缺失、歧义和循环；图完整性仍未独立验证。详见 [TorchLens 说明](docs/torchlens-backend.md)。

## 证据边界

- 保留原始字节和 SHA；损坏、路径越界、覆盖冲突会报错。Gate 报告是源报告声明，不冒充独立验收。
- 未完成执行、缺失字段、合成演示和真实历史分别标注。最早记录差异不等于根因。
- 不把离线指标、episode success 或 history 导入成功推定为 Gate 通过或 M2 完成。
- 小型文件 demo，单文件最大 64 MiB；暂不支持全量模型权重/任意大张量存储、实时干预或 replay。

设计、可扩展合同和验证范围见 [docs/design.md](docs/design.md)。

```bash
python -m unittest discover -s tests -v
```
