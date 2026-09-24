# Canonical 历史关联导入

从 WSL 调用 `bash scripts/import_canonical_in_container.sh rosetta-canonical-20260922-004`。脚本只读取原 Rosetta checkout 和既存 runs，在离线 Linux Docker 中以 2 CPU / 1 GiB 流式计算 SHA256；仅新建 Basin `outputs/rosetta-canonical-20260922-004`。改用新目录名可重做，已有输出绝不覆盖。

`history` 的 7 个观察单元覆盖 canonical training、2500/5000 checkpoint、004/005 Gate、保存数据及原报告字节。`identity-report.json` 记录每个指针、来源相对路径、声明 SHA、实测 SHA 与 match/missing/mismatch。原始 training/Gate JSON 字节由 `canonical-original-reports/artifacts` 保留；生成的 native envelope 另有独立哈希，不能冒充上游封存。`basin_check_identity` 用于逐个原文件核对，来源目录通过只读 alias 提供。

本次 004 的 57 项 match 明确分成 55 项 `prior_claim_vs_source_bytes` 与 2 项 `two_recorded_claims_compared`；0 mismatch。前者含 2500/5000 checkpoint 的 33 个文件、004/005 Gate4 报告和 handoff manifest 的独立封存链、Gate3 报告、artifact manifest、模型、当前 checkout 中 7 个登记源码/config 路径、保存数据 5 个文件。Gate4 报告 SHA 来自已有 `handoff-manifest.json/files`，该 manifest 的 SHA 又与已有 `transfer-receipt.json:manifest_sha256` 相符，已复核两层原始字节。两个 plan SHA 仅是 Gate4 报告与 gate-seal 的**两个记录声明相符**。22 项 missing 使用 `computed_at_import`：2 个保存数据 manifest 和 20 个保留的原报告/收据在先前 inventory 中没有事先 SHA seal；本次已记录它们的实测 SHA 和原始字节，不能把这次新算的哈希倒填为历史认证。004/005 的 Gate 4 均为历史报告结果，脚本没有模型执行或重新评估；checkpoint 字节匹配也不能推出训练过程或 M2 验收成功。

首轮 `outputs/rosetta-canonical-20260922-001` 在发现两个未事先封存的数据 manifest 后按门禁退出，第二轮 `...-002` 保留相同缺口分类。003 增加了未封存分类和报告原始字节，但两项 Gate4 报告对照来自同一原文件的本次哈希，不能计作历史封存匹配；004 已改为 handoff/receipt 的已有声明。旧输出原样保存。
