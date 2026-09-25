# 模型工具接口

Basin 的主入口是 API。模型宿主发现 schema 后，把 tool call 的 name / arguments 交给 Basin，获得结构化 JSON；无需浏览器或人工翻报告。

## 三种调用方式

### CLI JSON API

```bash
python -m basin tools
python -m basin tools --format functions
echo '{"run_id":"rosetta-gate4-1002","pointer":"/parameters/options"}' | python -m basin --store outputs/rosetta-demo-v2/history call basin_get_run
```

`tools` 输出 MCP 工具定义；`--format functions` 输出常见 function-calling 的 `type/function/name/description/parameters` 结构。宿主把模型生成的函数名和 JSON 参数传给 `call`，stdout 始终输出结果 JSON。`--args` 可直接传 JSON，默认 `-` 从 stdin 读取，避免 shell 引号问题。失败退出码 2、成功 0；工具错误的 JSON 含 `ok:false` 与错误码。

### Python API

```python
from basin.api import BasinAPI

api = BasinAPI("outputs/rosetta-demo-v2/history")
schemas = api.tools()
result = api.call("basin_events", {
    "run_id": "rosetta-gate4-1002", "step": 125, "field": "/action"
})
```

Python 调用的可处理失败抛 `ToolError`，含 `code`；CLI/MCP 将其转换为机器可读错误。

### MCP stdio

```bash
python -m basin --store outputs/rosetta-demo-v2/history mcp
```

宿主从任意 cwd 启动时，可用 Python 可执行文件 + `scripts/basin_mcp.py` 的绝对路径 + `--store` 的绝对路径。不使用终端交互，不输出欢迎语，不监听 HTTP 端口。

本机 Rosetta 记录的合规入口为 `scripts/mcp_in_container.sh`：从 WSL 启动既有 Linux Docker 镜像，把 Basin（含已导入 history）只读挂载，禁网、2 CPU/1 GiB；完全不挂载 Rosetta，也不执行模型。通用 MCP 宿主配置见 `examples/mcp-client.json`，路径需按机器调整。初次交付只验证 stdio 子进程；随后用户明确要求配置到 Codex，已完成下述注册，不冒充当前聊天工具列表已热加载。

## 工具清单

| 工具 | 用途 |
|---|---|
| `basin_history` | 按 source_run / evidence_kind 查询运行，分页 |
| `basin_get_run` | 查询身份、Gate、配置、参数 JSON Pointer |
| `basin_events` | 按 step / stage 查询，field 精确取值并回传 evidence |
| `basin_read_artifact` | 原始 JSON/JSONL 行、JSON Pointer、源字节哈希 |
| `basin_analyze` | 确定性统计，prefix 过滤与分页 |
| `basin_analyze_torchlens` | TorchLens 已保存激活统计及可观察图关系；按 modules / edges / issues 分页 |
| `basin_compare` | 参数差异、首个观测差异、缺失覆盖、证据位置 |
| `basin_verify` | 校验 history 中所有文件的字节哈希 |
| `basin_check_identity` | 取单个身份 JSON Pointer，与期望值和/或已登记来源文件的 SHA256 比较，明确报告 match/mismatch/missing |
| `basin_timeline` / `basin_locate_deviation` / `basin_branch_compare` | 双时间轴采样、偏离和分支证据查询 |
| `basin_import_training_config` | 从受控来源导入训练配置快照包，或 v2 计划与成对的 launch/runtime 文件 |

默认有 12 个只读工具。可选启动参数 `--source alias=/directory` 显式登记来源根后，才暴露五个导入工具：`basin_import_native`、`basin_import_torchlens`、`basin_import_rosetta`、`basin_import_dual_axis` 和 `basin_import_training_config`。TorchLens 导入仅接受现有采集器的安全 JSON envelope，不反序列化 Python 对象。模型只能选择已登记 alias 和其内部相对路径，不能通过 API 更改服务的 store/source 根，不能执行 shell、训练、覆盖证据或写回 Rosetta。

训练配置导入示例：`basin_import_training_config` 使用 `{ "source": "runs", "path": "exp/launch/run-training-config", "run_id": "run-config" }` 导入新快照包。历史 v2 计划可用相同工具的 `launch_path`、`runtime_path` 配对；YAML 或继承计划还需 `resolved_plan_path`。查询 `/parameters/training/dataset` 得到数据集标识、revision、所选 episode 与视图哈希，`status=plan_only` 与 `launch_prepared` 均不代表训练完成。

身份关联示例：`basin_check_identity` 参数 `{ "run_id": "rosetta-gate4-1002", "pointer": "/parameters/identity/endpoint/files/model.safetensors", "expected": "<已独立取得的64位SHA256>" }` 比较两个**声明值**。若服务启动时以 `--source artifact=/verified/checkpoint` 登记了只读来源目录，再传 `"source":"artifact","path":"model.safetensors"`，工具会流式读取该文件并计算 SHA256；返回 `verification:source_bytes_hashed` 和文件大小。缺失字段报告 `missing`，差异报告 `mismatch`，不会把别的文件、完整 checkpoint 或训练事实一起认证。文件读取最多 4 GiB；旧 MCP 配置未挂载 Rosetta 来源时只能使用 `expected` 模式。`basin_get_run` 对大型身份列表应使用窄 JSON Pointer，整段 `/parameters` 可能超过结果上限。

分页：`offset` 默认 0，`limit` 默认 20、最大 100；返回 `total`、`next_offset`。单结果上限 128 KiB，超过后返回 `result_too_large`，不会截断为伪完整证据；可用 pointer/field/prefix/limit 缩小查询。事件中未记录字段返回 `present:false`，null 与缺失不填零。

## 协议实现范围

实现 MCP **2025-11-25** 的 stdio/tools 子集：`initialize` → `notifications/initialized` → `tools/list` / `tools/call`，以及 `ping`。输出同时含 text content 和 `structuredContent`。JSON-RPC 错误与工具执行错误分开，通知不响应。客户端请求其他版本时服务返回其支持的 2025-11-25，客户端需按规范判断是否继续。

当前是无第三方依赖的同步本地实现，没有 HTTP、2026 协议族、sampling、异步 tasks、订阅或运行中取消能力，不宣称完整 MCP SDK 等价。

参考：[stdio 传输](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)、[生命周期](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)、[工具协议](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)。

## 不经过网页的验收

```bash
bash scripts/verify_in_container.sh --api-demo
```

先跑全部测试，再由独立客户端启动 Basin MCP 子进程，逐次等待握手与调用响应。执行 history → seed 参数 → step 125 的 action → 由返回的行号读取原始 artifact → analyze → compare → verify。真实协议收发记录保存到 `outputs/mcp-api-demo.json`，已有文件不覆盖。没有调用收费模型；验证的是模型宿主实际需要的工具协议和调用链。

### 2026-09-22 实测

- 最终 31 项测试通过，含真实子进程协议、CLI JSON、分页、参数校验、来源根边界和错误响应。
- `outputs/mcp-api-demo.json`：Linux 容器内协议客户端完成全部 7 类工具调用。
- `outputs/mcp-launcher-demo.json`：Windows 宿主按 `examples/mcp-client.json` 实际启动 WSL → Docker → Basin 服务，完成同一调用链；服务只读挂载 Basin，没有挂载 Rosetta。
- 两次均发现 7 个工具、查询到同一 source_run 的 6 个观察单元；seed=1002、step=125 的 action 与原始 artifact 一致；500 步比较及 history 哈希验证通过。
- `git diff --check` 通过。未提交、未推送、未修改 Rosetta 或模型客户端全局配置。

复现本机启动配置的调用验证（输出须用新文件名）：

```powershell
python scripts/agent_api_demo.py --mcp-config examples/mcp-client.json --output outputs/mcp-launcher-demo-new.json
```

## Codex 注册状态（2026-09-22）

用户授权后，通过 `codex mcp add basin -- ...` 写入用户级配置的 `[mcp_servers.basin]`，`codex mcp get basin --json` 确认为 enabled。命令为 Windows WSL 可执行文件，参数为 `bash` 和 Basin 中 `scripts/mcp_in_container.sh` 的绝对 WSL 路径。未修改 Rosetta。

配置修改前在原目录保存 `config.toml.basin-20260922-205636.bak`。核对并保留原有全部配置（包括 Codex CLI 规范化时省略的 node_repl 空 args）；除新增 basin 表外，解析后配置完全相同。

从实际登记配置取出命令，再完成 MCP 握手、发现 7 个工具和 7 类真实 history 查询，结果保存到 `outputs/codex-mcp-registration-20260922.json`。当前聊天会话是否热加载未验证；按 Codex 官方 MCP 配置流程，重新启动客户端后加载。Docker Desktop 需处于运行状态。
