# Basin 如何独立参加 Rosetta 开发

在 Basin checkout 中运行，所有新文件写到 Basin。Rosetta 仅提供既有记录，不需要在其源码增加 import、回调或配置。

模型优先通过 `tools/list` 发现 Basin MCP 工具，再调用 `tools/call`。支持 shell 工具的模型也可直接调用 `python -m basin tools` 和 `python -m basin call TOOL`；JSON 参数通过 stdin 传入。接口、分页和宿主配置见 [model-api.md](model-api.md)。此流程不依赖网页。

## 一次调查的输入与输出

1. 确认要调查的 source run、episode 与 Gate，明确这是历史记录还是新观测。不同 seed 或噪声条件不能自动视作对照干预。
2. 只读导入对应 trace / Gate report。给观察单元唯一 ID，保留 `source_run` 关联；同 ID 不覆盖。
3. `history` 找运行，`show --pointer /parameters` 查询配置和身份，`verify` 校验历史副本。
4. `compare --field /action` 或 `/state_after` 比较相同合同的记录；`analyze` 获取程序计算的统计。检查缺失覆盖、incomplete 和证据类型。
5. 用 `events --step N` 定位事件，再按 evidence 中的行号调用 `artifact ... --line N` 取回原始数据；不要仅依据汇总猜测根因。
6. 调查结果按“观测事实 / 尚未验证假设 / 缺少的证据 / 下一项有界验证”输出。新模型改动、采集、训练、回放或干预另行登记和授权。

命令具体例子见 README。CLI 的 JSON 可以直接进入 agent 工具上下文，不必把整个 trace 塞进提示词。数据缺失时明确返回缺失；Basin 不自动补造测量或改模型。

## 已可使用的首次调查

history：`outputs/rosetta-demo-v2/history`。

共同 source run：`canonical-fullframes-posttrain-20260916-005`。观察单元：`rosetta-gate4-1000` 到 `rosetta-gate4-1004`，关联报告 `rosetta-gate-report`。报告：`outputs/rosetta-demo-v2/index.html`。

例如先比较 seed 1000 与 1002 的 `/action` 与 `/input_identity`，核对模型/processor/Action Contract 身份和噪声 seed 差异，再回查关注步骤。记录只能支持“发生了差异”；要确定差异为什么导致失败仍需受控证据。
