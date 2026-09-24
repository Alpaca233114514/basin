# Basin demo 验证记录

实现分支：`codex/basin-evidence-demo`。未提交、未推送。

## 完成的接入

- Basin 以独立 Python 标准库程序运行；Rosetta 代码、配置、训练入口无需改动。
- 导入 canonical-fullframes-posttrain-20260916-005 的五条历史 Gate 4 episode（seed 1000–1004）和已有 Gate 结果报告。
- 2,500 条已完成执行事件，原始 prediction / step_started / step 全部保存在 artifact；两个 toy run 另标 synthetic。
- seed 1000 与 1002 的 action 比较覆盖 500 对事件，最早观测差异 step 0；参数记录显示 seed、policy_noise_seed 和 episode_index 不同。这是跨条件描述，不是因果结论。
- 最大 reward 分别为 0、0、2、0、0，五条 episode success 均为 false。源报告声明 Gate 3 passed、Gate 4 failed、M2 false；Basin 未重新执行或独立认证 Gate。

## 验证证据

通过 `wsl.exe bash` 启动 Linux 容器。使用已有镜像 `sha256:fb3c1bbda42881fac9b7725d3acb436119934f0c60af29747339d5951c3039da`，禁网、只读容器根目录、2 CPU、1 GiB 内存、无新增 capability。Rosetta 仓库和指定历史证据分别以只读挂载提供；仅 Basin 输出可写。

`python -m unittest discover -s tests -v` 最终 **23 项通过**。覆盖 hash 损坏、hash 正确但顺序错误、部分执行、覆盖冲突、路径穿越、缺失/null、数值容差、维度不一致、synthetic/real 隔离、原始张量字段回查、CLI 查询和 HTML 转义。

真实 demo 收据在 `outputs/rosetta-demo-v2/receipt.json`：

```json
{
  "completed_steps": 2500,
  "named_source_files": 21,
  "real_model_executed": false,
  "rosetta_integration": "existing_trace_imported",
  "source_snapshot_unchanged": true,
  "synthetic_first_difference": 3
}
```

前后快照 `rosetta-before.json` / `rosetta-after.json` 覆盖 HEAD、Git status、tracked diff 和 21 个指定输入文件的字节 SHA；并非整个磁盘、未跟踪文件全部内容或模型权重的校验。Rosetta 有其他并行工作，任务结束时的工作区列表有新增变化；本任务不归因或覆盖这些变化，只确认本次导入窗口的快照一致及只读挂载边界。

Browser 已验证报告页面 DOM、桌面布局，显示八个 history 项和比较结果。`git diff --check` 通过。未运行真实模型、GPU、训练或新仿真。

## 保留的失败与限制

最初 `outputs/rosetta-demo` 在只读接入时发现 runs 是迁移到 D 盘的目录链接，路径边界检查拒绝越界。合成输出原样保留；修复为解析该指定证据目录后单独只读挂载，未放宽通用路径检查。成功重试使用新的 `outputs/rosetta-demo-v2`。

当前只适配 Rosetta rollout_trace v1 和此类 Gate report；未适配所有新诊断格式。没有实时 hook、NNsight 后端、任意权重/全量 activation 采集、replay 或 intervention。source support 指标和 checkpoint 字节未独立重验。该 demo 完成的是独立证据接入，不表示 Rosetta 模型已改善。
