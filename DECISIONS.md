# 设计决策记录

## ADR-082：M01 仅在冻结教学域受限关闭，C00 只开放静态合同

- 日期：2026-08-03
- 状态：已实施；M01=`DONE_WITH_LIMITATION/E3`，C00=`CONTRACT_PLANNING_OPEN/E0`，电路执行仍关闭。
- 独立 E3 提交 `5d2134c` 推送并同步后，按既有 M01 验收逐项判断：同一 247 行目标条件、明确模型边界、两路输出与差异持久化、R11 语法/工具预检持久化均满足。`config/m01_simulator_cross_check_contract.json` 预先规定 M01 验收是完整可审计的两路线比较及限制说明，不以强制方程一致为门槛。
- R03 42/30/24 E3/E2/E3 还独立复现最大绝对/对数差 `4.3706900078321897e-19 A/cm`/`2.7533531010703882e-14 decade`。因此接受范围仅为 R03 portable IGZO 教学候选、冻结 247 行与 ngspice/GPL-Xyce 行为路线，并登记 `M01_TEACHING_MODEL_ONLY_PASS`。
- 旧根状态 `preflight_failed_tool_provenance/E0`、未授权 AIM-Spice、全部 Xyce build/tool 失败、R01 39/40、R02 路线分歧及根因链均继续作为不可改写历史证据，不因受限关闭而改标。
- 本决定不建立原生 AIM-Spice Level 15、HSPICE Level 61、方程身份、物理 IGZO 参数、实验校准、外部验证、正式电路结果或流片能力。C00 只允许建立并静态检查版本化双栅 IGZO 有源负载反相器合同；合同 PASS 状态另行提交前不得生成或运行正式电路网表，C01/C02/C03、版图、PEX 和 HZO 均关闭。

## ADR-081：R03 独立 E3 复现机器精度级路线一致，收口决定另设提交门

- 日期：2026-08-03
- 状态：已实施，E3；R03 静态/runner/独立三门唯一返回 42/42 E3、30/30 E2、24/24 E3，M01/C00 尚未关闭。
- runner PASS 提交 `6f4e89b` 推送并同步后，唯一执行 `make m01-open-source-device-dc-r03-check`。标准库 checker 启动 0 个进程并返回 24/24 PASS；报告 `results/reports/m01_open_source_cross_check_r03_check.json` SHA-256 为 `5419f34b20861561137ad19768af4783e4e7372265cc42ccb5abf27c2691a937`。
- checker 独立再生两个 247 器件 ASCII 网表，解析 ngspice raw 与 Xyce PRN，精确重算两份 247 行路线表、30 行指标和 247 行差异，并复核全部 14 个 runner 哈希和两张 PNG 尺寸。最大绝对/对数路线差仍为 `4.3706900078321897e-19 A/cm`/`2.7533531010703882e-14 decade`。
- 该 E3 在冻结 IGZO-only 教学模型和预注册 247 行域内独立复现机器精度级两路线一致；R02 的历史路线分歧与根因最小点边界继续保留。它不证明方程身份、原生 HSPICE Level 61、物理 IGZO 参数、实验校准、外部验证、正式敏感性、P2/T03、电路、版图、PEX 或 HZO。
- 按独立报告的 next gate，必须先提交并推送本 E3 登记，之后才能单独判断 M01 是否在声明的教学模型边界内关闭、C00 是否可开放。该判断前不运行 C00，R03 runner/独立 checker 和所有历史 revision 均不重跑。

## ADR-080：R03 runner 的机器精度级路线一致只打开独立落盘复核

- 日期：2026-08-03
- 状态：已实施，E2；静态合同 42/42 E3 后，两路线 runner 唯一返回 30/30 PASS，24 项独立 checker 尚未运行。
- 静态 PASS 登记提交 `e664629` 推送并同步后，唯一执行 `make m01-open-source-device-dc-r03`。报告 `results/reports/m01_open_source_cross_check_r03.json` SHA-256 为 `df188515d5749735fc479998d42d8b4b92ce84d2f40687801c531cc563249c79`。
- runner 恰好启动一个串行 ngspice 和一个串行 GPL Xyce 器件 DC 进程，均返回 0；两份 247 器件 ASCII 网表、两份有限 247 行路线表、30 行指标、247 行差异、14 个哈希绑定产物和两张非空图均落盘。AIM-Spice、TCAD、电路和下游进程为 0。
- 最大绝对路线差为 `4.3706900078321897e-19 A/cm`，最大对数差为 `2.7533531010703882e-14 decade`；两路最大电流分别为 `4.6825230492225634e-4` 与 `4.6825230492225607e-4 A/cm`。这支持“runner 在显式 clamp 候选上观察到机器精度级一致”，但差值按合同只作诊断，不是 PASS 阈值，独立 E3 尚未建立。
- E2 只证明冻结教学模型的完整有限器件级执行。它不证明方程身份、原生 HSPICE Level 61、物理 IGZO 参数、实验校准、外部验证、正式敏感性、P2/T03、M01/C00、电路、版图、PEX 或 HZO。
- 下一门是先提交并推送本 E2 状态及全部产物，再唯一运行 24 项零进程独立落盘复核。R03 runner、R02 正式器件 DC、根因探针和全部历史 revision 均不重跑。

## ADR-079：R03 42/42 静态 PASS 只打开已提交两路线 runner

- 日期：2026-08-03
- 状态：已实施，E3；静态合同唯一返回 42/42 PASS，两路线 runner 和 24 项独立检查均未运行。
- 实现提交 `50066b7` 推送并同步后，唯一执行 `make m01-open-source-device-dc-r03-contract-check`。报告 `results/reports/m01_open_source_device_dc_contract_r03.json` SHA-256 为 `a30611ad98941bcc576335e2b47f702c4c210d32d16247f42b65356a07c0237a`。
- 检查器验证不可变 R02 正式器件 40/30/24 与根因 R02 40/30/22 链、247 行/13 曲线、五处候选替换、参数和 `BIDS` 行字节一致、两路命令、42/30/24 注册、精确两进程预算、排他输出、失败保留和 no-downstream 边界；启动 0 个 build/simulator process，创建 0 个器件网表和 0 个数值输出。
- 该 PASS 只建立可审查的 R03 执行合同，不是器件 DC、路线一致、方程身份、物理参数、实验校准、正式敏感性、P2/T03、正式 M01、C00、电路、版图、PEX 或 HZO 证据。R02 路线分歧和根因 R02 最小点边界不可改写。
- 下一门是提交并推送 E3 状态后唯一运行 R03 两路线 runner；runner PASS 另行提交前不得运行独立 checker 或 C00。

## ADR-078：R03 以显式 clamp 建立可移植完整器件合同，静态门先于路线执行

- 日期：2026-08-03
- 状态：已实施，当前 E0；42 项静态合同、两路线 runner 和 24 项独立检查均未运行。
- `M01_OPEN_SOURCE_DEVICE_DC_R03` 使用独立配置、源码、候选和输出命名空间，绑定提交 `2ffac20` 下不可改写的正式器件 R02 40/30/24 链与根因 R02 40/30/22 E3/E2/E3 链。R02 的路线分歧和最小点语义诊断不被改写。
- 新候选只允许五处登记替换：版本/执行注释、子电路开始/结束标识，以及唯一语义替换 `limit(x/s,-60,60)` -> `min(max(x/s,-60),60)`。所有参数和 `BIDS` 行必须逐字节相同；同一候选字节供 ngspice/Xyce 两条路线使用，仍不宣称方程身份或物理参数。
- R03 冻结 247 个目标行、13 条曲线、两个 247 器件 ASCII 网表、每路一个串行进程、42/30/24 注册、排他输出、失败保留和 no-downstream 边界。未来静态 checker 不得启动 simulator/subprocess、生成网表或数值输出；runner 必须等待已提交的 42/42 E3 静态 PASS，独立 checker 必须等待已提交 runner PASS。
- 本实现只证明合同可审查性（E0），不是静态 PASS、器件仿真、路线一致、正式敏感性、P2/T03、正式 M01、物理参数、实验校准、C00、电路、版图、PEX 或 HZO 证据。先提交并推送实现，再唯一运行 42 项静态合同；P2/T03 和全部下游保持关闭。

## ADR-077：R02 独立 E3 关闭最小根因诊断并转入新 247 行合同

- 日期：2026-08-03
- 状态：`M01_ROUTE_DIVERGENCE_ROOT_CAUSE_R02` 静态/runner/独立三门唯一返回 40/40 E3、30/30 E2、22/22 E3；完整 247 行路线一致仍为 false。
- E2 提交 `406cfce` 推送并同步后，标准库独立 checker 唯一运行且启动零进程。报告 `results/reports/m01_route_divergence_root_cause_r02_check.json` SHA-256 为 `06878ca53aefc1dea557b6eb5838ea48e1bf7459a825d1ee99d996ef1b74d556`；它独立再生两份最小网表、重算 9 个 runner 产物哈希和 26 行表，并复现 `THREE_ARGUMENT_LIMIT_SEMANTICS_MISMATCH` 分类。
- 该 E3 只证明预注册点上的数值表达式语义根因和 bounded portable clamp；不接受一个完整器件模型，不证明物理 IGZO 参数、实验校准、正式敏感性、P2/T03、完整路线一致、正式 M01 或电路结果。
- 下一门是在新命名空间建立可移植完整器件候选及独立正式 247 行 ngspice/Xyce 合同。旧正式器件 R02 与根因 R02 均不重跑；新静态 PASS 提交前不得执行任一路线，C00、版图、PEX 和 HZO 继续关闭。

---

## ADR-076：R02 最小探针支持表达式语义根因，结论限于预注册点

- 日期：2026-08-03
- 状态：`M01_ROUTE_DIVERGENCE_ROOT_CAUSE_R02` runner 唯一返回 30/30、E2；22 项独立 checker 尚未运行。
- 静态 PASS 提交 `283cf32` 推送并同步后，runner 恰好启动一个串行 ngspice 和一个串行 Xyce 进程。报告 `results/reports/m01_route_divergence_root_cause_r02.json` SHA-256 为 `7b878ee2e109afb01d998f6a41c38723e5ed3d2f964ca859809dec205a019ddd`，网表、日志、命令记录、raw/PRN 和 26 行探针表均哈希保留。
- ngspice 三参数 `limit` 在输入 `-75/0.25/75` 上得到 `-15/60.25/135`，显式 clamp 与三个 portable 候选点通过；Xyce 三参数点与 clamp 一致。两路 1 V/1 kOhm 支路电流哨兵均通过。因此按预注册语义，`THREE_ARGUMENT_LIMIT_SEMANTICS_MISMATCH` 在这些最小点获得支持，支路电流提取替代解释被排除。
- 探针状态登记后的首次项目检查为 753/756；过宽机器状态补丁临时改变不可变的开源恢复、R11 与 R01 历史块。失败报告 SHA-256 `6821a18e74ae21b433f1e732005391e619c5db7a39540b2f6b6b93df35ee3684` 原样保留并记录零模拟器进程；修正仅恢复历史块且只登记 R02，随后 756/756 PASS，不改变探针产物、诊断、输入或门槛。
- 该结论不外推为完整 247 行路线一致、方程身份、接受的新器件模型、物理 IGZO 参数、实验校准、正式敏感性、P2/T03、正式 M01 或电路证据。先提交推送 E2 结果，再唯一执行 22 项独立落盘复核；P3、P5、C00、SPICE 电路、版图、PEX 和 HZO 继续关闭。

---

## ADR-075：R02 静态合同 40/40 E3 仅打开提交后的最小探针

- 日期：2026-08-03
- 状态：`M01_ROUTE_DIVERGENCE_ROOT_CAUSE_R02` 唯一静态检查 40/40、E3；探针 runner 与独立 checker 尚未运行。
- R02 静态合同在实施提交 `91fe397` 推送并同步后唯一执行，报告 `results/reports/m01_route_divergence_root_cause_contract_r02.json` SHA-256 为 `2870566c9bd6b3f5b0b4db796492afc75a55a5500d630dfa291e81a9ddb21169`。40 项全部通过，静态报告记录零模拟器进程、零网表和零数值输出。
- 登记 PASS 后首次项目总检查的 13 项失败全部来自历史 `next_scope` 白名单未接受合法的 execute-R02-probe 状态；归档 SHA-256 为 `518df893d4ee6a42ec3dd030957a62151eb752828f9d974a54633da921d8d23c`。只扩展状态白名单后 756/756 PASS，不修改合同、输入、阈值、探针预算或历史证据。
- 该 PASS 只验证 R01 失败绑定、三份诊断 CSV 的哈希与重算、状态一致的失败门及原有探针注册。表达式点、候选、工具、两进程串行预算、阈值、失败保留、IGZO-only 范围和 P2/T03/下游关闭门不变；不能写成根因确认、路线一致、物理参数、实验校准、正式敏感性、正式 M01 或电路结果。
- 只有本 PASS 状态提交并推送后，才允许按已冻结合同唯一启动一个 ngspice 和一个 Xyce 探针进程；探针完成后必须先保留失败，再运行 22 项独立落盘检查。P3、P5、SPICE 电路、版图、PEX 和 HZO 继续关闭。

---

## ADR-074：R02 只修正路线诊断证据源并保持静态门关闭

- 日期：2026-08-03
- 状态：已实施，当前证据 E0；R02 静态合同、根因探针和独立检查均未运行。
- R02 使用独立配置、源码和输出命名空间，绑定不可改写的 R01 提交 `203acaa`、R01 38/40 E0/FAIL 报告，以及正式器件 R02 已落盘并经独立复核的三份诊断 CSV（ngspice 原始表、Xyce 原始表和路线差异表）的 SHA-256。唯一逻辑修正是静态 checker 从这些实际持久化表重算最大电流/路线差异；不再读取不存在的 R02 runner 顶层 `route_diagnostics`。
- 表达式点、原始/可移植候选、工具与命令、两进程串行预算、阈值、失败保留、IGZO 范围和 no-downstream 边界全部继承 R01。R02 输出的 `next_gate` 按静态 PASS/FAIL 状态生成；失败仍必须保留且不得授权 runner。
- R02 实施只证明配置/源码/注册的可审查性，不是静态 PASS、根因确认、路线一致、物理参数、实验校准、正式 M01、P2/T03 敏感性或电路证据。先提交并推送 R02 实施态，再唯一运行 40 项静态合同；P3、P5、SPICE、电路、版图、PEX、HZO 和正式敏感性保持关闭。

---

## ADR-073：冻结路线分歧根因 R01 静态 schema 失败并转入 R02

- 日期：2026-08-03
- 状态：`M01_ROUTE_DIVERGENCE_ROOT_CAUSE_R01` 唯一静态检查 38/40、E0/FAIL；R01 不重跑，根因 runner/独立 checker 不开放。
- 实施提交 `015253f` 推送并同步后，R01 静态报告 `results/reports/m01_route_divergence_root_cause_contract_r01.json` SHA-256 为 `3aba1c829ca3aea4002f7ee285155a26c68837c9833ab88be3f475f336a34378`。报告记录零模拟器进程、零网表和零数值输出。
- 唯一实质失败是 `observation:r02_divergence_values`：checker 从不可改写的 R02 runner 报告读取不存在的顶层 `route_diagnostics` 字段；`result:static_ready` 仅因前置失败连带失败。该失败是 checker/schema 问题，不是 ngspice、Xyce、器件、路线、物理参数或假设的数值结论。
- R01 失败报告的 `next_gate` 是 checker 无条件写出的旧提示，不是运行授权；runner 的已提交 40/40 E3 门仍关闭。R02 必须使用新配置/源码/输出命名空间，只修正 R02 诊断证据读取为实际哈希绑定的落盘表或已独立验证的机器字段，并使失败提示与状态一致；不改变表达式点、候选、工具、进程预算、阈值、失败保留、IGZO 范围或下游关闭门。
- 在新 R02 静态 PASS 提交推送前，不得运行 ngspice/Xyce 根因探针；P3、P5、SPICE、电路、版图、PEX、HZO 和 C00 继续关闭。

---

## ADR-072：以最小表达式与支路哨兵合同隔离 R02 路线分歧

- 日期：2026-08-03
- 状态：`M01_ROUTE_DIVERGENCE_ROOT_CAUSE_R01` 40/30/22 实施完成，当前 E0；40 项静态合同、最小 runner 和独立 checker 均未运行。
- 不重跑 R02 247 行正式 DC，也不修改候选文件。R01 哈希绑定提交 `6e61c5d` 的 R02 40/30/24 报告、两份原生输出、冻结候选 `limit(x/s,-60,60)` 字节、ngspice `No compatibility mode selected!` 日志和本地 Xyce 7.10 表达式源码哈希。
- 预先假设是：ngspice-42 默认模式未注入 PSPICE 三参数 clamp，而 Xyce 将 `LIMIT(x,y,z)` 实现为区间限幅。这仅是文档/源码支持的运行前假设，不是已确认根因。
- 未来 runner 只启动一个 ngspice 和一个 Xyce 串行进程。每路固定 3 个表达式输入 `-75/0.25/75`、1 个 1 V/1 kOhm 支路电流哨兵、3 个原始候选点与 3 个诊断副本点；副本唯一表达式变化为 `min(max(x/s,-60),60)`。支路哨兵、显式 clamp、原始表达式分歧和可移植表达式两路解析符合分别验收，不以某一个结果替代另一个。
- 实施期首次项目检查为 752/753，原因是转录 Xyce R02 PRN SHA-256 遗漏最后一位；第二次为 753/754，原因是禁止导入全文扫描命中自身审计字面量。两份失败报告均哈希保留且记录零模拟器进程；修正只恢复哈希字符并改为真实 import 行匹配，后续项目检查 755/755 PASS。
- 先提交并推送 E0 实施态，再唯一运行 40 项静态合同。静态 PASS 状态另行提交推送前不启动两进程探针；C00、电路、版图、PEX 和 HZO 继续关闭。

---

## ADR-071：R02 独立 E3 确认落盘完整与路线分歧，M01/C00 保持关闭

- 日期：2026-08-03
- 状态：R02 静态/runner/独立三门唯一执行 40/30/24 PASS，证据等级依次为 E3/E2/E3；M01 未关闭。
- runner 提交 `605cbe9` 推送并与 `origin/main` 同步后，唯一运行 `make m01-open-source-device-dc-r02-check`。独立 checker 未导入 runner、未调用 subprocess，启动 0 个进程并返回 24/24 PASS；报告 SHA-256 为 `8afc00cec09ab533b8b3be4fe200529cabf24d35054034d2888e3a9c498e5fac`。
- 独立复核再生两份 247 器件网表，解析 ngspice raw 与 Xyce PRN，精确重算 247+247 行路线表、30 行指标、247 行差异、14 个 runner 产物哈希、两个零漏压不变量集合和两张 2240x1760 PNG。该 E3 证明已落盘器件级数值证据可复算，不提升模型物理等级。
- 复算确认 ngspice 最大 `|ID|/W` 为 `2.0417057839146633e-31 A/cm`、Xyce 为 `4.6825230492225607e-4 A/cm`，最大绝对/对数差为 `4.6825230492225607e-4 A/cm`/`16.670479923821013 decade`。不得把 24/24、两个返回码为 0 或 diagnostic-only 阈值写成路线一致。
- 不事后修改 R02 PASS 门、目标、提取或阈值，也不重跑 R02。M01 和 C00 保持关闭；下一门是在任何新模拟器执行前建立并提交版本化路线分歧根因合同，只隔离 ngspice/Xyce 器件支路电流语义、最小控制、解析、失败保留与证据边界。

---

## ADR-070：R02 runner 30/30 E2 保留路线分歧并只开放独立复核

- 日期：2026-08-03
- 状态：R02 runner 唯一执行 30/30 PASS、E2；独立 checker 未运行。
- 静态 PASS 提交 `da7dde8` 推送并同步后，唯一运行 `make m01-open-source-device-dc-r02`。ngspice 与 GPL Xyce 各启动一个串行器件级 DC 进程并返回 0；报告 SHA-256 为 `3dd916bea81caf582757696674c3f1fe41576122a66fef4c24ff3dd204f53cac`，2 个 247 器件网表、247+247 原始行、30 指标行、247 差异行和 2 张图完整落盘。
- 路线数值明显分歧：ngspice 最大电流代理 `2.0417057839146633e-31 A/cm`，Xyce 最大 `4.6825230492225607e-4 A/cm`；最大绝对/对数路线差为 `4.6825230492225607e-4 A/cm`/`16.670479923821013 decade`。不得以两个返回码为 0 或 runner PASS 声称路线一致。
- R02 合同在执行前已固定路线对目标和路线差异为 diagnostic-only，不允许事后改成失败门或放宽/收紧阈值。因此 30/30 的含义限定为有限、完整、受控两进程执行和诊断保留，不是方程身份、物理参数、实验校准、外部验证、正式 M01 收口或电路可用性。
- 首次 runner 状态登记后的项目检查为 741/745；通用 JSON 补丁误命中 recovery、R11、R01 历史块且未命中 R02。失败报告哈希 `5e02032f...a72d` 原样保留；修正只恢复历史机器状态并精确登记 R02 E2，不改变 runner 结果或阶段门。
- 先提交并推送 runner E2 状态，再唯一运行 24 项独立落盘 checker。独立 PASS 提交前，R02 runner、R01/R11 不重跑，C00、版图、PEX 和 HZO 继续关闭。

---

## ADR-069：R02 静态 40/40 E3 只开放提交后的两路线 runner

- 日期：2026-08-03
- 状态：R02 schema-only 静态合同唯一执行 40/40 PASS、E3；两路线 runner 与独立 checker 未运行。
- 实施提交 `86c5106` 推送并同步后，唯一运行 `make m01-open-source-device-dc-r02-contract-check`。报告 SHA-256 为 `0154abfbe5175b91d7622416804561c5bb50bdeeef0792e426d0299a37564d2c`，40 项全部通过。
- 报告验证 R11 实际 25/25 summary 与 independence PASS、R01 39/40 不可改写失败、247 行目标、同一 IGZO 候选、工具/命令、两个 247 器件网表合同、提取/指标、两进程预算、失败保留和 no-downstream 边界；记录零 build/simulator process、零器件网表和零数值输出。
- 该 E3 是静态合同证据，不是 ngspice/Xyce 器件 DC、路线一致性、物理参数、实验校准、正式 M01 或电路结果。必须先提交并推送本 PASS 状态，才允许一次 R02 两路线 runner；runner PASS 状态再提交前，独立 checker、C00、版图、PEX 和 HZO 继续关闭。

---

## ADR-068：R02 在三组件统一采用 R11 持久化 schema，并保留审计字面量

- 日期：2026-08-03
- `M01_OPEN_SOURCE_DEVICE_DC_R02` 使用独立 config/common/static-checker/runner/independent-checker/output 命名空间，哈希绑定提交 `7d5f079` 中不可改写的 R01 五个源文件和 39/40 失败报告。
- 唯一逻辑修正同时应用于 R02 静态 checker、runner 和独立 checker：要求 R11 独立报告 `summary.check_count/passed/failed=25/25/0` 且 `independence:no_runner_or_process_import=PASS`，不再读取不存在的顶层 `processes_invoked`。这样静态门与未来运行前置门使用同一持久化 schema。
- R02 静态 checker 仍保留旧字段字符串作为 runner/independent 源码审计条件。首次项目总检查误把该审计字面量当成可执行旧读取并失败，报告 `bc7fed2c...34221` 保留；项目检查只改为禁止旧可执行条件，不删除审计能力或放宽任何门。
- R02 维持 40/30/24 注册、247 行、候选字节、两条 argv、两进程串行预算、两份 247 器件网表、提取/指标/差异/图、阈值、排他输出、失败保留与 no-downstream 边界。实施提交前不执行静态合同，静态 PASS 提交前不执行两路线。

---

## ADR-067：R01 39/40 schema 断言失败冻结，R02 只修正持久化字段读取

- 日期：2026-08-03
- R01 实施提交 `b8c3a03` 推送后，40 项静态合同唯一返回 39/40、E0/FAIL。唯一失败项要求不可改写的 R11 独立报告具有顶层 `processes_invoked=0`，但该报告没有此字段；它通过已登记的 no-runner/no-process 检查表达同一边界。
- R01 报告哈希为 `7baba2fcd7bc186bfa30780882816c27d33708c91957e0a53db51c8c435b16ba`，记录零 build/simulator process、零器件网表、零数值输出，并证明运行前正式路径全缺失。该失败是 checker-schema 缺陷，不是器件、模拟器、输入、物理或权限失败。
- R01 config/checker/common/runner/independent 与报告全部冻结且不得重跑。R02 必须使用新 config/source/output 命名空间，只把错误字段读取替换为对 R11 25/25 报告既有 summary/检查项的 schema-aware 复核；247 行、候选字节、两进程预算、网表、提取、阈值、失败保留和证据边界不变。
- R02 静态 PASS 状态提交并推送前，ngspice/Xyce 正式路线、独立 checker、C00、版图、PEX 和 HZO 均保持关闭。

---

## ADR-066：正式 M01 采用两份 247 器件单点 DC 网表和严格两进程预算

- 日期：2026-08-03
- 状态：R01 后续唯一静态检查为 39/40、E0/FAIL；本 ADR 的器件/进程/提取合同不变，正式器件 DC 继续关闭。
- 两路线使用完全相同的 `IGZO_DG_BEHAVIORAL_R02` 候选字节和 247 行冻结目标，但不宣称方程身份。选择清单唯一决定执行顺序；预测表按稳定 `row_uid` 连接，不能要求两文件物理排序相同。
- 每路线生成一个 ASCII 仓库相对网表，包含 247 个独立 IGZO 子电路、各自 VDS/VTG/VBG 源和一个 dummy 单点 DC sweep。ngspice 与 GPL Xyce 各启动一次且串行，总进程预算 2；AIM-Spice、TCAD、电路、瞬态、SnO、HZO 和下游进程为 0。
- 提取固定为 `abs(I(VDS))/(W_um*1e-4)`；输出固定为每路线 247 原始行、26 曲线 + 4 split 聚合指标行、247 路线差异行和两图。路线对目标误差与路线差异必须报告但不是事后调参门；完整、有限、零 VDS 和落盘完整性才是执行门。
- 首次项目检查器错误要求预测表与选择清单同序并留下 1 项失败归档；修正只采用既有 UID 映射，不改输入、方程、阈值或路线。实现提交后只允许唯一一次 40 项静态合同，PASS 状态再提交前不得运行两路线。

---

## ADR-065：R11 独立 25/25 E3 关闭工具/parser 预检，不直接开放器件执行

- 日期：2026-08-03
- 状态：R11 静态 36/36 E3、runner 32/32 E2、独立检查 25/25 E3 全部 PASS；正式 M01 器件 DC 尚未建立执行合同。
- runner PASS 提交 `0660dab` 推送并同步后，唯一执行 `make m01-xyce-build-preflight-r11-check`。独立 checker 不导入 runner 或 `subprocess`，只读重算已落盘证据并返回 25/25 PASS；报告 SHA-256 为 `792a4f6d4be65746fc08ff0c00205acc2f7b64bc5ad2d3f0c370d27c41d2d615`。
- 复核覆盖 runner 32/32、19 个历史绑定、R07 完整 generator/Xyce 安装树和二进制、1.25 V 固定列 `.prn`、相对 ASCII include parser-only 输入/日志、4 条命令、manifest、正式输出缺失和无进程独立性。该 E3 只关闭工具/parser 预检，不验证 IGZO 方程、器件曲线、物理参数、实验校准、正式 SPICE 数值或电路。
- 下一阶段必须先用新命名空间建立并提交正式 M01 两路线器件 DC 执行合同，冻结 ngspice/Xyce 工具绑定、247 行目标、网表生成、输出解析、指标、失败保留、进程预算和证据边界。静态合同 PASS 再提交前不得执行任一路线；R11/R10 和更早预检不重跑，C00 与全部下游继续关闭。

---

## ADR-064：R11 runner 32/32 E2 PASS 后仅开放独立落盘检查

- 日期：2026-08-03
- 状态：R11 runner 唯一运行 32/32 PASS、E2；独立 checker 尚未运行，正式 M01 器件 DC 继续关闭。
- 在静态合同 PASS 提交 `b38b319` 推送并与 `origin/main` 同步后，唯一执行 `make m01-xyce-build-preflight-r11`。版本、许可证、控制标量 B-source 和仓库相对 ASCII include 的 `-syntax` 共 4 个允许的 Xyce 工具/parser 进程均返回 0，固定列 `.prn` 观测为 1.25 V；报告 SHA-256 为 `cfe369d5df97217499f207701836447f784f5dbc201ad33b01a0b1765841d552`。
- 32/32 E2 只证明 hash-bound Xyce 工具、输出解析、自测和路径安全 parser-only 预检通过；它不是正式 IGZO 器件 DC、方程/器件曲线、物理参数、实验校准、SPICE 数值或电路证据。没有构建、formal device DC、ngspice、AIM-Spice、数值 M01 或下游进程。
- runner 报告、`preflight.log`、两个 manifest、B-source `.cir/.log/.prn`、版本/许可证/命令日志和 parser-only 输入/日志全部按 SHA-256 保留。下一门是提交并推送本 E2 状态后唯一运行 25 项独立持久化检查；只有独立 E3 PASS 再提交后才建立正式 M01 两路线器件 DC 合同，R10 和更早 revision 不重跑。

---

## ADR-063：R11 静态合同 36/36 E3 后仅开放提交后的 runner

- 日期：2026-08-03
- 状态：R11 静态 checker 唯一执行 36/36 PASS、E3；runner 与独立 checker 未运行。
- R11 实施提交 `f64dc16` 推送并与 `origin/main` 同步后，唯一运行 `make m01-xyce-build-preflight-r11-contract-check`。报告 SHA-256 为 `73ebc2bd650411e91d7bb704a8d2b26938f47e1a0d83332fd1f5b9e37164e400`。
- 36 项检查验证 R10 静态/失败归档和 8 文件部分树未改变、R10 不重跑、冻结 IGZO candidate 使用仓库相对 ASCII include、runner cwd 为 project root、36/32/25 注册完整以及正式/下游门关闭。
- 报告记录 0 个 build/simulator process、无器件网表和数值输出。该 PASS 只是路径安全工具/输出合同证据，不是 Xyce parser 执行、IGZO 方程/器件曲线、物理参数、实验校准、正式 M01、SPICE 或电路证据。
- 先提交并推送 36/36 E3 状态，再唯一运行 32 项 R11 工具/parser runner；只有 runner PASS 状态另行提交并推送后才允许 25 项独立落盘检查。R10 与更早 revision 均不重跑，正式器件 DC 和下游继续关闭。

---

## ADR-062：R11 只修正 parser include 的 Unicode 路径表示

- 日期：2026-08-03
- 状态：已实施，36 项静态合同尚未运行；当前证据 E0。
- R11 使用全新 config/common/static-checker/runner/independent-checker/report/output 命名空间，绑定提交 `63be6a4` 下不可改写的 R10 配置、源码、36/36 E3 静态报告、E0 Unicode 路径失败报告/日志和 8 文件部分运行树。
- 唯一恢复变化是把冻结候选 `spice/models/igzo_dg_behavioral_r02.inc` 写成仓库相对 ASCII `.include`，并显式固定未来 runner 的 cwd 为 project root；生成前同时断言路径相对、ASCII、与配置一致，且网表不含绝对工程路径。
- R07 Xyce 二进制/完整安装树哈希、四命令白名单、1.25 V B-source 自测、36/32/25 注册、阈值、失败保留、no-build/no-ngspice/no-AIM-Spice/no-formal-DC 和 downstream closure 全部不变。R10 不重跑，R11 当前没有任何报告、Xyce 进程、parser-only 结果、器件曲线或正式 M01 输出。
- 下一门是提交并推送 R11 实施后唯一运行纯静态 36 项合同。只有 36/36 PASS 状态另行提交并推送后，才允许一次 R11 runner；这仍不开放正式器件 DC、电路、版图、PEX 或 HZO。

---

## ADR-061：保留 R10 Unicode 路径运行器失败并转入 R11

- 日期：2026-08-03
- 状态：R10 runner 唯一执行后为 E0/FAIL；parser-only 与独立 checker 未运行，R11 待建立。
- R10 36/36 E3 静态 PASS 已提交为 `8dff9ad`。随后唯一运行 `make m01-xyce-build-preflight-r10`，Xyce 版本、GPL 许可证和标量 B-source 三条命令均返回 0，固定列 `.prn` 解析得到冻结预期 1.25 V。
- 失败发生在第四条 Xyce 命令之前：runner 将中文工程绝对路径插入 parser-only `.include` 行，并以 ASCII 写入 `device_syntax.cir`，在 `scripts/run_m01_xyce_build_preflight_r10.py:336` 抛出 `UnicodeEncodeError`。因此这不是 Xyce parser、IGZO 方程、器件收敛、物理参数、实验校准或权限失败。
- 失败报告、伴随日志和 8 文件部分目录全部保留；目录树 SHA-256 为 `5a3d1ac4ff62848fb7132db9211a6281a477b43900e87ddfe6047f6da9fef85e`，其中 `device_syntax.cir` 是失败写入留下的零字节占位文件。审计记录 0 个 build、3 个 Xyce 工具进程、无 parser-only 进程、无正式 DC、无数值 M01 输出、无 ngspice/AIM-Spice 和无下游进程。
- R10 配置、源码、静态报告和部分输出不可改写且不得重跑，R10 独立 checker 不运行。R11 必须使用全新 config/source/report/output 命名空间，只把 parser 网表改为不含中文绝对路径的显式路径安全表示，并继续绑定同一 IGZO 候选、R07 Xyce 二进制/安装树、四命令白名单、36/32/25 门和 no-downstream 边界。R11 静态 PASS 提交前不得启动 R11 runner。

---

## ADR-060：R10 静态合同 36/36 E3 后仅打开提交后的 runner 门

- 日期：2026-08-03
- 状态：R10 静态 checker 唯一执行 36/36 PASS、E3；R10 runner 与独立 checker 未运行。
- R10 实施提交 `bd7ebda` 推送后，唯一命令 `make m01-xyce-build-preflight-r10-contract-check` 验证 R07/R08/R09 历史哈希、allowlist、independent wording、独立命名空间、36/32/25 注册和 no-execution 边界；报告 SHA-256 为 `a7dbcf6d639897f6648d25a151d3a29c48c3dc352992a7872104b684b29fe785`。
- 报告明确 0 个 build/simulator process、无器件网表和数值输出。该 PASS 只证明静态工具/输出合同可审阅，不证明 Xyce 命令运行、parser-only 通过、IGZO 方程、器件曲线、物理参数、实验校准、正式 M01 或电路结果。
- 注册 PASS 后首次项目总检查为 683/684，唯一失败是历史 R08 状态允许列表未包含 execute-R10 scope；失败报告与哈希保留。只补入该已登记 scope 后总检查为 685/685，不改变合同、阈值、输入、结果或下游门。
- 先提交并推送本 36/36 E3 状态，再唯一运行 R10 32 项工具/parser runner；只有 runner PASS 状态提交后才允许 25 项独立持久化检查。R07/R08/R09 不重跑，正式 M01 DC、C00、电路、版图、PEX 和 HZO 继续关闭。

---

## ADR-059：R10 仅修正 R09 两项静态断言

- 日期：2026-08-03
- 状态：R10 合同已实施，静态 checker 尚未运行；当前 E0。
- R10 使用新的 config/common/static-checker/runner/independent-checker 和输出命名空间，继续冻结 36/32/25 项门。R09/R08/R07 的配置、源码、报告、日志和安装证据按 SHA-256 绑定且不得改写或重跑。
- R10 只修正 R09 已定位的两个合同问题：复用路径检查允许明确登记的 R08/R09 失败归档，`next_gate` 明确包含独立检查关闭条件。IGZO 候选、物理输入、Xyce 二进制/安装树、命令白名单、阈值和失败保留不变。
- R10 静态 checker 只能读文件、计算哈希并写自己的合同报告，必须记录 0 个 build/simulator process、无器件网表和数值输出。实施提交推送后才允许唯一运行 36 项静态合同；36/36 PASS 状态再次提交前不得启动 R10 runner。
- 即使未来 R10 静态 PASS，也只建立工具/输出合同证据，不是 Xyce parser 执行、IGZO 方程、器件曲线、物理参数、实验校准、正式 M01、SPICE 或电路结果。正式 M01 DC、C00、电路、版图、PEX 和 HZO 继续关闭。

---

## ADR-056：R08 静态合同注册表失败保留，转入 R09

- 日期：2026-08-03
- 状态：R08 静态 checker 唯一执行在报告生成前以 `expected=36 actual=30` 中止，E0/FAIL；R08 runner 与独立 checker 未运行

### 失败判定

- R08 实施提交 `95d6563` 推送并同步后，唯一静态命令 `make m01-xyce-build-preflight-r08-contract-check` 没有启动任何进程，但 checker 在自检注册表时发现实际只构造 30 个检查而预注册 36 个，未生成 R08 合同报告。
- 该结果是静态 checker 自身的注册缺陷，不是 Xyce 版本/许可证、`.prn` 自测、parser-only、IGZO 方程、器件收敛、权限、物理参数或 M01 数值失败。R08 配置、checker、runner、common 和实现提交均保持不可改写。

### 保留与下一门

- 失败报告 `results/reports/m01_xyce_build_preflight_contract_r08_registry_mismatch_failed.json` 和日志 `results/compact/m01_xyce_build_preflight_r08_contract_registry_mismatch_failed.log` 记录提交、源码哈希、期望/实际计数、0 个 build/simulator process、无网表/数值输出以及 R08 runner/独立检查未运行。
- R09 必须使用新配置/checker/runner/common/output namespace，只修正注册表缺陷并继续绑定 R08 失败与 R07 固定列 `.prn` 证据；不得重跑 R08/R07、不得放宽 no-execution、IGZO-only、失败保留或 downstream 关闭门。

## ADR-055：R08 只做 Xyce 固定列 `.prn` 输出/parser 恢复

- 日期：2026-08-03
- 状态：合同已实现，静态检查尚未运行，当前 E0

### 决策

- R07 的 42/47 E0/FAIL 是 runner 将实际 `.prn` 输出注册为 `.csv` 的输出合同缺陷；R07 配置、runner、报告、日志、`.prn`、安装树和独立检查未执行状态全部保持不可改写。
- R08 绑定真实 R07 提交 `9a7375ef30ae90adf5214b3c7421a5f7a8cab726`，只复用哈希匹配的完整 R07 generator/Xyce 安装前缀；不构建、不重建依赖、不使用 AIM-Spice/ngspice，不改变 IGZO 候选或数值门槛。
- R08 冻结 36 项静态合同、32 项 runner、25 项独立持久化检查。runner 只允许 Xyce 版本/许可证、标量 B-source `.prn` 解析和随后冻结 IGZO 候选的 parser-only `-syntax`；正式 M01 器件 DC、电路、版图、PEX 和 HZO 继续关闭。

### 阶段门

实现提交推送后才运行静态合同一次；只有 36/36 PASS 状态再次提交后才运行 R08 runner；只有 runner PASS 才运行独立 checker。任何失败均保留新命名空间并转入下一 revision，不覆盖 R07。

### 证据边界

R08 通过最多建立工具/输出合同证据，不是 IGZO 方程、器件曲线、物理参数、实验校准、正式 M01、SPICE 数值或电路结果。

## ADR-054：R07 Xyce `.prn` 输出格式失败保留，R08 只修正解析合同

- 日期：2026-08-03
- 状态：R07 runner 42/47、E0/FAIL 已唯一执行并冻结；R07 独立 checker 未运行；R08 待建立

### 事实与根因

- R07 静态合同 39/39、E3 后，M4/Bison/Flex 和串行纯源码 Xyce 7.10.0 均构建/安装成功；版本、GPL 许可证和 B-source 命令返回码均通过。
- Xyce 的 `-o` basename 输出为固定列 `.prn` 文件，实际 `bsource_self_test.prn` 含 `V(NOUT)=1.25000000e+00`。R07 配置把 output path 写成 `.csv`，runner 用 `csv.DictReader` 读取，观察值为空，停止 parser-only IGZO 候选门。
- 失败五项中两项是 self-test 输出/数值门，后续两项是未执行 parser-only 的依赖失败，最后一项是依赖命令未登记的 invocation audit；这不构成 Xyce 构建失败、器件仿真失败或物理参数证据。

### R08 边界

- R07 配置、静态报告、runner、失败报告和全部构建/自测证据保持不可改写，不运行 R07 独立 checker，不重跑 R07。
- R08 使用新配置、runner、独立 checker、报告/输出根；只修正 Xyce `.prn` 读取和 output suffix 注册，并显式绑定 R07 的完整 generator/Xyce 安装树和二进制 SHA-256。不得改变 IGZO 候选、物理输入、构建任务、数值阈值或正式 M01 门。
- R08 静态门通过并提交后才允许一次工具/自测 runner；runner PASS 后才允许独立持久化检查。正式 M01 器件 DC、ngspice 对照、电路、版图、PEX 和 HZO 继续关闭。

## ADR-053：R07 允许 runner 路径哈希绑定但禁止导入与进程执行

- 日期：2026-08-03
- 状态：R07 静态合同 39/39、E3 已唯一执行并冻结；runner 与独立 checker 尚未运行

### checker 修正

- 独立落盘检查必须知道 runner 路径，才能比较运行报告中的 runner SHA-256；因此 runner 文件名字面量本身不是执行耦合。R07 允许 `RUNNER_PATH` 登记该路径。
- 真正的独立性门改为源码可审计条件：独立 checker 不得 `import` R07 runner，不得导入或调用 `subprocess`，不得执行任何进程；只允许标准库读取、解析和哈希持久化证据。该修正不改变 25 项独立检查内容、数值门槛或证据边界。

### 复用与新根

- R07 哈希绑定 R06 配置、checker、36/37 报告和两份项目检查失败；R06 不修改、不重跑。M4/Bison/Flex 继续使用已冻结的官方归档与解压树，SuiteSparse/Trilinos 继续只复用 R05 完整树哈希前缀。
- generator、Xyce build/install、report 和 output 全部使用新的 `r07` 根；R05 partial Xyce 与所有 R06 Xyce/build/output 根均列入禁用清单。runner 持久化 `r06_xyce_or_outputs_reused=false`，独立 checker 复核该标记和实际 manifest 路径。
- R07 静态/runner/独立检查分别为 39/47/25 项。实施提交 `d421277` 推送后，静态合同唯一运行并返回 39/39 PASS、E3；报告 SHA-256 为 `2d8cfe605dd86f8313043e42834b4acbd916c165d8d1765758fa609aba0b7fdd`，记录 0 个构建/模拟器进程、无器件网表和数值输出。该 PASS 状态再次提交前不得构建；随后 runner 只允许一次且 PASS 后才运行独立复核。AIM-Spice 和正式 M01/下游继续关闭。

## ADR-052：R06 checker 路径字面量失败保留，R07 只修正可执行性断言

- 日期：2026-08-03
- 状态：R06 静态合同 36/37、E0/FAIL 已唯一执行并冻结；R07 待建立

### 失败判定

- R06 独立 checker 必须声明 runner 路径，才能对未来落盘 runner 哈希做独立绑定；静态 checker 却要求独立 checker 源码完全不含该 runner 文件名字面量。两项要求不可同时成立，唯一失败属于 checker 合同缺陷。
- R06 其余 36 项通过，报告记录 0 个 build/simulator process、无器件网表、无数值输出。该结果不说明 M4/Bison/Flex、Xyce、IGZO 候选、器件 DC 或电路失败，也不提升任何器件/物理证据。

### R07 边界

- R06 配置、checker 和 36/37 报告保持不可改写且不得重跑。R07 使用全新配置、checker、runner、独立 checker、build/install/report/output 根，并哈希绑定 R06 失败。
- R07 只把“源码不得出现 runner 文件名”替换为可审计的实际边界：独立 checker 不导入 runner、不导入或调用 `subprocess`，只读取并哈希持久化文件；其他来源、版本、树哈希、两任务、no-formal-device-DC、失败保留和验收门槛不变。
- R07 实施先提交推送，再唯一运行静态合同。静态 PASS 状态再次提交前不得构建生成器或 Xyce；AIM-Spice 永久排除，正式 M01 数值与下游继续关闭。
- 注册 R06 失败状态后的项目总检查首次为 653/658，原因仅是五个历史门的 `next_scope` 允许列表过期；失败报告保留。修正只加入已登记的 R06-failure-to-R07 scope，随后 659/659 PASS，不改变任何历史门状态或阈值。

## ADR-051：R06 采用纯源码生成器工具链并完整哈希复用 R05 依赖

- 日期：2026-08-03
- 状态：R06 合同、runner 与独立 checker 已实现，静态合同尚未运行，当前 E0

### 工具与复用决策

- 不修改系统 `/usr`，也不使用本机缺少可审计合法授权来源的 AIM-Spice。R06 固定 GNU M4 1.4.19、GNU Bison 3.8.2 和 Flex 2.6.4 官方 HTTPS 归档、实际 SHA-256、解压树 `configure` 与许可证哈希；未来在用户目录按 M4、Bison、Flex 顺序源码构建，并显式设置 `M4` 与 `BISON_PKGDATADIR`。
- R05 成功安装的 SuiteSparse 与 Trilinos 以相对路径、模式、大小、逐文件内容哈希和符号链接目标形成完整树摘要；R06 只允许复用这两个前缀，禁止重建它们，禁止复用 R05 partial Xyce。所有 R06 generator/Xyce build、install、report 和 output 根均为新的 `r06` 命名空间，最多两任务、MPI/Fortran 关闭。
- 工具链安装后先运行最小 Bison/Flex C 源生成冒烟，再配置 Xyce；Xyce 生成后仍先做 1.25 V 标量 B-source 自测，再做冻结 IGZO 候选的 `-syntax` parser-only 检查。两者都不是正式器件 DC 或 SPICE 路线数值。

### 阶段门与失败保留

- R06 静态合同、未来 runner 与独立落盘检查分别冻结 37/47/25 项。当前只完成实现和官方源码准备，合同报告、构建根、工具链前缀、Xyce 前缀及全部 R06 输出均不存在；不得写成合同通过、Xyce 已构建或 M01 数值完成。
- 开发期首次 `make check` 为 655/656，原因是总检查器把合同 checker 中审计用的 `import subprocess` 字符串误判为真实 import。报告已归档；修正为行首 import 匹配后 657/657 PASS。该失败不是 R06 静态合同、构建或模拟器失败，也没有放宽门槛。
- 先提交推送合同实施，再唯一运行 R06 静态合同。只有 37/37 PASS 且状态提交后才执行一次 runner；runner PASS 才执行独立检查。正式 M01 器件 DC、C00、电路、版图、PEX 和 HZO 继续关闭。

## ADR-050：保留 R05 生成器工具链失败并转入 R06

- 日期：2026-08-03
- 状态：R05 build/tool runner 唯一运行 19/29、E0/FAIL；独立检查按门未运行

### 失败判定

- SuiteSparse AMD-only 和 serial MPI/Fortran-off Trilinos 均配置、构建、安装成功；Trilinos build/install 耗时 1068.870 s。Xyce 配置成功并发现所需依赖，说明 R02 以来的显式 BLAS/LAPACK 修正有效。
- Xyce build 在 0% 的 Bison/Flex 生成步骤停止：`/usr/bin/m4` 不存在，用户目录 Bison 的数据文件存在于 `/home/reachgao/.local/toolchain/usr/share/bison`，但二进制默认查找 `/usr/share/bison`。因此这是本地生成器工具链打包/路径失败，不是 Xyce C++ 编译、IGZO 器件或 SPICE 数值失败。
- 报告 SHA-256 为 `893e890b561298cde332cfcd5f466ab34d706dd46ae26f506701bc3772cc7ffc`。未产生 Xyce 二进制、自测、parser-only 候选调用或数值输出；其余九项失败是前置二进制缺失及 invocation audit 的连锁结果。

### R06 范围

- R05 报告、日志、manifest、成功的 SuiteSparse/Trilinos 安装和 partial Xyce build 全部不可改写。R06 可通过路径与哈希复用成功安装的两项依赖，避免在普通笔记本重复约 17.8 分钟的 Trilinos 构建；不得复用 R05 partial Xyce build。
- R06 必须先冻结并验证完整 M4/Bison/Flex 工具链及数据目录，使用新的 Xyce build/install/report/output 根，并绑定 R05 19/29 失败。R06 合同通过并提交前不得运行 Xyce build、自测或候选解析；正式 M01 器件 DC 和下游继续关闭。

## ADR-049：R05 静态合同通过后只打开 build/tool 预检门

- 日期：2026-08-03
- 状态：R05 静态合同唯一检查 27/27 PASS、E3；R05 build/tool runner 尚未执行

### 结果与证据边界

- 提交 `1c95347` 推送后唯一运行 R05 checker，报告 SHA-256 为 `4c45dbd06b53aa55b0fcdea88a4e3cc5fdacc889162102cecf4fefecce4b6262`。27 项全部通过，模拟器进程、器件网表和数值输出计数均为零。
- E3 只证明 R05 合同及失败绑定可审计，不证明 SuiteSparse/Trilinos/Xyce 已构建、B-source 自测或 parser-only 候选检查通过，也不形成器件、SPICE 数值、物理参数、实验校准或电路证据。

### 下一门

- 本状态提交并推送后只允许 R05 build/tool runner 一次。runner 失败则原样保留并停止；只有 runner PASS 才运行不调用模拟器的独立落盘检查。两者均 PASS 前，正式 M01 两路线器件 DC 和全部下游保持关闭。

## ADR-048：保留 R04 状态断言失败并转入 R05

- 日期：2026-08-03
- 状态：R04 静态合同唯一检查 25/26、E0/FAIL；无构建或模拟器执行，R05 只修正机器状态字面量

### 失败判定

- R04 报告 `results/reports/m01_xyce_build_preflight_contract_r04.json` 的 SHA-256 为 `bc5dcd446fa9bc613504458cac4ac58351e1a594f6764cba5bb9f4e448e7448e`，25 项 PASS，唯一 FAIL 为 `experiment:r04_is_planned_and_prior_failures_bound`。
- 失败来自 checker 将实验机器记录的 `contract_planned` 错写成 `preflight_planned`；不是 SuiteSparse/Trilinos/Xyce 构建、自测、候选解析、器件 DC 或 SPICE 数值失败。R04 配置、checker 和报告不得改写或重跑。

### R05 范围与阶段门

- R05 使用新的配置、checker、wrapper、报告、构建和输出命名空间，新增对 R04 报告哈希及 25/26 状态的不可变绑定。唯一接口修正是按已提交机器配置断言 `contract_planned`；物理输入、IGZO 候选、BLAS/LAPACK、两任务预算、MPI/Fortran、阈值和 no-downstream 规则不变。
- 提交并推送 R05 后只运行 27 项静态合同检查一次。即使 PASS，也只打开 R05 build/tool 预检门；正式 M01 器件 DC、C00、电路、版图、PEX 和 HZO 仍关闭。

## ADR-047：R04 绑定 R03 失败并修正合同接口断言

- 日期：2026-08-03
- 状态：R04 合同已实现并唯一检查 25/26、E0/FAIL；R01/R02/R03/R04 失败保持不可改写

### 修正范围

- R04 使用 26 项静态检查和独立 `r04` 输出命名空间，绑定 R03 报告 `be516ad9d0f8998cf3b0e9e441f45312d9d7db21e1934fa3df5cfc18b4f6c3c3` 及其 21/25、E0/FAIL 状态。
- 只修正三类已观测 checker 断言：实际机器状态 `contract_planned`、实际包装器底层文件名 `run_m01_xyce_build_preflight.py`/`check_m01_xyce_build_preflight.py`，以及 R03 失败边界的显式字面量绑定。IGZO 候选、BLAS/LAPACK、serial 两任务、MPI/Fortran、物理输入、split、阈值和 no-downstream 规则不变。

### 阶段门

- 提交并推送 R04 后执行的唯一静态合同检查没有构建或启动任何模拟器，也没有创建器件网表或数值输出；其 25/26 失败按 ADR-048 转入 R05。

## ADR-046：保留 R03 Xyce 合同检查器失败并转入 R04

- 日期：2026-08-03
- 状态：R03 静态合同唯一检查 21/25、E0/FAIL；无构建或模拟器执行，R04 只修正 checker 断言

### 失败与保留

- 在提交 `b9a103b` 推送后，`make m01-xyce-build-preflight-r03-contract-check` 只生成 `results/reports/m01_xyce_build_preflight_contract_r03.json`，返回 21/25。报告 SHA-256 为 `be516ad9d0f8998cf3b0e9e441f45312d9d7db21e1934fa3df5cfc18b4f6c3c3`，必须原样保留。
- 四个失败均属于 checker 合同断言：实验记录仍期待 `preflight_planned` 而实际机器枚举为 `contract_planned`，两个 wrapper 静态检查寻找不存在的 R01 文件名，形式门要求证据边界中有未登记的 `R01` 字面量。R03 没有调用 subprocess、构建依赖、启动 Xyce/ngspice/AIM-Spice、生成器件网表或数值输出。

### R04 范围

- R04 使用新的配置、checker、wrapper、报告和输出命名空间，绑定 R03 报告哈希；只把上述状态/文件名/字面量断言改为实际已提交接口，不改变 IGZO 候选、BLAS/LAPACK 路径、构建预算、物理输入、split、阈值或失败保留规则。
- R01 14/29、9/20，R02 22/25 和 R03 21/25 都是不可改写的 E0 失败证据。R04 合同即使通过，也只打开后续 build/tool 预检门，不是 Xyce 二进制、器件仿真、SPICE 数值、物理参数、实验校准或电路证据。

## ADR-045：R03 只修正 Xyce 预检合同边界，不重跑历史失败

- 日期：2026-08-03
- 状态：R03 合同已实现，静态检查尚未运行；R01/R02 失败保持 E0/FAIL，M01 数值执行关闭

### 修正范围

- R03 绑定并保持 R01 的 14/29 runner、9/20 独立检查失败和 R02 的 22/25 静态合同失败；两份报告、日志、manifest、partial cache 和哈希均不可覆盖。
- 候选范围检查改为完整词边界，避免 `translation` 之类普通注释被 `tran` 子串规则误判。runner 与独立 checker 明确登记 `formal_device_dc_invoked=false` 和 20 项独立检查标记，且使用独立 `r03` 构建/输出根。
- 显式用户目录 `libblas.so`/`liblapack.so`、serial 两任务、MPI/Fortran 关闭、IGZO-only 候选、失败保留和 no-downstream 门均保持不变；不改物理输入、M00 split、器件候选字节或验收阈值。

### 阶段门与证据边界

- 提交并推送 R03 后只允许静态合同检查一次。合同检查自身不得构建 SuiteSparse/Trilinos/Xyce，不得启动 ngspice/AIM-Spice，不得生成器件网表或数值表。
- 即使 R03 合同 PASS，也只证明预检执行链可审计；后续必须再经过一次 R03 build/tool 运行和独立落盘检查，才可考虑冻结的两路线器件 DC。任何失败继续完整保留并停止。
- R03 不是 Xyce 二进制、IGZO 方程、器件仿真、SPICE 数值、物理参数、实验校准、M01 完成或电路证据；P3、P5、C00、电路、版图、PEX 和 HZO 继续关闭。

## ADR-044：纯源码 Xyce 采用串行用户目录构建，先过工具自测再开放器件 DC

- 日期：2026-08-03
- 状态：构建/工具预检合同 25/25 静态 PASS、E3；执行链已实现但尚未运行，M01 保持 E0

### 构建与来源决策

- 固定 Xyce `Release-7.10.0`、Trilinos `trilinos-release-14-4-branch`、SuiteSparse `v7.8.3` 和 CMake `3.30.5` 的官方归档 URL、本机稳定路径与 SHA-256。安装和构建目录全部位于 `/home/reachgao/.local/`，不写入仓库、不要求 root，也不接受 XyceNF 或其他专有二进制。
- 普通笔记本口径采用 serial C/C++ build、最多 2 个编译任务、`Trilinos_ENABLE_Fortran=OFF`、`TPL_ENABLE_MPI=OFF`。SuiteSparse 只构建 Xyce 所需的 `suitesparse_config;amd`，随后按 Xyce 官方 initial cache 构建 Trilinos 和 Xyce。
- 旧恢复合同保留的 Xyce 归档字符串为 `b5a883...541cfecf...`；对原下载包和稳定复制包独立重算均得到 `b5a883...541fecf...`。旧配置/报告及其哈希不改写，新预检合同明确登记该转录差异并以实际重算值作为构建输入。因此 ADR-043 的字符串只能解释为未落盘复核的源码审阅记录，不是本机 archive fingerprint。

### 自测与证据边界

- runner 在来源、工具和构建全部通过后，先执行不包含项目候选的标量 B-source 自测，预期 `limit(1,0,2)+sgn(1)*0.25=1.25 V`；只有该自测通过后才生成冻结 IGZO 候选的 parser-only 网表并调用 Xyce `-syntax`。
- `-syntax` 输入含一条 `.DC` 声明以检查解析完整性，但 runner 明确禁止数值求解并要求无 CSV 产生；它不是正式器件 DC。独立检查器只读取持久化报告、日志、argv、源码/二进制哈希和自测 CSV，不调用任何模拟器。
- 25/25 合同只构成 E3 结构与边界证据。正式 Xyce 二进制、自测和语法结果要等执行链提交推送后唯一运行；即使预检通过，也必须经独立落盘检查后才允许正式 ngspice/Xyce 两路线器件 DC。C00、电路、版图、PEX 和 HZO 继续关闭。


## ADR-043：以纯源码 Xyce 替代未授权 AIM-Spice，先冻结恢复合同

- 日期：2026-08-03
- 状态：开源恢复合同 30/30 静态 PASS、E3；M01 仍 `preflight_failed_tool_provenance/E0`，下一门只允许提交后的纯源码 Xyce 构建/工具预检与自测

### 路线选择

- R01 预检已按用户披露将 AIM-Spice 授权来源可审计和文档化 batch/CLI 冻结为 FAIL；该副本不得进入正式工具、数值或 M01 证据链。R01 的 11/13 报告、原始日志和所有缺失数值输出状态保持不变。
- 静态审阅 GNUCAP 0.36 的当前表达式源接口只接收组件的单一标量输入；直接把冻结的 `VDS/TG/BG` 三端 M00 行为核拆成手工网络会改变方程语义，因此 GNUCAP 不被写成第二路线。研究文件在仓外临时目录，未读取项目网表或运行数值。
- 选择 Xyce 7.10.0 纯源码路线：官方源码归档 SHA-256 为 `b5a883196f0a2b3972fd13c541cfecf04735bfabc7d124d7c7e17de707204f4e2`，许可证为 GPL-3.0-or-later。源码文档/测试和实现审阅到 `limit()`、`sgn()`、`.func`、B-level 1 表达式源、位置网表参数、`-l` 日志和 `-o` 输出基名；这只建立语法能力，不等于构建、语法自测或数值运行。专有 XyceNF 二进制不接受。

### 冻结内容与边界

- 恢复合同 `config/m01_open_source_recovery_contract_r01.json` 固定 247 行/13 曲线、233 scored（163 train/70 holdout）、14 审计行、W/L/300 K/源极/双栅端口映射、同一 `IGZO_DG_BEHAVIORAL_R02` 候选哈希和 ngspice/Xyce 两条独立路线。两路不宣称方程身份；替代路线不称 AIM-Spice Level 15、HSPICE Level 61 或物理参数卡。
- 合同固定未来的设备级 DC 批处理模板、输出命名、失败日志/部分表保留、两路/247 行笔记本预算和 `no-device-execution` 门。合同检查器只读标准库配置/CSV/源码，不创建网表，不调用仿真器。
- 首次 30 项干跑得到 28/30 的失败报告 `results/reports/m01_open_source_recovery_contract_r01.json` 原样保留；修正后的 30/30 E3 报告使用 `results/reports/m01_open_source_recovery_contract_r01_e3.json`，没有覆盖失败证据。

### 后续阶段门

- 本合同提交并推送后，下一步只实现纯源码 Xyce 构建/依赖哈希、二进制版本和许可证指纹、候选语法/受控 B-source 自测及 no-circuit 检查。自测链未通过并提交前，不得传入任何正式器件网表。
- 只有 build/tool preflight 通过后才允许正式两路线器件级 DC；任一路线失败均保留并停止 M01。P3、P5、C00、SPICE 电路、版图、PEX 和 HZO 继续关闭。


## ADR-042：未授权 AIM-Spice 不进入证据链，先运行无网表工具预检

- 日期：2026-08-03
- 状态：R01 工具/来源预检已唯一运行 11/13、E0/FAIL；失败证据保留，下一门只允许开源第二路线恢复合同

### 来源与执行边界

- 用户明确披露本机 AIM-Spice 副本未获授权。正式项目证据要求软件来源可审计，因此该副本即使能启动或识别 Level 15，也不得作为工具资格、数值结果或 M01 第二路线证据。披露前进行的探索仅使用帮助/版本形式参数，没有传入网表、生成曲线或形成正式证据；披露后正式运行器禁止启动该进程。
- R01 预检绑定已提交的 revision-3 合同、247 行目标口径和两个 IGZO-only 候选。唯一允许的子进程是固定哈希的 ngspice 以 `--version` 运行；AIM-Spice 只读取可执行文件路径、字节数和 SHA-256。器件网表、数值曲线、M01 原始表、叠图、电路、瞬态和下游全部禁止。
- 13 项门中，AIM-Spice 授权来源可审计和已文档化可复现 batch/CLI 两项按现状冻结为不满足。预检执行后必须保留 E0/FAIL 报告和日志；这是工具/来源阶段门失败，不是 ngspice/AIM-Spice 数值失败、IGZO 器件结果或 M01 完成。
- 执行链提交 `a6386d2` 推送后，R01 预检只运行一次并得到 11/13。ngspice 可执行文件指纹、唯一 `--version` argv 和 `ngspice-42` 版本通过；AIM-Spice 可执行文件只读取指纹且未启动。失败精确为上述两项，报告和 827 字节原始日志哈希保留，10 个声明的数值输出全部不存在。

### 恢复路线

- 本预检失败收口并提交后，才允许建立开源第二仿真器恢复合同。候选工具的许可证、官方发行来源、版本/二进制哈希、可复现批处理入口、行为模型能力、与 ngspice 的路线独立性、输出和失败边界必须先冻结并静态通过；不得把替代路线称为原生 AIM-Spice Level 15 或 HSPICE Level 61。
- 在恢复合同提交前不得执行任何 M01 器件级网表；C00、其他电路、版图、PEX 和 HZO 继续关闭。


## ADR-041：冻结 M01 两路 IGZO simulator cross-check 合同

- 日期：2026-08-03
- 状态：revision-3 静态合同 32/32 PASS、E3；没有调用 ngspice/AIM-Spice，下一步仅允许工具预检和器件级 DC 对照

### 冻结输入与路线

- M01 使用 R02 已落盘的 247 个选定行和 13 条曲线。233 个 `selection_role=scored` 行（163 train、70 holdout）进入线性/对数指标；7 个 `zero_vds_invariant` 和 7 个 `repeated_low_vds_audit` 行单独报告，不混入 scored 聚合。manifest 与 predictions CSV 的 SHA-256 固定，禁止重采样、插值、删点、补外部数据或用 holdout 调参。
- 两条路线都固定 IGZO n 型、W=60 um、L=8/10/12 um、300 K、源极 0 V、原始 VBG/VTG/VDS 和 `|ID|/W` A/cm 口径。ngspice 使用 `IGZO_DG_BEHAVIORAL_R02` 行为等效子电路；AIM-Spice 使用 `IGZO_DG_LEVEL15_R02` 与原生 `NMOS LEVEL=15` 包装。候选、映射和工具可执行文件均冻结哈希。
- 外部 ngspice/AIM-Spice 目录仅作 reference-only；SnO/P 型、HZO、教师表、旧电路和瞬态资产全部排除。行为路线不得称原生 Level 61，两条路线不声称方程相同。

### 指标、失败和阶段门

- 每条路线逐行输出电流、有限性/非负性、曲线单调性、linear NRMSE、log RMSE、train/holdout 分开聚合，并生成逐行/逐曲线路线差异表。路线差异是必须披露的诊断，不允许为了“对齐”而调参或隐藏；M01 门是完整、可复现、可审计的双路线执行证据，不是强制方程一致门。
- 合同检查不执行模拟器，只排他生成 `results/reports/m01_simulator_cross_check_contract_v3.json`。revision-1 因把 247 行误标为全部 scored 而 28/32 FAIL；revision-2 因把历史失败报告算作未来输出而 31/32 FAIL；两份报告都原样保留，修正没有改变 R02 输入或物理口径。
- 正式运行输出使用独立目录和文件，任一路线工具/语法/收敛失败均保留日志、部分表、预检和失败报告并停止 M01。不得执行电路、瞬态、版图、PEX、HZO 或 C00；只有两路正式执行和独立持久化检查均通过后才允许进入 C00。

### 证据边界

- 即使未来 M01 通过，也只能说明两个不同方程路线在冻结 IGZO 教学目标上的数值对照。不得声称实验拟合、物理参数提取、两路方程身份、ngspice 原生 Level 61、真实器件校准、电路可用性或 foundry sign-off。


## ADR-040：以 R02 两级证据在教学数值域内关闭 M00

- 日期：2026-08-03
- 状态：R02 runner 24/24 PASS、E2；独立落盘检查 20/20 PASS、E3。M00 仅在冻结 IGZO 教学数值曲线与局部有效域内关闭，下一门为 M01 simulator cross-check 合同

### 正式运行与结果

- R02 在执行链提交 `56a4215` 推送后只运行一次。优化器只读取 9 条 train/163 个计分点，20 次函数评价后正常终止并先落盘日志；随后才加载 4 条未参与优化的整条件 holdout/70 点。runner 24/24 PASS、E2。
- train aggregate linear NRMSE/log RMSE 为 `0.0830935/0.0838732 decade`，holdout 为 `0.109299/0.142615 decade`。两条 holdout transfer 的 VTH 误差为 `0.0218637/0.00917274 V`，gm 相对误差为 `0.363249/0.419248`，均通过 R01 起即冻结且未放宽的 `0.50` 上限。
- 只有 runner PASS 后才执行标准库独立检查器。它不导入 runner、NumPy、SciPy、DEVSIM 或 subprocess，独立重建 247 行选择、固定指数核、预测/残差、13 条曲线指标、VTH/gm、10 参数边界、两张图、候选状态和主产物哈希，20/20 PASS、E3。

### 证据边界与下一门

- R01 的 21/24、E0/FAIL、输入、系数和全部失败证据保持原样；R02 通过不修改 R01 状态，也不证明 `Lref/L` 是 IGZO 物理反长度规律。原 13 表、9/163 train、4/70 holdout、底值、权重、优化器、指标和全部阈值均未改变。
- 10 个系数都是教学代理。`lambda_per_v` 的归一化下界距离约 `8.17e-35`，`log_gmin` 约 `4.07e-4`；合同没有预注册额外边界裕量门，所以两者作为近下界诊断保留，不能解释为稳健物理参数。
- ngspice 行为候选、AIM-Spice Level-15 候选和映射已生成并哈希，但两路都未执行；没有运行 TCAD、电路、版图、PEX 或 HZO。因此 M00 只建立对合格项目教学数值曲线的局部代理一致性，不是实验拟合、物理参数提取、外部独立验证、仿真器验证、原生 HSPICE Level 61 执行或电路可用性。
- 下一步先建立 M01 simulator cross-check 合同，冻结相同几何、偏压、目标行、路线映射、语法/版本检查、指标差异、失败保留、输出路径和 no-circuit 边界。合同通过并提交前不得执行 ngspice/AIM-Spice；C00 与全部下游继续关闭。

## ADR-039：R02 正式运行必须绑定已提交执行链

- 日期：2026-08-03
- 状态：执行链合成自测 PASS、E2；正式 R02 仍为 E0，只有执行链提交推送后才允许唯一一次正式运行

### 实现与隔离

- R02 runner 直接实现合同冻结的 `Lref/L` 几何因子，不再读取自由 `length_exponent`；其余 10 个有界参数、9 条 train/163 点、4 条 holdout/70 点、底值、权重、优化器、指标和全部阈值保持不变。
- 正式模式先核对 R02 合同、注册表和 13 个源表哈希，只加载 train 进入确定性 `least_squares`；优化终止并落盘日志后才加载 holdout。运行目录和每个输出均拒绝覆盖，任一失败必须保留。
- 独立检查器不导入 runner、NumPy、SciPy、DEVSIM 或 subprocess，只用标准库从冻结 CSV 重建 247 行选择、固定指数参考核、线性/对数残差、逐曲线与聚合指标、holdout VTH/gm、参数边界、图片和候选哈希。独立报告同样排他创建。

### 阶段门

- `make m00-compact-model-r02-self-test` 只验证合成核、固定 1.25 长度比和二维 SciPy 探针，未读取正式 train/holdout 进入优化，也未生成任何正式 R02 输出。该结果只构成执行链 E2，不是拟合证据。
- 先提交并推送 runner/checker/Make 入口和当前机器状态，使未来输入快照记录已提交字节。之后 R02 只运行一次；runner 任一门失败即保留并停止，只有 24/24 PASS 才执行 20 项独立落盘检查。
- 即使两级检查通过，也只允许声明结构正则化教学代理对合格项目数值曲线的局部一致性。M01、SPICE、电路、版图、PEX 和 HZO 在 M00 两级 PASS 与结果收口提交前继续关闭。

## ADR-038：R02 以固定一阶长度几何因子消除训练结构混淆

- 日期：2026-08-03
- 状态：R02 静态合同 27/27 PASS、E3；只允许进入版本化执行链实现，不代表拟合、M00、M01 或 SPICE 完成

### 独立结构依据

- R01 失败触发结构审计，但失败 holdout 的数值、R01 拟合系数和预测均不参与 R02 方程、固定值、初值、边界、重启或门槛选择。
- 已提交的 R01 split 在训练侧包含 8 条参考长度 `L=10 um` 曲线和仅 1 条非参考长度 `L=8 um` 曲线，而 R01 同时开放 `length_exponent` 与 `length_vth_slope_v` 两个长度自由度。一个非参考训练条件不能稳健区分幅值缩放和阈值移动，二者可在训练目标内互相补偿；该判断只依赖提交前 split 与方程。
- R02 将既有电荷差教学核的一阶几何归一化固定为 `Lref/L`，指数严格为 `1.0` 并移出优化；`length_vth_slope_v` 保留为唯一训练拟合长度系数，使用中性初值 `0.0 V`。有界系数由 11 个降为 10 个。

### 不变项与阶段门

- 13 个注册表字节/哈希、9 条 train/163 点、4 条整条件 holdout/70 点、7 个零漏压不变量、7 个低漏压复现点、当前底值/权重、确定性无重启优化、全部线性/对数/VTH/gm/单调/边界门和 `0.50` gm 上限均与 R01 完全一致。
- R01 配置、运行器、检查器、E0/FAIL 报告和全部失败产物保持原样；R02 使用独立配置、报告、运行目录、表、图和候选路径并拒绝覆盖。
- `Lref/L` 是消除不可识别自由度的教学正则化假设，不证明 IGZO 物理反长度缩放。静态合同没有运行拟合、holdout 评分、TCAD、ngspice、AIM-Spice 或电路。
- 下一步只实现并自测 R02 运行器与独立检查器。执行链提交推送前不得运行正式 R02；之后也只允许一次正式运行。只有 R02 runner 与独立落盘检查均 PASS 才能关闭 M00 并打开 M01。

## ADR-037：保留 M00 R01 holdout gm 阶段门失败并停止下游

- 日期：2026-08-02
- 状态：正式失败已保留；等待 R02 研究路线决定，不代表 M00、M01 或紧凑模型完成

### 唯一正式运行

- 在合同提交 `c9b2063` 和执行链提交 `2e184e7` 均推送后，R01 只运行一次。优化器只读取 9 条 train/163 个计分点，确定性 `least_squares(method=trf)` 在 18 次函数评价后正常终止；随后才加载 4 条 holdout/70 点。247 行选择清单、输入快照、优化日志、预测、线性/对数残差、11 个系数、局部有效域和两张图全部落盘。
- train 的 aggregate linear NRMSE/log RMSE 为 `0.0799203/0.0832202 decade`，holdout 为 `0.123434/0.148789 decade`，均通过冻结聚合门。全部逐曲线线性/对数误差、VTH、有限性、非负性、零漏压、采样单调性和严格参数边界门也通过。
- 两条 holdout transfer 的 gm 相对误差分别为 `0.374514` 和 `0.512384`。后者来自未参与优化的 `L=12 um` 整条件曲线，超过预注册上限 `0.50`，因此主数值门失败，运行器为 21/24 PASS、E0/FAIL。

### 失败语义与后果

- 另外两项 FAIL 是主数值失败的预注册后果：只有全部数值门通过才允许生成 ngspice/AIM-Spice 候选，因此 3 个候选文件不存在，完整候选产物门也随之失败。它们不是额外的优化或工具异常。
- 运行器失败后没有执行只允许 PASS 后运行的独立检查器，没有生成或运行 ngspice/AIM-Spice，没有运行 TCAD、电路、版图、PEX 或 HZO。M00 仍为 E0/FAIL，M01 与全部下游保持关闭。
- R01 不重跑、不删点、不改 split、不把 holdout 放入目标函数，也不把 `0.50` 放宽到覆盖 `0.512384`。当前系数和图只能作为失败教学代理诊断，不是已接受紧凑模型、物理参数、实验标定、外部独立验证或电路可用证据。
- 任何恢复必须先建立并提交新的 R02 合同，并明确给出不依赖 R01 holdout 调参的模型结构依据；若无法满足这一方法学边界，则保持 R01 FAIL 或等待新的合格数据。该路线选择属于研究决策，作出前不继续执行。

## ADR-036：以整条件 holdout 建立 M00 教学紧凑模型输入与验证合同

- 日期：2026-08-02
- 状态：通过；只关闭 M00 静态合同门，不代表模型拟合、M00、M01 或 SPICE 完成

### 数据资格与划分

- `references/m00_dataset_registry.csv` 冻结 13 个表的路径、SHA-256、行数、上游运行报告和独立检查。正式拟合只可使用 T01-D-B/C、T02-C、T03-P4 与 T03-P3 V2 理想接触 output 的显式子集。
- 加密网格、上下栅互易、回程和重复控制只作复现审计；P1 偏压/电容分配、P3 非理想接触和 P5 `V_t-only` 数据只作不判门挑战；P2 陷阱变体与外部 ngspice 基线不得进入正式拟合或 holdout。
- 不随机打散相邻点。训练集固定为 9 条完整偏压/几何条件曲线、163 个计分点；holdout 固定为 4 条未参与优化的整条件曲线、70 个计分点。7 个 `VDS=0` 点只做零电流不变量，7 个重复 `VDS=0.01 V` output 点只做跨阶段复现，避免重复加权。

### 教学核、优化与误差

- 参考核固定为平滑电荷差 DC 教学代理：单栅控制量为 `VBG`，对称双栅控制量为 `eta_dg*(VTG+VBG)`，包含局部长度缩放、漏端电荷差、输出调制和数值底电导。11 个系数均有预注册初值和上下界，它们是教学代理系数，不是物理参数。
- 未来正式拟合只允许一次确定性 `scipy.optimize.least_squares(method=trf)`，不做随机重启，holdout 不得初始化参数、进入目标函数、选择重启或修改门槛。训练每条曲线等总权，线性归一化残差与以 `1e-20 A/cm` 为底的对数残差各占一半。
- 训练与 holdout 必须分开报告聚合/每曲线线性 NRMSE 和对数 RMSE，并报告 VTH/gm、零漏压、有限性、非负性、采样单调性、参数边界与局部有效域。任一门 FAIL 都必须保留输入、优化日志、预测、残差和失败报告；不允许删点、换划分、改底值/权重或放宽阈值。

### 模型路线与证据边界

- M00 首先验证仿真器无关的参考核。ngspice 只生成 IGZO-only 行为翻译候选，不得称为原生 HSPICE Level 61；AIM-Spice 候选使用原生 `NMOS LEVEL=15` 与显式双栅控制包装，30 nm 物理 Al2O3 与 10 nm 有效 TOX 口径仍分离。两路执行和差异必须留到 M01，不声称方程同一。
- 首次静态合同检查因把 T01/T02 的真实机器状态 `complete_e2`/`bidirectional_verified` 误写为通用 `verified` 而 24/25 PASS。原 FAIL 报告已保留；只修正状态字面值后静态检查 25/25 PASS、E3，没有改数据、划分、方程、参数边界或验收阈值。
- 该 E3 只证明合同可复核，`fit/TCAD/SPICE/circuit` 均为 `NOT_RUN_BY_CONTRACT_CHECK`。即使后续 M00 PASS，也只能称与同一冻结教学模型的训练/holdout 数值曲线一致，不得称实验拟合、外部独立验证、物理参数提取、双仿真器验证、电路可用或定量电路预测。

## ADR-035：以两级证据关闭 P5 与数值 T03 并进入 M00 合同门

- 日期：2026-08-02
- 状态：通过；只关闭冻结二维未校准教学模型内的 P5 与五组数值 T03，不代表物理温度模型、实验校准、紧凑模型或电路完成
- 执行：合同提交 `a666203` 推送后只运行一次正式 P5。三个新器件完成 123 次全部收敛 DC、93 个 transfer 点、3 个 `VTG=1 V` 状态、7257 行节点、7680 行沟道单元和 18 VTK；墙钟 `9.12665 s`。运行器 14/14 PASS、E2。
- 独立证据：只有运行器 PASS 后才执行的检查器不导入运行器或 DEVSIM，复算 93 点、123 条求解、提取、300 K T02-C 回归、3 状态、18 VTK、两张图和主产物哈希，15/15 PASS、E3。最大端口相对不平衡为 `4.37301e-10`，300 K 曲线、状态、VTH 和 gm 对 T02-C 的差异均为 0。
- 数值响应：250/300/350 K 的 VTH 代理为 `0.245409/0.263857/0.281977 V`，SS 代理为 `117.138/137.594/157.796 mV/dec`，gm 代理为 `3.98472e-5/3.93760e-5/3.88128e-5 S/cm`。最低栅压电流代理增加，最高栅压电流代理下降，预注册最大端点响应为 `0.941934`。
- 边界：唯一变化项仍是既有 Scharfetter-Gummel 电流中的 `V_t=k_B*T`。迁移率固定 35.5 cm2/(V*s)，DOS、能带、介电、接触、陷阱、几何和偏压不变；方向只作诊断。因此不得声称物理/实验 IGZO 温度依赖、激活能、迁移率/DOS/接触/陷阱温度律、物理 VTH/SS/Ioff/Ion、工作温区、自热或可靠性。
- T03 决策：P1/P2/P3/P4/P5 均有正式运行和独立落盘检查，数值 T03 在声明边界内完成；P2 V1/V2 与 P3 V1 失败不被通过结果覆盖。
- 下一门：只建立正式 M00 教学紧凑模型输入与验证合同，先冻结数据资格、train/holdout、双轨模型边界、提取/优化、误差、失败保留和输出。合同通过并提交前不做拟合或 SPICE；M01、电路、版图、PEX 和 HZO 继续关闭。

---

## ADR-034：以 V_t-only 教学闭包冻结 T03-P5 正式温度合同

- 日期：2026-08-02
- 状态：通过；只关闭 P5 静态输入合同，不代表正式温度敏感性、完整 T03、物理温度模型或实验校准完成
- 决策：正式 P5 采用 `T=250/300/350 K` 三点，NIST CODATA 的 `k_B=8.617333262e-5 eV/K` 只用于计算既有 Scharfetter-Gummel 电子电流表达式中的 `V_t=k_B*T`，得到 `0.021543333155/0.025851999786/0.030160666417 V`；300 K 点与 T01/T02-C 冻结值完全相同。
- 固定项：教学迁移率始终为 `35.5 cm2/(V*s)`，不启用经验温度迁移率；有效 DOS、带隙、亲和势、介电常数、接触密度、陷阱、几何、网格、偏压和提取方法均不随温度改变，也不加入自热或热边界方程。
- 协议：每个温度新建一个 T02-A 启用双栅器件，复用 T02-C 顶栅主扫、底栅 0 V、`VDS=0.01 V` 和 31 点网格。未来正式运行冻结为 3 器件、123 次 DC、93 个 transfer 点、3 个 `VTG=1 V` 状态和 18 VTK；300 K 必须完整回归 T02-C。
- 提取与门：冻结恒流 VTH、`VTH+0.2 V` gm、`1e-7~1e-6 A/cm` 固定窗口 SS、最低/最高栅压电流代理；250/350 K 端点在这些量中的最大相对响应须至少 0.1%。方向假设只报告、不判门，不能据此强行要求单调物理趋势。
- 失败与证据：正式输出拒绝覆盖，任一失败必须保留快照、日志、部分表、状态、报告和可生成图片；不得事后删温度点、加入经验温度律或放宽门槛。静态检查为 23/23 PASS、E3、`NOT_RUN_BY_CONTRACT_CHECK`，所以 3/123/93/3/18 都仍是计划量。
- 证据边界：未来即使运行器 E2 与独立落盘检查 E3 均通过，也只能关闭冻结二维 n-IGZO 教学模型的三点 `V_t-only` 数值敏感性。不得声称实测/拟合温度依赖、激活能、迁移率/DOS/接触/陷阱温度律、物理 VTH/SS/Ioff/Ion、工作温区、自热、可靠性或电路温度验证。
- 下一门：先提交并推送本合同里程碑，之后只允许完整运行一次正式 P5；运行器 PASS 后才允许独立落盘检查。M00/M01、SPICE、电路、版图、PEX 和 HZO 继续关闭。

---

## ADR-033：以 V2 两级证据关闭数值 P3 并顺序进入 P5 合同

- 日期：2026-08-02
- 状态：通过；只关闭冻结二维教学模型内的 P3，不代表物理接触验证、完整 T03 或下游阶段完成
- 背景：P3 V1 已完成 12 器件、243 次收敛 DC 和 156 点，但因把相对端口守恒用于 9 个零漏压数值噪声点而以 24/25 保持 E0/FAIL。ADR-032 的 V2 恢复合同不改三点、方程、偏压、提取、阈值和预算，只修正零/非零漏压门的适用域，并在提交后允许唯一一次正式运行。
- 决策：V2 按已提交合同唯一运行一次，完成 12 器件、243 次全部收敛 DC、93 个 transfer 点、63 个 output 点、3 状态和 18 VTK。运行器 25/25 PASS、E2；只有运行器通过后才执行的独立落盘检查 20/20 PASS、E3，因此数值 P3 关闭。
- 数值门：非零漏压最大端口相对不平衡为 `3.35344e-11`，零漏压最大绝对电流为 `1.08454e-19 A/cm`；circuit KCL、Ohm 定律和压降分配残差分别为 `2.42178e-12`、`1.20922e-12` 和 0。最大输入的高栅电流代理相对理想点下降 `0.161396%`，外部总电阻宽度积代理由 `2780.13345` 增至 `2784.63204 kOhm*um`。
- 证据边界：上述量只证明未校准二维漂移扩散器件与对称外部 lumped resistor 的受控数值响应。两个非零输入仍是 E1 文献数量级按项目总源漏口径的教学映射，不是项目测量、TLM 提取、Ti/Ni 比较、势垒、注入、current crowding、物理 Ion 或接触参数校准。
- 历史保留：V2 通过不把 V1 改写为 PASS；V1 配置、运行器、日志、表、图、状态、报告、原失败 manifest 和 archive collision supplement 保持原哈希。V1 独立检查仍未运行。
- 阶段门：下一步只建立正式隔离 T03-P5 温度敏感性合同。合同必须先冻结温度点、温度依赖/不依赖项、偏压、提取、失败保留、输出、资源预算与证据边界并提交；此前不得运行 P5。M00/M01、SPICE、电路、版图、PEX 和 HZO 继续关闭。

---

## ADR-032：保留 P3 V1 零漏压适用域失败并建立 V2 恢复合同

- 日期：2026-08-02
- 状态：通过；只关闭 V2 静态恢复合同，不代表 V1/V2 正式敏感性 PASS、P3 或完整 T03 完成

### V1 结果与失败分类

- V1 按 ADR-031 完成 12 个独立器件、243 次全部收敛 DC、93 个 transfer 点、63 个 output 点、3 状态和 18 VTK；运行器 25 项中 24 项通过。circuit KCL 最大相对残差为 `2.42178e-12`、Ohm 定律最大相对残差为 `1.20922e-12`，压降分配绝对残差为 0，T02-C 理想控制与全部方向/响应/状态门均通过。
- 唯一失败门 `device_terminal_current_conservation` 把相对端口电流不平衡应用到 9 个 `external VDS=0` 输出点。此时端口电流约为 `1e-20 A/cm` 的数值噪声，相对比值最高 `1.6720517`，没有可解释的相对尺度；非零漏压 147 个点的最大相对不平衡为 `3.35344e-11`，零漏压最大绝对电流为 `1.08454e-19 A/cm`，分别通过原 `1e-5` 相对门和 `1e-16 A/cm` 绝对门。
- 该失败归类为验收适用域实现错误，不是求解不收敛、器件/电路 KCL 失败或物理输入冲突。V1 仍严格保持 E0/FAIL，不运行 V1 独立检查，也不把其余 24 项通过写成 P3 完成。
- V1 配置、运行器、合同、报告、快照、求解日志、曲线、指标、circuit 表、状态、VTK 和图片全部冻结。原失败归档因报告与配置同 basename 发生外部副本覆盖；原 manifest 和原始证据未改写，新增 supplement 披露冲突并用唯一名称补齐可哈希副本。

### V2 决策

- 保持 `R_pair*W=0/0.5/4.5 kOhm*um`、总源漏对称分摊、二维 n-IGZO 教学模型、自洽 device-circuit 方程、网格、偏压路径、提取方法、方向/最小响应门和 12 器件/243 DC/156 点/3 状态/18 VTK 预算不变。
- 两个数值阈值都不改变：`maximum_relative_device_terminal_current_imbalance=1e-5` 只在 `external VDS>0` 判门；`maximum_zero_external_vds_absolute_current_a_per_cm=1e-16` 只在 `external VDS=0` 判门。这与 T01-D-B 已冻结的零漏压绝对量、非零漏压相对量分域原则一致。
- V2 所有合同、运行、表、图、状态、检查和潜在失败归档使用独立 `_v2` 路径。失败归档的外部 artifact 名同时包含角色和原 basename，避免重现 V1 同名覆盖。
- 34 项静态检查逐项验证 V1 哈希、唯一失败门、归档补充、V1/V2 不变物理/数值章节、原阈值和新适用域；结果 34/34 PASS、E3、`simulation=NOT_RUN_BY_CONTRACT_CHECK`。

### 边界与下一步

- V2 合同 PASS 不把 V1 改为 PASS，也不证明 V2 器件运行、项目 TLM/接触电阻提取、Ti/Ni 比较、势垒/注入物理或实验校准。
- 下一步只允许完整运行一次正式 P3 V2；运行器 PASS 后才执行不导入运行器或 DEVSIM 的独立落盘检查。任一门失败继续保留全部证据并停止在 P3。
- P5、M00/M01、SPICE、电路单元、版图、PEX 和 HZO 继续关闭。

## ADR-031：以总源漏对称串联电阻代理冻结 P3 正式合同

- 日期：2026-08-02
- 状态：通过；只关闭 P3 静态输入合同，不代表接触仿真、物理接触参数、P3 或完整 T03 完成

### 决策

- P3 只改变一个标量 `R_pair*W`，取 `0/0.5/4.5 kOhm*um`。零点使用 T02-C 直连理想欧姆接触回归；非零点按 `R_pair=R_pairW*1000/W_um` 换算，并将源漏各固定为总值的一半，不扫描不对称接触或势垒高度。
- 两个非零数值来自 DOI `10.1109/IEDM45625.2022.10019488` 的 Ni/Ti TLM 报告数量级，只作 E1 低/高锚点。原论文器件、栈、尺寸、过驱动和提取定义均不继承；运行案例不使用金属名，禁止声称项目 TLM 提取、Ti/Ni 选择、势垒、热发射、隧穿或工作函数验证。
- 非零点必须使用 DEVSIM device-circuit 自洽耦合：源漏 Poisson 与电子接触方程绑定内部 circuit node，通过对称 R 元件连接外部 V 元件。禁止事后电流降额或手工外层压降迭代；零电阻控制不创建零值 R 元件。
- 正式协议冻结 3 个 transfer 器件与 9 个独立 output 器件，共 12 器件、243 次 DC、93 个 transfer 点、63 个 output 点、3 状态和 18 VTK。线性区总电阻宽度积用 `VTG=1 V`、外部 `VDS=0.001/0.005/0.01 V` 的过原点 OLS 提取。
- 完成门包括全求解收敛、器件守恒、circuit KCL、Ohm 定律、内外电压分配、选定偏压电流随 `R_pair*W` 严格下降、线性区总电阻严格增加、最大点至少 0.1% 电流响应、T02-C 理想控制回归、状态/图/哈希和独立复算。提取增量与输入电阻的 15% 一致性只作必须报告的诊断，不是完成门。
- 任何运行器异常或预注册门失败都必须保留 E0/FAIL 报告、求解日志和部分产物，恢复前版本化归档；不得覆盖失败、删点或放宽阈值。只有运行器 PASS 才允许执行不导入运行器/DEVSIM 的独立检查。

### 合同结果与边界

- 首次静态检查因三个检查器断言错误而 27/30 PASS：T02-C 独立报告没有顶层证据字段、`Ti` 被错误匹配到 `literature` 子串、以及连字符拼写不一致。失败报告已保留；修正只改断言，不改任何输入、模型、偏压、提取或验收门槛。
- 修正后合同 30/30 PASS、E3、`NOT_RUN_BY_CONTRACT_CHECK`。12/243/156 是未来计划量，不是仿真事实。
- 下一步只实现并运行正式 P3；P5、M00/M01、SPICE、电路单元、版图、PEX 和 HZO 继续关闭。

## ADR-030：以 V3 两级证据门关闭数值 P2 并顺序进入 P3 合同

- 日期：2026-08-02
- 状态：通过；只关闭冻结准静态教学模型边界内的 P2，不代表物理陷阱校准或完整 T03

### 决策

- V3 按 ADR-029 的统一 `VTG=-0.5~1.8 V/0.05 V` 合同运行全部 8 个隔离器件，不补跑单点、不改变密度、方程、提取方法或验收阈值。运行器完成 456 次收敛 DC、376 个 transfer 点、8 状态和 48 VTK，17/17 PASS、E2。
- 只有运行器 PASS 后才执行独立检查。独立检查不导入运行器或 DEVSIM，重算输入/输出哈希、曲线、提取、T02-C 双零控制、96 点占据积分及导数、状态和图像，16/16 PASS、E3。
- 两个零控制对 T02-C 的 31 个共同点及 VTH/gm 完全复现，并在 47 点 V3 网格上彼此完全一致；该控制链与有限、单调、守恒、状态/VTK 完整性共同关闭数值 P2。
- NTA 的 VTH/SS 代理严格增加且 gm 代理严格下降；NGA 的 VTH 代理严格增加、gm 代理严格下降，但 SS 代理由 `137.594` 轻微下降至 `132.874 mV/dec`。方向假设按冻结合同只作诊断，不是完成门；如实保留 NGA-SS 结果，不将其解释为真实深态机制或通过实验验证的物理规律。
- V1/V2 的 E0/FAIL 输入、运行器、日志、曲线、状态、VTK 和报告继续作为正式失败证据保留；V3 PASS 不覆盖或改写这些历史结论。
- P2 完成仅允许声称文献约束 NTA/NGA 点在未校准准静态教学模型中完成受控 transfer sensitivity，VTH、SS、gm、最低栅压电流和内部状态仍为数值代理。测量/拟合 DOS、动态捕获-发射、迟滞、bias stress、物理 Ion/Ioff、实验校准和不确定度仍未验证。
- 阶段 DAG 下一步只建立正式 T03-P3 接触敏感性合同；合同通过并提交前不运行 P3。P5、M00/M01、SPICE、电路、版图、PEX 和 HZO 继续关闭。

### 依据

- `results/reports/tcad_t03_p2_bulk_traps_formal_v3.json`
- `results/reports/tcad_t03_p2_bulk_traps_formal_v3_check.json`
- `results/tables/tcad_t03_p2_bulk_traps_formal_v3_metrics.csv`
- `results/tcad/t03_sensitivity/p2_bulk_traps_formal_v3/state_manifest.json`

## ADR-029：以统一 1.8 V 网格建立 bulk 正式 V3 恢复合同

- 日期：2026-08-02
- 状态：通过；只关闭 V3 输入合同，不代表正式敏感性、P2 或 T03 完成

### 决策

- 用户明确批准采用建议的统一 `VTG=-0.5~1.8 V`、`0.05 V`、47 点网格，并授权以后在不改变项目范围、物理口径或预注册门槛时按保守方案直接解决可处理问题。
- V3 对全部 8 个器件应用同一网格；不补跑单个失败器件。NTA/NGA 八个执行点、family 隔离、准静态占据与 Poisson 方程、96 点积分、VTH/Delta VTH/SS/gm/最低栅压电流提取方法和全部验收阈值保持不变。
- V2 的诊断 gm 评价点为 `1.6666676 V`。`1.75 V` 是提供 1.70 V 中心差分样本的最低上限；选择 `1.8 V` 额外保留一个 `0.05 V` 裕量点。V3 计划量为每器件 47 个 transfer 点和 57 次 DC，共 8 器件、376 点、456 次 DC、8 状态和 48 VTK。
- 原活动 V2 配置和运行器分别冻结为 `config/tcad_t03_p2_bulk_traps_formal_v2_failed.json` 与 `tcad/run_t03_p2_bulk_traps_formal_v2_failed.py`；合同检查同时核对 V1/V2 精确输入、运行器哈希、失败报告、曲线与归档，V1/V2 证据不得被 V3 覆盖。

### 合同结果与边界

- 首次 V3 合同检查因新增 `v2_curve_csv` 被错误送入 JSON 加载器而在断言前异常退出；该检查器失败已保存，且没有运行 DEVSIM、改变物理输入或放宽阈值。修正仅把该依赖加入既有 CSV 加载分支。
- 修正后 V3 合同 24/24 PASS、E3、`NOT_RUN_BY_CONTRACT_CHECK`。合同 PASS 只允许下一步完整运行一次 V3；只有运行器 PASS 后才允许执行不导入运行器或 DEVSIM 的独立落盘检查。
- 376/456 是未运行计划量。通过的正式 bulk 敏感性、物理 DOS/SS/VTH/Ioff/Ion、实验校准、完整 P2/T03、P3/P5、紧凑模型、电路、版图、PEX 和 HZO 仍未完成。

## ADR-028：bulk 正式 V2 提取网格失败后暂停阶段 DAG

- 日期：2026-08-02
- 状态：失败已保留；等待明确恢复决定，不代表正式敏感性、P2 或 T03 完成

### V2 结果与失败门

- V2 按 23/23 E3 静态合同完成 8 个新器件、440 条全部收敛的 DC 记录、360 个 transfer 点、8 个共同状态和 48 个 VTK；墙钟 `28.414 s`，最大端口相对电流不平衡为 `6.01e-9`。这些完成事实不覆盖运行器 E0/FAIL。
- `NTA=5e19 cm^-3 eV^-1` 在 `VTG=1.7 V` 达 `1.41901e-5 A/cm`，已经包络不变的 `1e-5 A/cm` 恒流 VTH 判据。1.45/1.50 V 包络给出的诊断 VTH 为 `1.4666676 V`。
- 不变的 gm 定义要求在 `VTH+0.2 V=1.6666676 V` 做中心差分。该评价点高于 45 点网格的倒数第二点 1.65 V，缺少上邻点；因此 V2 失败于提取网格充分性，而不是求解收敛、VTH 包络、守恒或陷阱方程。
- 标准 V2 目录、版本化失败归档、配置快照、运行器哈希、求解日志、360 点曲线、8 状态、48 VTK 和 E0 报告全部保留。提取中止后的指标/参考/零控制比较表保持空数据行，不生成报告图，不运行独立检查。

### 暂停与恢复边界

- 按用户自动执行规则，阶段门失败后暂停并报告；当前不自行建立 V3、不补跑单个器件、不修改 V2 输入或阈值，也不进入 P3/P5 等后续阶段。
- 若批准恢复，必须先冻结新的统一网格合同；所有 8 个器件使用相同上限，并保持 NTA/NGA 点、准静态方程、VTH/SS/gm 方法和全部验收阈值不变。是否采用最小 1.75 V 或留余量的 1.8 V 上限属于待确认的恢复决定。
- V2 的 8/440/360 是已完成但 E0/FAIL 的计算证据，不支持正式 bulk 敏感性、物理 DOS/SS/VTH/Ioff/Ion、实验校准、完整 P2/T03 或任何紧凑模型、电路和版图结论。

## ADR-027：保留 bulk V1 失败并以统一扩展栅压建立 V2 合同

- 日期：2026-08-02
- 状态：通过；只关闭 V2 输入合同，不代表 V2 正式敏感性、P2 或 T03 完成

### V1 结果与失败保留

- V1 按冻结合同完成 8 个新器件、328 条全部收敛的 DC 记录、248 个 transfer 点、8 个共同状态和 48 个 VTK；最大端口相对电流不平衡为 `6.01e-9`，墙钟为 `22.61 s`。这些完成事实不改变运行器 `E0/FAIL` 结论。
- `NTA=5e19 cm^-3 eV^-1` 在 `VTG=1.0 V` 的最大电流仅为 `3.13750e-6 A/cm`，未包络保持不变的 `1e-5 A/cm` 恒流 VTH 判据。其余 7 条曲线能够包络该判据。
- 非零受主型占据体电荷在所有外部端子为 0 V 时产生有限的自洽内部电势，V1 最大值为 `0.157504 V`。因此“所有器件内部电势接近零”是从无陷阱零控制错误继承的门；所有器件零偏端电流接近零仍是有效完成门。
- V1 配置、运行器源码、输入快照、求解日志、曲线、状态、VTK、标准失败报告和版本化归档全部保留，不删除、覆盖或重新标为通过。

### V2 决策

- 保持 NTA/NGA 八个执行点、准静态 Poisson 体电荷方程、96 点积分、`1e-5 A/cm` VTH、family 内 Delta VTH、`VTH+0.2 V` 中心差分 gm、`1e-7~1e-6 A/cm` SS 窗口、最低栅压电流和全部守恒/独立复算门不变。
- 所有 8 个器件统一采用 `VTG=-0.5~1.7 V`、`0.05 V` 步长的 45 点网格。V1 末段对数斜率把高 NTA 的 VTH 估计在约 `1.34 V`；原 gm 定义和中心差分还需至少一个更高采样点，因此 `1.7 V` 为 VTH 与 gm 同时留出明确余量。不得只给失败器件增加点或删除 `5e19` 文献点。
- V2 计划量为每器件 55 次 DC，共 440 次 DC、360 个 transfer 点、8 个 `VTG=0.3 V` 状态和 48 个 VTK。前 31 个 transfer 点逐点继承 T02-C 网格；新增 14 点只扩展共同高栅压范围，T02-C 回归仍限定在共同的 31 点。
- 所有器件继续要求零偏端电流不超过原 `1e-18 A/cm` 门。内部电势接近零只用于两个精确零陷阱控制；六个非零陷阱器件要求内部电势有限并保留为诊断，不把有限内建响应改写为物理测量。
- 提取器必须在未包络时报告案例、判据和曲线电流范围，不再用无上下文 `StopIteration` 隐藏失败位置。任何 V2 失败仍按 revision 2 新路径完整归档。

### 证据边界

- V2 合同通过 23/23 静态检查，证据等级 E3，仿真状态为 `NOT_RUN_BY_CONTRACT_CHECK`；它只允许下一步完整重跑 V2，再做不导入运行器或 DEVSIM 的独立落盘检查。
- V1 的 8/328/248 是失败运行的已完成计算，V2 的 8/440/360 是尚未运行的冻结计划。两者都不能支持项目 DOS 测量/拟合、物理 SS/VTH/Ioff/Ion、动态捕获-发射、实验校准或完整 P2/T03 结论。
- P3、P5、M00、M01、SPICE、电路、版图、PEX 和 HZO 继续关闭。

## ADR-026：正式 bulk transfer 在运行前冻结隔离点、提取和失败保留

- 日期：2026-08-02
- 状态：通过；只关闭正式输入合同，不代表正式 NTA/NGA 敏感性、P2 或 T03 完成

### 决策

- NTA 与 NGA 继续作为两个完全隔离的 family。NTA family 使用 `0/1e18/5e18/5e19 cm^-3 eV^-1`，NGA family 使用 `0/1e16/5e16/5e17 cm^-3 eV^-1`；每个 family 都单独执行零控制，另一 bulk family、上下界面 DIT、NTD 和 NGD 固定为零。
- 正式工作量冻结为 8 个独立器件、每器件 41 次 DC、共 328 次 DC、248 个正式 transfer 点、8 个 `VTG=0.3 V` 状态和 48 个 VTK。合同检查只验证这些计划及路径，没有运行 DEVSIM。
- VTH、Delta VTH、`VTH+0.2 V` gm、`1e-7~1e-6 A/cm` 一 decade OLS SS 和 `VTG=-0.5 V` 最低栅压电流沿用 DIT V2 的冻结提取方法；最低栅压电流不得称为物理 Ioff。
- 增大受主型占据态后 VTH/SS 可能增加、电流/gm 可能降低，只作为预注册方向性诊断，不是完成门。只要结果有限、收敛、守恒且可独立复算，反向或非单调趋势必须保留并解释。
- 所有失败必须归档输入快照、截至失败的求解日志、已完成表格和状态、失败门报告及可生成图片。不得删除失败证据、静默放宽阈值、见到结果后删除文献点，或用部分求解器件替代零控制。

### 证据与边界

- `config/tcad_t03_p2_bulk_traps_formal.json` 和 `results/reports/tcad_t03_p2_bulk_traps_formal_input_contract.json` 通过 22/22 静态检查，证据等级 E3，仿真状态明确为 `NOT_RUN_BY_CONTRACT_CHECK`。
- 该 PASS 只允许下一步单独运行正式隔离 NTA/NGA transfer sensitivity，再执行不导入运行器/DEVSIM 的落盘证据复核。运行器和独立检查都通过前，不得声称正式敏感性、物理 DOS/SS/VTH/Ion/Ioff、完整 P2/T03、实验标定或紧凑/电路/版图证据。
- P3、P5、M00、M01、SPICE、电路、版图、PEX 和 HZO 继续关闭。

## ADR-025：bulk traps 先冻结隔离的 NTA/NGA 准静态合同

- 日期：2026-08-02
- 状态：通过；已关闭静态输入合同和三案例方程冒烟，不代表正式 bulk 敏感性或完整 P2

### 决策

- 使用 DOI `10.3390/electronics9101652` 的 E1 a-IGZO DOS 来源。导带指数尾态取 NTA=`1e18/5e18/5e19 cm^-3 eV^-1`、`WTA=0.08 eV`；高斯深态取 NGA=`1e16/5e16/5e17 cm^-3 eV^-1`、`WGA=0.2 eV`、`EGA=0.5 eV below Ec`。每组另加零值回归控制。
- 采用 `epsilon=Ec-E` 和局部准静态费米占据；受主态空时中性、占据时带一个负电荷。积分占据密度只加入 Poisson 体电荷，并提供对 `Electrons` 的解析 Jacobian；当前不加入 SRH、trap continuity、捕获截面或时间常数。
- NTA 与 NGA 必须分两次隔离扫描：扫描一类时另一类峰值为零，上下界面 DIT 也为零。价带尾态 NTD 和施主型高斯态 NGD 延后，避免一次引入四带 DOS 和界面/体陷阱混合归因。
- 能量积分固定为 `0~3.0 eV` 的 96 点 Gauss-Legendre；合同检查器另用 32768 区间 Simpson 对六个代表点复核。只有静态合同 PASS 才允许构建零控制、NTA 参考和 NGA 参考三案例方程冒烟。
- 论文公式和 Table 1 将 NGA 归为 acceptor-like，但 Figure 3 caption 写成 donor-like。本合同采用公式/表口径，并把冲突保留在来源表和限制中，不静默消除。

### 结果边界与下一步

- 30/30 静态检查 PASS；96 点积分的最大相对误差为 `7.93e-7`，低于冻结的 `1e-5` 门。随后三案例方程冒烟完成 3 器件/21 次 DC，运行器 E2 PASS，独立 16 项检查 E3 PASS。
- 来源器件为单底栅、100 nm SiO2、`VD=40 V`，与本项目双栅 30/24/30 nm Al2O3/IGZO 栈和 `VDS=0.01 V` 不同；这些点不是项目测量、拟合或 DOS 提取。
- 原定下一步已由 ADR-026 的正式隔离合同关闭；当前只允许运行该合同定义的正式 NTA/NGA transfer sensitivity，再做独立落盘检查。当前冒烟和静态合同都不支持物理 DOS、SS/VTH/Ion/Ioff 或完整 P2 结论。

## ADR-024：以 V2 关闭 bottom-interface DIT 子阶段，但保留 P2 partial

- 日期：2026-08-01
- 状态：通过；只关闭 P2 界面 DIT 子阶段，不代表完整 P2 或 T03

### 决策

- 保持已通过的 bottom 单界面、线性准静态方程，固定零陷阱控制和三个 E1 文献约束点 `8.43e11/3.07e12/6.02e12 cm^-2 eV^-1`；共同偏压和 T02-C 提取口径不改。
- V1 的 DEVSIM mesh 重名失败与两-decade SS 窗口线性度失败都保留为归档证据。V2 只将 SS 固定窗口改为一 decade，仍保持 `R2>=0.98`、控制器件和其他门槛不变。
- 将 VTH、SS、`VTG=-0.5 V` 最低栅压电流和 gm 只报为冻结教学模型数值代理；方向性假设不作完成门，尤其是线性化 `Psi_neutral=0 V` 下最低栅压电流增大不解读为物理 Ioff。
- 只在合同 21/21、运行器 14/14、独立 16/16、零 DIT T02-C 回归和落盘状态/VTK/PNG 哈希全部通过后关闭该子阶段。

### 结果边界与下一步

- V2 产生 4 器件、164 次 DC、124 个正式点和 4 个状态，VTH 随 DIT 增加、SS 恶化、gm 下降；这些只是数值敏感性，不是测量、拟合、能量分布或不确定度结果。
- 该子阶段通过后仅允许进入另立的 `T03-P2-BULK-TRAPS` 合同；bulk traps、P3、P5、紧凑模型、SPICE、电路、版图和 HZO 仍保持关闭。

## ADR-023：P2 先冻结单界面 DIT 方程并只关闭冒烟门

- 日期：2026-08-01
- 状态：通过；T03-P2 仍为 partial，不代表正式 DIT 敏感性或完整陷阱组

### 决策

- P2-DIT 的唯一当前变量是 bottom `bottom_interface_D_it_cm^-2_eV^-1`；`bottom_oxide_channel` 为 active interface，`channel_top_oxide` 固定为零，避免将单界面文献值重复施加。
- 采用准静态线性均匀界面陷阱电荷：`Q_it=-q*D_it*(Potential@r1-Psi_neutral)`，`Psi_neutral=0 V` 是显式教学假设；DEVSIM 的 `fluxterm` 写成 `+q*D_it*(Potential@r1-Psi_neutral)=-Q_it`，并保留连续 `PotentialEquation`。
- RSC DOI `10.1039/D6TC00357E` 的 `8.43e11/3.07e12/6.02e12 cm^-2 eV^-1` 在本 ADR 决策时作为后续三点形式扫描（现已由 ADR-024 执行），`4.98e12` 留在来源表但不增加第四个器件；这些值只提供 E1 敏感性范围，不是项目测量。
- 只有 22 项合同、5 案例/17 次 DC 方程冒烟、节点/界面落盘和独立 15 项检查全部通过，才允许进入另立的三点 transfer sensitivity 合同；本次不提取 SS、VTH、Ioff、Ion。

### 结果边界

- 冒烟证明冻结教学模型中的零陷阱极限、界面电势连续、界面通量公式/符号、中心 Gauss 关系、耦合求解收敛和 T02-C 零陷阱回归；独立落盘复核为 E3。
- 该结果不能称为完成 DIT 扫描、完成 P2、动态捕获-发射、迟滞、bias stress、bulk tail/deep traps、双界面验证、实验校准或电路参数。

## ADR-022：P1 电容比采用固定总耦合分配代理并关闭数值组

- 日期：2026-08-01
- 状态：通过；与 T03-P1-BIAS 共同完成数值 P1，不代表物理电容验证或完整 T03

### 决策

- P1-CAP-RATIO 的唯一变量为有效 `Ctop/Cbottom=0.5/0.75/1.0/1.5/2.0`。上下介质物理厚度均固定 30 nm，总平行板耦合代理固定为对称 T02-C 的两倍单栅值，即 `epsilon_top+epsilon_bottom=13.6`。
- 一个比值 `r` 只映射为 `epsilon_top=13.6*r/(1+r)`、`epsilon_bottom=13.6/(1+r)`。这对区域参数是差分静电耦合编码，不是两个 Al2O3 层的实测体介电常数，也不代表已制造的非对称介质栈。
- P1 拥有固定总量下的差分耦合分配比；P4 继续拥有物理介质厚度、沟道几何和公共介质变化。顶栅主扫、底栅 0 V、`VDS=0.01 V`、31 点偏压网格、10 um 沟道、`interface_4x` 网格、材料、迁移率、接触和提取公式全部继承 T02-C。
- 只有 20 项合同、205 次 DC、155 个正式点、5 个完整状态、运行器 16 项和独立持久化检查 13 项全部 PASS，且比值 1 复现 T02-C，才允许与已通过的 BIAS 子阶段共同关闭数值 P1。

### 实际结果与边界

- 五个新器件各完成 41 次 DC；全部收敛，最大端口相对不平衡为 `4.8429e-10`，5 个节点/单元状态和 30 个 VTK 通过独立内容及哈希复核。
- VTH 代理依次为 `0.368433/0.298337/0.263857/0.228299/0.209247 V`，相对比值 1 的 Delta VTH 为 `+0.104576/+0.034480/0/-0.035558/-0.054610 V`；gm 代理依次为 `2.80673e-5/3.47230e-5/3.93760e-5/4.55185e-5/4.94347e-5 S/cm`。
- 在共同 `VTG=0.3 V` 下，电流、中心势和中心电子浓度均随比值严格增加；比值 1 的曲线、状态、VTH 和 gm 对 T02-C 的落盘复现差异为 0。
- 数值 P1 现已完成，但 P2/P3/P5 和完整 T03 仍未完成。上述量不得称为实测电容比、实测 Al2O3 介电常数、物理 Ion、实验校准、工艺分布或电路可用参数。

## ADR-021：P1 先关闭固定副栅偏压子阶段，电容比另立合同

- 日期：2026-08-01
- 状态：通过；仅完成 T03-P1-BIAS，不代表完整 P1 或 T03

### 决策

- P1 的第一子阶段只改变固定底栅副栅偏压 `VBG=-0.4/-0.2/0/+0.2/+0.4 V`。顶栅保持主扫，沿用 T02-C 的 `VDS=0.01 V`、`-0.5~1.0 V/0.05 V` 网格、恒流 VTH、Delta VTH、gm 和 OLS 口径。
- 上下栅均保持 30 nm、相对介电常数 6.8，平行板 `Ctop/Cbottom=1` 只作为固定几何输入代理。该子阶段不改变介质厚度或介电常数，避免与 P4 几何/介质变量在同一运行中混合。
- 五个 VBG 点各使用新建器件，并在共同 `VTG=0.3 V` 保存完整电势、电子浓度和局部电流密度状态。只有 22 项合同、217 次 DC、155 个正式点、运行器 14 项及独立持久化检查 14 项全部 PASS 才关闭 BIAS 子阶段。
- P1 的电容比要求必须另立 `T03-P1-CAP-RATIO` 合同，先明确它与 P4 的变量归属和固定量；该合同通过前不运行电容比扫描，也不把本次偏压结果写成完整 P1。

### 实际结果与边界

- 五个器件的求解次数为 `45/43/41/43/45`，全部 217 次 DC 收敛；155 个正式点最大端口相对不平衡为 `1.1782e-9`，5 个状态和 30 个 VTK 通过独立哈希及内容复算。
- VTH 数值代理依次为 `0.600083/0.438180/0.263857/0.068202/-0.155482 V`，相对零副栅 Delta VTH 为 `+0.336226/+0.174323/0/-0.195655/-0.419339 V`；五点 OLS 斜率为 `-0.940554 V/V`、`R2=0.995712`。
- 零副栅曲线、中心状态、VTH 和 gm 对 T02-C 的落盘复现差异为 0。E3 只说明证据可独立复算，不提升冻结 E2 教学模型的物理验证等级。
- 这些数值不得称为实测阈值、物理上下栅电容比、实验耦合系数、物理 Ion、紧凑模型参数或电路预测。P1-CAP-RATIO、P2/P3/P5 和完整 T03 仍未完成。

## ADR-020：T03-P4-L 保留理想缩放失败并以方向性敏感性关闭子组

- 日期：2026-08-01
- 状态：通过；仅完成 T03-P4-L，不代表五组 T03 完成

### 决策

- 只改变沟道长度 `L=8/10/12 um`，参考点为 `10 um`；宽度、沟道厚度、上下氧化层、材料、移动率、接触、网格、偏压、求解顺序和 VTH/gm 提取公式均沿用 T02-C。
- 每个长度使用新建器件，完成 41 次 DC 和 31 个正式点；三组合计 123 次 DC、93 点和 3 个 `VDS=0.01 V, VBG=0 V, VTG=1 V` 状态。
- V2 完成门不再假定理想 `I∝1/L`；必须有限、可提取且有网格和偏压顺序一致的 VTH/gm，以及开态电流与 gm 随 L 严格下降。理想 1/L 只作预先冻结的可反验诊断，必须报告但不是完成门。
- 首次 V1 已完整保留，不通过不可用放宽阈值或删除失败结果来关闭子组。

### 实际结果与边界

- V2 合同 25 项、运行器 16 项、独立持久化证据 14 项全部 PASS，证据等级为 E3。T02-C 10 um 参考曲线、中心状态、VTH 和 gm 逐点复现差异均为 0。
- `L=8/10/12 um` 的开态电流代理为 `4.10629e-5/3.59372e-5/3.19487e-5 A/cm`，gm 代理为 `4.45359e-5/3.93760e-5/3.51205e-5 S/cm`，两者均随 L 严格下降。
- V1 理想缩放诊断保留 `FAIL`：VTH 范围 `12.058 mV`、I*L spread `14.315%`、gm*L spread `15.461%`、log I-log L 斜率 `-0.61818`、`R2=0.999517`。这些只说明冻结教学模型在该局部范围不服从预设理想1/L 诊断，不能称为物理短沟道效应、Ion 或缩放定律验证。
- 本子组只关闭 P4-L；P1 双栅、P2 陷阱、P3 接触和 P5 温度仍未实现，不允许进入 M00、定量电路预测或实验标定。

## ADR-019：T02-C 以对称双向曲线、回程和受限代理关闭数值门

- 日期：2026-07-31
- 状态：通过

### 决策

- 顶栅主扫和底栅主扫分别取副栅 `-0.3/0/+0.3 V`，主栅统一取 `-0.5~1.0 V`、步长 `0.05 V`；六条正向曲线各自从新器件初始化。
- 两条零副栅曲线从 `1.0 V` 回扫至 `-0.5 V`，只检验无迟滞方程下的数值路径无关性，不称为真实器件迟滞测试。
- VTH 沿用 T01-D-C 的 `10 nA*(W/L)=60 nA` 恒流对数插值；Delta VTH 以同一主栅方向的零副栅曲线为参考；gm 在 `VTH+0.2 V` 处由中心差分后线性插值；耦合斜率由三点 OLS 给出。
- 只有 21 项合同、318 次 DC、248 点、6 个状态、运行器 15 项和独立 17 项全部 PASS 才关闭 T02 数值门并允许进入 T03。

### 结果与边界

零副栅 VTH 为 0.263857 V，副栅 -0.3/0/+0.3 V 对应 Delta VTH 为 +0.256957/0/-0.304252 V，顶/底主栅耦合斜率均约 -0.93535 V/V。所有数值只属于对称 30 nm Al2O3、理想接触、无陷阱/铁电的冻结教学模型；不得称为实验标定、物理电容比、真实迟滞、参数不确定度或电路可用紧凑模型。

---

## ADR-018：T02-B 以四点正向顶栅族验证最小非零响应

- 日期：2026-07-31
- 状态：通过；只打开 T02-C 双向偏压合同与曲线族

### 决策

T02-B 继承 T02-A 的 `enabled_symmetric_teaching_top_stack` 和 `interface_4x` 网格，固定 `VDS=0.01 V`、`VBG=0 V`、源极 0 V、几何、材料、移动率、接触、方程和温度，只将 `VTG` 按 `0/0.1/0.2/0.3 V` 单向增加。每次正式运行从新建器件、全零偏压 Poisson/耦合平衡和低 VDS 阶梯开始，共 9 次 DC；`VTG=0 V` 点复用低 VDS 阶梯终点，不重复求解。

阶段门仅要求四点漏端电流绝对值、沟道中心电势和电子浓度随 VTG 严格增加，源漏符号和端口守恒正确，且端点响应超过预先冻结的可检出阈值。只在 `VTG=0/0.3 V` 保存节点状态和 VTK；本阶段不引入负偏压、回程扫描、底栅族或任何阈值/跨导提取。

### 实际结果与后果

- 输入合同 17 项检查 PASS；9 次 DC 全部收敛，运行器 10 项和独立 14 项检查全部 PASS。
- 四个漏端二维电流为 `1.1931e-6/3.7004e-6/7.4130e-6/1.1549e-5 A/cm`，随 VTG 严格增加；端点电流比为 `9.6802`。
- 沟道中心电势从 `0.00133269 V` 升至 `0.0565449 V`，增量 `0.0552122 V`；中心电子浓度从 `8.7922e15` 升至 `7.3640e16 cm^-3`，端点比为 `8.3756`。
- 最大源漏相对不平衡为 `1.405e-14`；两个端点各保存 2419 行节点状态和 6 个 VTK 关联文件。
- 该 PASS 只证明冻结教学模型四个非负顶栅点的正向响应和数值可检出性。它不证明负偏压或反向路径、Delta VTH、gm、电容比、耦合斜率、实验精度、物理 Ion/Ioff 或完整 T02。

## ADR-017：T02-A 以移除顶栈定义禁用极限

- 日期：2026-07-31
- 状态：通过；只打开 T02-B 最小非零双栅偏压族

### 决策

T02 启用模式冻结为对称教学顶栈：30 nm Al2O3、相对介电常数 6.8、理想静电 Dirichlet 顶栅，并在沟道/顶介质两侧镜像 T01-D-A 的 12 nm/10 nm 界面法向加密窗口。这个顶栈来自 T00 对称教学假设，不是课程已制造单底栅工艺中的事实层。

“关闭顶栅耦合”不定义为 `VTG=0 V`：只要有限介电常数的顶介质和 Dirichlet 顶栅仍在，零伏顶栅依然会约束沟道电势。禁用极限固定为移除完整顶介质/顶栅域，恢复 T01 的沟道顶部自然零法向通量边界，并复用完全相同的 `interface_4x` 网格、方程、接触和偏压顺序。

T02-A 只在禁用模式运行 VDS=0.01 V、VBG=0/0.1/0.2/0.3/0.5/0.7/1.0 V 的七点回归；启用模式只运行所有端口为 0 V 的 Poisson 与移动电子耦合平衡态。非零顶栅偏压族属于 T02-B，不得用零偏压烟雾代替。

### 实际结果与后果

- 合同 16 项检查 PASS；首次合同检查因 `VBG=0.75 V` 不属于 T01-D-C 冻结参考网格而正确 FAIL，随后改为已有参考点 `0.7 V`，未放宽任何容差。
- 禁用模式 12 次 DC 与启用零偏压模式 2 次 DC 全部收敛。禁用模式为 1394 节点/2560 三角形，启用模式为 2419 节点/4480 三角形。
- 七个回归点对 T01-D-C 的最大电流相对差为 `7.13e-15`、中心沟道电势差为 `4.16e-17 V`、中心电子浓度相对差为 `2.21e-16`；最大端口相对不平衡为 `6.10e-14`。
- 启用顶栈的全零偏压端口电流和最大结点电势均为 0，保存 2419 行节点状态与 6 个 VTK 关联文件；独立 14 项复算 PASS。
- 该 PASS 只证明输入合同、启用拓扑零偏压闭合和禁用极限。它不证明非零双栅电流方向、Delta VTH、gm、耦合斜率、实验精度或完整 T02。

## ADR-016：T01-D-C 只以可复算数值代理关闭教学模型数值门

- 日期：2026-07-31
- 状态：通过；完整 T01 教学模型数值门关闭，打开 T02

### 决策

T01-D-C 继承 T01-D-A 通过的 `interface_4x` 正式网格和 `interface_8x` 参考网格，在 `VDS=0.01 V` 上使用同一 51 点定向 VGS 网格。恒流 VTH 代理固定为 `10 nA*(W/L)=60 nA` 端电流并在对数电流上插值；SS 代理固定在 `1e-13~1e-8 A/cm` 窗口线性回归；场效应迁移率代理固定用 30 nm 物理 Al2O3 电容和 VGS=0.475/0.525 V 中心差分。验收只要求公式可复算、两档网格一致和状态证据完整，不要求代理值接近课程目标或配置的常数输运迁移率。

关态代理、课程目标附近代理和开态代理固定为 VGS=-0.5/0.2/1.0 V。每点保存氧化层/沟道节点电势、沟道电子浓度，以及由 DEVSIM `ElectronCurrent` 边模型投影得到的三角形三节点 `Jx/Jy` 和单元中心平均矢量；局部量使用 A/cm2，接触积分后的二维端口量使用 A/cm。

### 实际结果与后果

- 两档各 51 个正式点，共 120 次 DC 和 102 个正式点全部收敛；最大源漏相对不平衡为 6.76e-8，电流随 VGS 单调增加。
- interface_4x 数值代理为 VTH=0.217535 V、SS=59.6081 mV/dec、场效应迁移率=19.1739 cm2/(V*s)；4x/8x 差分别为 0.017 mV、2.49e-9 相对值和 0.0265%。T01-D-B 四个锚点最大电流回归差为 5.89e-15。
- 三种状态共保存 3 份节点 CSV、3 份含三节点矢量的单元 CSV 和 15 个 VTK 关联文件；运行器 12 项与独立 17 项检查全部 PASS。
- 该 PASS 只关闭冻结教学模型的完整 T01 数值阶段门并允许进入 T02。VTH、SS、迁移率和约 17.42 decade 电流跨度不得写成实验验证参数、物理 Ion/Ioff、预测精度或紧凑模型标定结果。

## ADR-015：T01-D-B 每条 Id-Vd 曲线独立初始化并分离零电流验收口径

- 日期：2026-07-31
- 状态：通过；只打开 T01-D-C 状态与受限提取

### 决策

T01-D-B 固定 T01-D-A 通过的 `interface_4x` 作为正式网格，以 `interface_8x` 只复核 VGS=0.5/1.0 V。每条曲线都从新建器件的零偏压 Poisson 与耦合平衡态开始，在 VDS=0 分步升到目标 VGS，再按冻结 Stage 3 的 VDS=0/0.01/0.05/0.1/0.2 V 逐点求解，禁止沿用上一条曲线的终态。VDS=0 用绝对端口电流阈值验收；只有 `VDS > 0` 才使用相对源漏电流不平衡，避免对舍入级零电流作无意义除法。

### 实际结果与后果

- interface_4x 的 VGS=0/0.3/0.5/1.0 V 四条正式曲线与 interface_8x 的两条复核曲线共 65 次 DC、30 个正式点全部收敛，运行器 11 项与独立 16 项检查 PASS。
- VDS=0 最大绝对端口电流为 3.38e-19 A/cm；非零 VDS 最大源漏相对不平衡为 7.28e-14。所有曲线随 VDS 单调不减，正式网格电流在相同非零 VDS 下随 VGS 有序。
- 高栅压 4x/8x 最大电流差为 0.01639%，最大中心沟道势差为 0.03289 mV；T01-D-A 的 4 个低漏压锚点最大电流回归差为 1.50e-14。
- 该结果只允许声称冻结教学模型的 30 个离散输出点通过数值门。点间连线不证明连续输出行为、真实饱和机理或沟道长度调制，也不证明实验精度、参数提取、完整 T01 或双栅性能。

## ADR-014：T01-D-A 以界面窗口加密关闭高正栅压网格警告

- 日期：2026-07-31
- 状态：通过；只打开 T01-D-B Id-Vd

### 决策

固定 T01-C fine 的 x 向网格、体区 y 向网格、几何、材料、温度、迁移率、接触、方程和 VDS/VGS 路径，仅在 Al2O3/IGZO 界面两侧的 10 nm/12 nm 窗口把法向网格按 1x/2x/4x/8x 加密。退出门固定为：全部 DC 收敛、端口守恒、漏电流随 VGS 单调、1x 严格复现 T01-C fine，且 4x/8x 在 VGS=0.5/1.0 V 的最大电流相对差不超过 5%、中心沟道势差不超过 1 mV。

### 实际结果与后果

- 四档网格分别有 656/902/1394/2378 个含界面重复计数的活动节点，共完成 48 次 DC 和 28 个正式偏压点；独立 14 项结果检查 PASS。
- 4x/8x 的最大电流相对差为 0.01639%，最大中心沟道势差为 0.03265 mV；最大源漏相对不平衡为 8.45e-14。
- 1x 对 T01-C fine 在 VGS=0/0.5/1.0 V 的最大电流回归差为 7.83e-15，确认新网格路径没有改变既有基线。
- 首次运行因分段长度/间距的浮点商略高于整数，`ceil` 多插入一层节点，正确触发 T01-C 回归 FAIL；修正为近整数稳健计数后，在不改变物理参数和验收阈值的情况下完整重跑通过。
- 该结果只允许声称冻结教学模型在 VDS=0.01 V、VGS=0.5/1.0 V 的绝对电流已达到数值网格收敛。它不关闭完整 T01，不证明实验精度、物理 Ion/Ioff、VTH/SS/迁移率或双栅性能。

## ADR-013：T01-C 通过续算门但保留高栅压网格警告

- 日期：2026-07-31
- 状态：通过；T01-D 必须先完成网格加密

### 决策

T01-C 的退出条件限定为：冻结的 VGS 阶梯全部收敛、端口电流守恒、漏端电流随 VGS 单调、T01-B 的 VGS=0 V 锚点可复现、每点状态可追溯，并报告两档网格差异。完整绝对电流网格收敛、Id-Vd 和参数提取属于 T01-D，不用放宽相对差阈值来声称 T01-C 已网格独立。

### 实际结果与后果

- 两档网格共 30 次 DC 求解和 16 个正式偏压点均收敛，独立 14 项结果检查 PASS。
- VGS=1 V 时粗/细网格电流为 2.761e-5/3.809e-5 A/cm，相对差 27.5%、对数差 0.140 decade；报告状态为 T01-C 续算通过并带 `WARNING`。
- 当前绝对电流、约 17 decade 的数值跨度、VTH、SS、迁移率和 Ion/Ioff 不得用于物理或拟合结论。
- T01-D 的第一任务是累积层局部网格加密；只有网格收敛后才进入完整 Id-Vd 和参数提取。

## ADR-012：T01-A 先冻结单栅电子输运输入合同

- 日期：2026-07-30
- 状态：通过；T01-B/C 已执行，完整 T01 待 T01-D

### 决策

T01 从明确的单栅、电子-only 漂移扩散输入合同开始：厘米制物理坐标，底栅 IGZO 结构，300 K 常数教学迁移率，Scharfetter-Gummel 边通量，理想欧姆源漏和两档结构化网格。顶栅、陷阱、复合、非理想接触、铁电和双栅输运均不进入 T01-A。

### 后果

- `config/tcad_t01_baseline.json` 是 T01-B/C 的唯一输入口径；`10 nm` 有效 TOX 继续只留给未来紧凑模型。
- 偏压必须按“零偏压平衡态 -> 低 VDS -> 分步 VGS -> 输出曲线点”延续，不能直接跳到最大偏压。
- `make t01-a-check` 的 PASS 只代表输入合同通过；当前 `simulation=NOT_RUN`，不能写成 `Id-Vg`、`Id-Vd` 或迁移率结果。
- T01-B 使用独立运行器在两档网格完成零偏压和 VGS=0 V、VDS=0/1/5/10 mV continuation；10 mV 电流网格差为 0.240%，但该结果只打开 T01-C 的 VGS continuation，不关闭完整 T01 门。
- T01-C 继承同一输入口径完成 VGS=-1.0 至 1.0 V 的低漏压续算；高栅压网格警告只打开 T01-D，不关闭完整 T01 门。

## ADR-011：S00 通过教学参数数据门，不通过定量拟合数据门

- 日期：2026-07-30
- 状态：通过

### 决策

S00 审计冻结 `IGZO_T01_TEACHING_BASELINE_V1` 作为 T01 的教学参数输入。审计验证 50 条来源哈希、9 个带单位参数、8 个数据集边界和 6 项冲突登记。G0 状态为 `TEACHING_BASELINE_ONLY`：允许 E2 教学参数二维仿真，不允许实验拟合、模型精度或校准双栅预测。

### 后果

- 30 nm 物理 Al2O3 与 10 nm SPICE 有效 TOX 必须分开使用和报告。
- 学长 IGZO/VTC 表及旧 ngspice/AIM-Spice 输出保持 `reference_only`，不参与拟合。
- 收到条件完整的原始 Id-Vg/Id-Vd、批次和偏压/温度/接触条件后，重新运行 S00 并更新 G0。

## ADR-008：活动范围收敛为单材料双栅 IGZO

- 日期：2026-07-30
- 状态：通过，覆盖 ADR-001 中的旧器件组合

### 决策

主线只保留 IGZO 器件、二维 TCAD、紧凑模型、单极性逻辑和教学 PDK。既有其他材料资产不再进入活动基线，旧电路结果不作为当前证据。

### 理由

- 老师允许缩减材料范围。
- 单材料更适合在普通笔记本和有限周期内做深度双栅模型。
- 避免两类器件数据口径同时不完整造成不可识别参数。

## ADR-009：使用双栅 IGZO 有源负载逻辑

- 日期：2026-07-30
- 状态：架构通过，实现待验证

### 决策

电路主拓扑为双栅 IGZO 有源负载有比例逻辑。固定器件数为 INV 2、NAND2 3、NOR2 3、XOR2 12、RING5 10、全加器 33。理想电阻负载只作求解和 Boolean 冒烟。

### 后果

- 必须报告静态功耗、输出摆幅和尺寸比。
- 有源负载的第二栅作用必须来自 T02/M00，不能凭空设定后称为物理验证。
- 旧电路基线全部失效，需要重做。

## ADR-010：先冻结架构，再开始实现

- 日期：2026-07-30
- 状态：通过

### 决策

当前只建立总体 DAG、数据合同、目录职责和验收门，不运行新的 TCAD、SPICE 或版图生成。架构经用户/老师确认后，按 T01 -> M00 -> C00 -> INV LVS 顺序实施。

## ADR-001：选择“基础 IC 闭环 + 双栅 HZO 扩展”

- 日期：2026-07-29
- 状态：暂定，待 2026-07-30 老师确认

### 候选方向评分

| 方向 | 现有数据/代码 | 两周可交付性 | 文献匹配 | IC 流程经验 | 主要风险 | 建议 |
|---|---:|---:|---:|---:|---|---|
| 精确双栅氧化物 TFT | 4/5 | 4/5 | 3/5 | 5/5 | 原始双栅数据缺失 | **作为主方向** |
| CFET PDK + OISC | 1/5 | 1/5 | 1/5 | 5/5 | 新工艺、新架构、新 EDA 同时导入 | 不作为本次主线 |
| COGENDA Te TFT 拟合 | 1/5 | 2/5 | 1/5 | 3/5 | 无 Te 数据、无已验证环境 | 作为后续独立项目 |
| 纯 HZO/AFE 存储模型 | 2/5 | 3/5 | 5/5 | 2/5 | 偏离老师指定逻辑版图 | 只作为扩展 |

### 决策

基础主线保持 IGZO/SnO 互补逻辑和 PDK/DRC/LVS，以双栅紧凑模型响应高难方向 1，以 HZO 铁电顶栅可编程阈值作为文献支撑的创新点。

### 后果

- 优点：现有资产可复用，有完整 IC 工程经验，扩展有文献深度。
- 代价：必须严格区分实测、标定、文献参数和概念验证。
- 降级：如无双栅数据，双栅/HZO 部分改为参数化敏感性研究，不声称精确拟合。

## ADR-002：ngspice 与 Level61 双轨模型

- 日期：2026-07-29
- 状态：通过

### 决策

- AIM-Spice 保留老师指定的 Level15/HSPICE Level61 参考实现。
- ngspice 使用可审查行为等效子电路，用于自动扫描、电路仿真和 CI 验证。
- 两者用同一份参数 JSON 和同一批误差指标校验，但不声称方程完全相同。

## ADR-003：LVS 必须从 GDS 几何提取

- 日期：2026-07-29
- 状态：通过

### 决策

优先使用 KLayout 原生 LVS。基础实现使用 `CHANNEL` 标记和 IGZO/SnO 有源层识别器件，用 Ti、Al 和 `DIEL_OPEN` 建立连通性。如内置 MOS3/MOS4 提取器不能正确处理顶接触 TFT，实现自定义 TFT3 提取器。

不接受“源 SPICE 与版图生成器同时输出的 SPICE 文本互比”作为最终 LVS 证据，因为它不能发现 GDS 中的开路和短路。

## ADR-004：HZO 扩展的模型层次

- 日期：2026-07-29
- 状态：提案

### 层次

1. `DG-static`：电容加权的上/下栅等效电压，无回滞。
2. `FE-quasistatic`：使用 Landau/可审查回滞状态引起 `Delta VTH`。
3. `FE-NLS`：使用开关时间分布描述瞬态极化，仅在有可用时域数据时实现。
4. `reliability-sensitivity`：将唤醒、疲劳、应变和界面层作为参数敏感性，不冒充完整材料物理 TCAD。

## ADR-005：学长资料只作可追溯参考

- 日期：2026-07-30
- 状态：通过

### 决策

- 不复制或覆盖学长原始 Office/PDF 文件，只保存路径、大小、SHA-256、用途和证据边界。
- 两份 XLSX 通过结构化解析生成规范 CSV，并保留源文件、工作表和原行号。
- `1.xlsx` 缺少 VDS、几何、材料和求解设置；`Vout1/Vout2` 缺少电路工况。二者在元数据补齐前均为 `reference_only`。
- 学长二极管报告和硅 CMOS VisualTCAD 流程只参考实验组织与软件操作，不作为氧化物器件结果。

### 后果

这样可以复用报告经验，同时避免数据身份混乱。若后续恢复原 `.tif/.sim/.lib` 和完整条件，再新增版本化数据集，不修改当前参考 CSV 的来源记录。

## ADR-006：二维 TCAD 采用分层 DEVSIM 路线

- 日期：2026-07-30
- 状态：通过，待老师确认工具接受度

### 决策

1. `T00 electrostatic`：二维双栅 Poisson/Laplace、四端边界、两档网格和上下栅耦合；作为必须可运行的数值基准。
2. `T01 drift-diffusion`：加入电子连续性和漂移扩散，建立单栅 IGZO 电流基线。
3. `T02 traps/contacts/dual-gate`：加入陷阱、接触和双栅扫描，才用于阈值与 I-V 讨论。
4. `T03 five-group sensitivity`：双栅、陷阱、接触、几何/介质、温度五组受控分析。

### 已有证据

`T00` 在 DEVSIM 2.10.0 上运行通过：粗网格 273 个区域节点计数/400 个单元，细网格 943/1600；中心沟道势均为 0.5 V；上下栅耦合均为 0.5 V/V。

### 证据边界

`T00` 无移动电荷、陷阱、接触输运和漏电流，不能称为“完整 IGZO TFT TCAD”或“精确双栅模型”。

## ADR-007：最终报告以单文件 HTML 为唯一格式主源

- 日期：2026-07-30
- 状态：通过

### 决策

- 工作稿使用结构化 XHTML，严格包含老师要求的 12 个主章节和附录 A-E。
- 报告图片在工作阶段来自 `report/assets/`，正式构建时转换为 Base64 data URI。
- 正式构建拒绝未解决的 `[待填写...]`、外部图片、绝对路径、外部 CSS/脚本和空 `alt`。
- PDF 只能作为可选阅读副本，不替代最终单文件 HTML。

### 后果

报告结构检查可以提前自动化，但在内容仍为空时不能生成“伪最终版”。所有结论继续通过 `report/evidence_matrix.csv` 追溯到数据、脚本和命令。
## ADR-058：R09 静态合同断言失败保留，转入 R10

- 状态：R09 静态 checker 唯一执行返回 34/36、E0/FAIL；R09 runner 与独立 checker 未运行。
- 两个失败项均为合同断言缺陷：复用黑名单检查没有允许已经保留的 R08 失败归档路径；R09 `next_gate` 文本没有包含本合同要求的 independent-check wording。
- 报告 `results/reports/m01_xyce_build_preflight_contract_r09.json` 和日志 `results/compact/m01_xyce_build_preflight_r09_contract_assertions_failed.log` 已按 SHA-256 登记；报告明确 0 个 build/simulator process、无器件网表和数值输出。
- R09 配置、公共模块、静态 checker、runner、独立 checker 和失败报告保持不可改写，禁止重跑。R10 必须使用新 config/source/output namespace，只修正这两个断言，继续绑定 R09/R08/R07 全部失败证据，不改变 IGZO 候选、物理输入、阈值或 no-downstream 门。
- 正式 M01 器件 DC、ngspice/AIM-Spice 数值、电路、版图、PEX 和 HZO 继续关闭；R10 只有在实施提交后才可唯一执行 36 项静态合同。

---

## ADR-057：R09 新命名空间修正 R08 checker 注册缺陷

- 状态：已实施，静态合同尚未运行；当前证据 E0。
- R08 唯一静态执行在报告生成前以 `expected=36 actual=30` 中止。R09 不修改或重跑 R08，而是复制为独立的 config/common/static-checker/runner/independent-checker 和输出命名空间。
- R09 继续绑定 R07 42/47 `.prn` 观察、R07 完整 generator/Xyce 安装树和 R08 配置/源码/失败归档的 SHA-256；新增六项静态审计，确保 36/36 注册、R08 失败归档完整、R08 不重跑、R09 输出与失败目录隔离、静态 checker 不启动进程。
- R09 只允许 `Xyce -v`、`-license`、受控标量 B-source `.prn` 解析和冻结 IGZO 候选 `-syntax` 作为未来 runner 命令；不构建、不调用 ngspice/AIM-Spice、不求解正式器件 DC、不产生 M01 数值或下游证据。
- 下一门是提交并推送 R09 实施后唯一运行 36 项静态合同；只有已提交 36/36 PASS 才能开启 R09 runner，R07/R08 runner 和独立 checker 永久关闭。

## ADR-056：R08 静态合同注册表失败保留，转入 R09
