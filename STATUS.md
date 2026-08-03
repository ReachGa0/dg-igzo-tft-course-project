# 项目状态

- 最后更新：2026-08-03
- 当前阶段：`C00_R03_IMPLEMENTED_STATIC_NEXT`
- 整体状态：`YELLOW`
- 当前原则：C00 R02 50/50 E3 静态 PASS 与 runner 提交自引用阻塞已由提交 `747f384` 保留。R03 新命名空间已实现，只以同步 HEAD/origin 快照和后续登记报告哈希替代自引用字段；当前为 `contract_implemented/E0`，50 项静态门尚未运行，电路与下游权限保持关闭。

## 本次里程碑

- [x] 新增 `C00_ACTIVE_LOAD_INVERTER_R03` 配置、pure common、50 项零进程静态 checker、36 项未来 runner、29 项未来独立 checker 和三个 Make 入口；全部未来输出使用独立 R03 路径并拒绝覆盖。
- [x] R03 哈希绑定 R02 实现提交 `216c6a7`、保留提交 `747f384`、五个源文件、50/50 静态报告 `e820af3b...1a99`、runner 阻塞报告 `9c810623...6ea51` 和项目检查失败 `e6fb9087...f4c6`；R02 不修改、不重跑。
- [x] 唯一语义修正为：静态 checker 在已推送实施提交上记录同步 HEAD/origin 快照；未来 runner 要求当前 HEAD/origin 同步、静态报告哈希已登记且报告内快照同步；未来独立 checker 对 runner 报告采用同一规则。不存在 tracked 字段等于包含它的提交哈希。
- [x] 2-TFT 端口、portable IGZO 候选、ASCII 标识符整词范围、18/36 案例、锚点、提取、验收阈值、两条开源路线、50/36/29 三门、四进程串行预算和失败保留均与 R02 不变。
- [x] JSON/Python 语法与纯内存生成自检通过：18 个 DC、36 个瞬态案例和四份 ASCII 网表结构成立；`make check` 为 766/766 PASS，`make report-check` 为 12 章、5 附录、15 个既有占位和 30 图 PASS，`git diff --check` 通过。检查没有运行 R03 静态 checker、模拟器或落盘网表，R03 运行目录、报告和数值输出均不存在。
- [ ] 下一门：提交并推送 R03 实现，确认与 `origin/main` 同步后，唯一运行 `make c00-active-load-inverter-r03-contract-check`。只有 50/50 E3 静态 PASS 及报告哈希另行提交推送后才允许四个串行电路进程。

- [x] R02 实现提交 `216c6a7` 推送并与 `origin/main` 同步后，唯一运行 `make c00-active-load-inverter-r02-contract-check`，返回 50/50 PASS、E3；报告 `results/reports/c00_active_load_inverter_contract_r02.json` SHA-256 为 `e820af3b6a80095a907ddbdc7ddab5461937cd99ff1bc442e03a6ffd07bd1a99`。
- [x] 50 项静态门验证 R01 五源/46/48 报告不可变、R02 仅作 ASCII 标识符整词修正、2-TFT 拓扑、18/36 案例、锚点、提取、阈值、工具、四进程预算、失败保留和零输出边界；报告记录 `simulator_processes_invoked=0`、`circuit_netlists_created=0`。
- [x] runner 执行前源码审计发现 `HEAD == origin == machine.static_pass_commit` 不能与已提交的 tracked `static_pass_commit` 登记同时成立：写入该值会改变同一提交的哈希。阻塞报告 `results/reports/c00_active_load_inverter_r02_runner_gate_self_reference_blocked.json` SHA-256 为 `9c810623...6ea51`；runner 未调用，0 网表、0 进程、0 数值输出。
- [x] 禁止以未提交机器状态、移动 Git 引用、改写历史、修改已哈希绑定 R02 runner 或重跑 R02 绕过该门。R02 状态登记为 `static_contract_passed_runner_gate_blocked/E3`，但 `circuit_execution_permitted=false`。
- [x] 登记该状态后的首次 `make check` 为 764/765：历史 M01 收口检查未接受新 C00 根状态枚举。失败报告 `results/reports/project_check_c00_r02_static_blocked_m01_scope_stale_failed.json` SHA-256 为 `e6fb9087...f4c6`，记录 0 个模拟器进程；修正只增加该枚举并哈希绑定归档，不改 R02 合同、报告、输入、阈值或权限，随后 `make check` 恢复为 765/765 PASS。
- [x] R02 50/50 PASS 与阻塞证据已由提交 `747f384` 推送，独立 C00 R03 已建立；R03 只修正 committed-state Git 绑定并保持全部电路合同不变。

- [x] 新增 `C00_ACTIVE_LOAD_INVERTER_R02` 配置、pure common、50 项零进程静态 checker、36 项未来 runner、29 项未来独立 checker 和三个 Make 入口；所有 R02 输出使用独立命名空间并拒绝覆盖。
- [x] R02 哈希绑定实现提交 `4097b9d`、失败登记提交 `60cdcbc`、R01 五个源文件和 46/48 报告 `53f408e...a08493`。静态门新增“R01 不可变失败”与“仅 token-safe 修正”两项检查。
- [x] 禁止范围规则统一为正则 `[A-Za-z_][A-Za-z0-9_]*` 提取 ASCII 标识符后进行不区分大小写的精确相等；合法节点 `NORM` 不再被禁止词 `nor` 的子串规则误判。该修正不改变任何物理、电路、扫描、提取或验收输入。
- [x] `config/experiments.json` 登记 R02 `contract_implemented/E0`、五个源哈希、50/36/29 三门和零执行状态；R01 仍为 `contract_failed_static_checker/E0`。当前没有 R02 静态报告、运行目录、正式网表、数值表、图片或独立报告。
- [x] R02 JSON/Python 语法、纯内存 18/36 案例与四文本 token-safe 自检通过；`make check` 为 765/765 PASS，`make report-check` 为 12 章、5 附录、15 个既有占位和 30 图 PASS。检查没有启动模拟器或落盘 R02 网表。
- [x] R02 实现已提交推送，50 项静态门已唯一运行并 PASS；因上述 Git 自引用门，R02 四进程 runner 保持未运行。

- [x] 实现提交 `4097b9d` 推送并与 `origin/main` 同步后，唯一运行 `make c00-active-load-inverter-r01-contract-check`，返回 46/48、E0/FAIL；报告 `results/reports/c00_active_load_inverter_contract_r01.json` SHA-256 为 `53f408e870e5f84993dd635cf95086c9b4db263ea5b8bead6cc2f5ed44a08493`。
- [x] 唯一主失败 `netlist:forbidden_scopes_absent` 来自普通子串规则：禁止词 `nor` 命中 DC 控制节点 `NORM`；`result:static_contract_ready` 为派生失败。其余 46 项通过，未否定拓扑、模型、P6 网格、锚点、提取、阈值、资源或失败保留合同。
- [x] 静态报告记录 `simulator_processes_invoked=0`、`circuit_netlists_created=0`，C00 结果目录、运行表、图和 runner/独立报告均不存在。R01 报告和源码冻结，不重跑；正式电路、C01+、版图、PEX 与 HZO 继续关闭。
- [x] R01 失败登记后的 `make check` 为 764/764 PASS，`make report-check` 为 12 章、5 附录、15 个既有占位和 30 图 PASS，`git diff --check` 通过；检查阶段没有启动模拟器或创建电路网表。

- [x] 新增 `C00_ACTIVE_LOAD_INVERTER_R01` 配置、pure common、48 项零进程静态 checker、36 项未来 runner、29 项未来独立 checker 和三个 Make 入口；所有未来输出使用独立 C00 R01 命名空间并拒绝覆盖。
- [x] 固定 2-TFT 双栅 IGZO 有源负载拓扑：驱动 `D/TG/BG/S=VOUT/VIN/0/0`，负载 `VDD/V_TOP_LOAD/VDD/VOUT`；`Wdriver=60 um`、`L=10 um`，负载宽度由 `Wload/Wdriver` 决定，不允许电阻负载进入正式结果。
- [x] 预注册 `VDD=0.1/0.2 V`、三档负载顶栅比例、三档负载/驱动宽度比和 `Cload=0.5/1 pF`，形成 18 个 DC 与 36 个瞬态计划案例；锚点固定为 `v200_t100_r0125_c1000`，禁止运行后换最佳案例。
- [x] 冻结 VOH/VOL/VM/增益/VIL/VIH/NML/NMH、静态功耗、tPHL/tPLH 和第二周期动态功耗提取；两路线锚点必须同时通过登记电平、增益、噪声裕量和延迟门，路线差异只作诊断且不得运行后放宽阈值。
- [x] 冻结一个 ngspice DC、一个 ngspice 瞬态、一个 GPL Xyce DC 和一个 GPL Xyce 瞬态共四个严格串行进程；AIM-Spice、TCAD、C01+、版图、PEX、SnO 和 HZO 预算均为 0。当前没有执行静态合同、生成正式网表或创建数值输出。
- [x] 开发期 JSON/Python 语法与纯内存网表生成检查通过：18/36 案例和四份 ASCII 文本结构成立，未落盘 C00 网表；`make check` 为 764/764 PASS，`make report-check` 为 12 章、5 附录、15 个既有占位和 30 图 PASS，`git diff --check` 通过。发现 T02 真实证据为 E2 后已修正合同元数据，未虚构 E3。

- [x] 新增 `M01_OPEN_SOURCE_DEVICE_DC_R03` 配置、common、42 项静态 checker、30 项 runner、24 项未来独立 checker 和三个 Make 入口；全部使用独立 R03 输出命名空间。静态报告与 runner 的 15 个文件产物已落盘，当前只剩独立检查报告未生成。
- [x] 新候选 `spice/models/igzo_dg_behavioral_r03_portable.inc` 精确由 R02 五处登记替换得到：四处版本/子电路标识和唯一语义变化 `limit(x/s,-60,60)` -> `min(max(x/s,-60),60)`；所有 `.param` 与 `BIDS` 行逐字节不变。
- [x] R03 哈希绑定提交 `2ffac20` 下正式器件 R02 40/30/24 与根因 R02 40/30/22 的 16 个配置/源码/报告产物；保持 247 行、两个串行进程、两份 247 器件网表、提取、诊断、失败保留及 no-downstream 边界不变。
- [x] R03 实施提交 `50066b7` 推送并同步后，唯一运行 `make m01-open-source-device-dc-r03-contract-check` 返回 42/42 PASS、E3；报告 `results/reports/m01_open_source_device_dc_contract_r03.json` 的 SHA-256 为 `a30611ad98941bcc576335e2b47f702c4c210d32d16247f42b65356a07c0237a`。检查记录 0 个 build/simulator process、0 个器件网表和 0 个数值输出；R03 runner 与独立 checker 未运行。
- [x] 静态 PASS 登记提交 `e664629` 推送并同步后，唯一运行 `make m01-open-source-device-dc-r03` 返回 30/30 PASS、E2。恰好一个串行 ngspice 和一个串行 GPL Xyce 器件 DC 进程返回 0；两份 247 器件 ASCII 网表、两份有限 247 行表、30 行指标、247 行路线差异、14 个哈希绑定产物和两张非空图均已落盘。runner 报告 `results/reports/m01_open_source_cross_check_r03.json` SHA-256 为 `df188515d5749735fc479998d42d8b4b92ce84d2f40687801c531cc563249c79`。
- [x] R03 runner 观察到两路线最大绝对差 `4.3706900078321897e-19 A/cm`、最大对数差 `2.7533531010703882e-14 decade`，两路最大电流分别为 `4.6825230492225634e-4` 与 `4.6825230492225607e-4 A/cm`。这些差值按预注册合同只作诊断，不是 PASS 阈值；机器精度级一致仍待 24 项独立 checker 从落盘证据重算。
- [x] runner E2 提交 `6f4e89b` 推送并同步后，唯一运行 `make m01-open-source-device-dc-r03-check` 返回 24/24 PASS、E3，启动 0 个进程；报告 `results/reports/m01_open_source_cross_check_r03_check.json` SHA-256 为 `5419f34b20861561137ad19768af4783e4e7372265cc42ccb5abf27c2691a937`。checker 独立再生两份 247 器件网表，解析 raw/PRN，精确重算 247+247 行、30 指标、247 差异，复核 14/14 产物哈希和两图尺寸。
- [x] 独立 E3 在冻结 IGZO 教学域内复现机器精度级路线一致，但不证明方程身份、原生 HSPICE Level 61、物理参数、实验校准、外部验证或正式 M01 通过。R02 路线分歧、根因 R02 最小点边界和所有历史失败均不可改写；M01/C00 在本 E3 状态提交推送并另行记录收口决策前保持关闭。
- [x] 独立 E3 登记后的 JSON/Python 语法检查通过，`make check` 为 763/763 PASS，`make report-check` 为 12 章、5 附录、15 个既有占位和 30 张图 PASS，`git diff --check` 通过；登记检查没有启动任何 simulator 或下游进程。
- [x] 独立 E3 提交 `5d2134c` 推送并同步后，按冻结 M01 验收单独作出 `M01_TEACHING_MODEL_ONLY_PASS` 决策：同一 247 行目标、明确模型边界、两路输出与差异完整落盘、R11 工具/parser 预检均满足；原合同明确 M01 验收是可审计比较与限制说明，不要求强制方程一致。
- [x] M01 只在 R03 portable IGZO 教学候选、ngspice/GPL-Xyce 行为路线和登记有效域内 `DONE_WITH_LIMITATION/E3`。未授权 AIM-Spice、全部 build/tool/合同失败、R01 39/40、R02 路线分歧及根因历史均原样保留；不声称原生 AIM-Spice Level 15、HSPICE Level 61、方程身份、物理参数、实验校准、外部验证或电路验证。
- [x] C00 状态仅切为 `contract_planning_open/E0`：允许建立并静态检查双栅 IGZO 有源负载反相器合同，当前 `circuit_execution_permitted=false`，不得生成或运行正式电路网表，也不得打开 C01/C02/C03、版图、PEX 或 HZO。
- [x] 收口登记后的 JSON/Python 语法检查通过，`make check` 为 763/763 PASS，`make report-check` 为 12 章、5 附录、15 个既有占位和 30 张图 PASS，`git diff --check` 通过；没有启动 simulator、生成电路网表或创建电路数值输出。
- [x] runner E2 登记后的纯静态验证为：相关 JSON/Python 语法通过，`make check` 763/763 PASS，`make report-check` 为 12 章、5 附录、15 个既有占位和 30 张图 PASS，`git diff --check` 通过；检查阶段没有启动 TCAD/SPICE 或下游进程。
- [x] R03 实施登记后的 `make check` 为 763/763 PASS，`make report-check` 为 12 章、5 附录、15 个既有占位和 28 张图 PASS，`git diff --check` 通过；静态合同没有启动任何仿真，剩余 17 个未来输出路径保持缺失。
- [x] 静态 PASS 登记后的首次项目总检查因历史 next-scope 白名单和 R03 ready-state 断言滞后返回 14 项失败；归档报告 `results/reports/project_check_m01_open_source_device_dc_r03_static_pass_next_scope_stale_failed.json`、SHA-256 `b80e696b376fdb087117ca386490a4b6dbb13516d2b1fe209ba92a3b51c87403` 已保留。修正只扩展已登记 R03 runner scope 并绑定归档，随后 `make check` 恢复 763/763。
- [x] 新增 `config/m01_xyce_build_preflight_r01.json`、静态合同检查器、构建 runner、独立落盘检查器和三个 Make 入口；合同 25/25 PASS、E3，runner/独立检查分别冻结 29/20 项。
- [x] 用户目录已固定 Xyce 7.10.0、Trilinos 14.4、SuiteSparse 7.8.3 和 CMake 3.30.5 官方包；实际 Xyce 归档 SHA-256 为 `b5a883196f0a2b3972fd13c541fecf04735bfabc7d124d7c7e17de707204f4e2`。
- [x] 明确保留恢复合同中的历史转录串 `...541cfecf...` 和原 30/30 报告，不改写旧证据；新预检合同登记重复重算得到的 `...541fecf...`，只把后者作为构建输入。
- [x] 构建计划为用户目录串行两任务、MPI/Fortran 关闭；先构建 SuiteSparse AMD、Trilinos、Xyce，再做版本/许可证指纹、受控标量 B-source 自测和随后 `-syntax` 的冻结 IGZO 候选解析。正式器件 DC 与 ngspice 路线均未运行。
- [x] M01 Xyce build/tool R01 已在提交 `ee5116e` 推送后唯一运行：来源/工具 14 项通过，SuiteSparse 配置因 CMake 找不到用户目录 `BLAS_LIBRARIES` 在 5.5 秒停止；runner 14/29、独立检查 9/20，均为 E0/FAIL。R01 的报告、独立报告、日志、命令 manifest 和部分构建 cache 保留，未启动 Xyce/ngspice/AIM-Spice，未创建器件/数值输出。
- [x] M01 Xyce build/tool R02 静态合同检查已唯一运行：22/25、E0/FAIL。BLAS/LAPACK 路径、R01 失败绑定和 R02 输出隔离门通过；失败仅为候选注释 `translation` 被 `tran` 子串误判，以及 wrapper 静态 no-formal 标记缺失。报告 `results/reports/m01_xyce_build_preflight_contract_r02.json` 原样保留，未运行任何 R02 configure/build、Xyce、自测、器件网表或数值输出。
- [x] M01 Xyce build/tool R03 合同已建立并按规则唯一执行静态检查：配置固定显式 BLAS/LAPACK、独立 `r03` 构建/输出根、R01/R02 失败绑定、token-safe 候选词边界和 runner/独立 checker no-formal 静态标记；报告 21/25、E0/FAIL，失败已保留，未运行 configure/build、Xyce、自测、器件网表或数值输出。
- [x] M01 Xyce build/tool R03 静态合同已唯一运行：21/25、E0/FAIL，报告 `results/reports/m01_xyce_build_preflight_contract_r03.json`、SHA-256 `be516ad9d0f8998cf3b0e9e441f45312d9d7db21e1934fa3df5cfc18b4f6c3c3` 原样保留。失败为 R03 checker 的 planned-state 断言、错误包装器文件名断言和缺失 R01 字面量断言；没有运行 configure/build、Xyce、自测、器件网表、ngspice/AIM-Spice 或数值输出。
- [x] M01 Xyce build/tool R04 静态合同已唯一运行：25/26、E0/FAIL，报告 `results/reports/m01_xyce_build_preflight_contract_r04.json`、SHA-256 `bc5dcd446fa9bc613504458cac4ac58351e1a594f6764cba5bb9f4e448e7448e` 原样保留。唯一失败是实验机器状态断言仍期待 `preflight_planned`，而注册状态为 `contract_planned`；其余 25 项通过。没有运行 configure/build、Xyce、自测、器件网表、ngspice/AIM-Spice 或数值输出。
- [x] M01 Xyce build/tool R05 静态合同已唯一运行：27/27 PASS、E3，报告 `results/reports/m01_xyce_build_preflight_contract_r05.json`、SHA-256 `4c45dbd06b53aa55b0fcdea88a4e3cc5fdacc889162102cecf4fefecce4b6262`。它绑定 R04 25/26 失败并明确断言 `contract_planned`；检查器启动 0 个模拟器进程，未创建器件网表或数值输出。
- [x] M01 Xyce build/tool R05 runner 已唯一运行：19/29、E0/FAIL，报告 `results/reports/m01_xyce_build_preflight_r05.json`、SHA-256 `893e890b561298cde332cfcd5f466ab34d706dd46ae26f506701bc3772cc7ffc`。SuiteSparse AMD-only 与 serial MPI/Fortran-off Trilinos 安装通过，Trilinos 编译约 1068.870 s；Xyce 配置通过，但构建在 Bison/Flex 生成阶段因 `/usr/bin/m4` 缺失和 Bison 默认 `/usr/share/bison` 数据路径缺失停止。Xyce 二进制、自测、parser-only 候选、ngspice/AIM-Spice、正式器件 DC 和数值输出均未产生，独立检查按门未运行。
- [x] R05 失败状态已提交并推送为 `6779aab`；全部原始日志、manifest、结构化报告、成功依赖安装和 partial Xyce build 保留，R05 不重跑。
- [x] R06 合同实施在唯一静态检查前已完成：官方 GNU M4 1.4.19、GNU Bison 3.8.2、Flex 2.6.4 归档与许可证哈希已冻结；R05 SuiteSparse/Trilinos 完整安装树摘要分别为 `a47a4179...160f` 和 `5d4b574b...afb1`。专用 runner 只源码构建生成器和新根 Xyce，不重建两项依赖，不复用 R05 partial Xyce；静态/runner/独立检查分别登记 37/47/25 项。
- [x] 首次开发期 `make check` 为 655/656：总检查器把 R06 合同 checker 内用于审计的字符串 `import subprocess` 误判为真实导入。失败报告已保存为 `results/reports/project_check_m01_xyce_r06_contract_source_subprocess_literal_failed.json`；修正只改为行首 import 匹配，随后 657/657 PASS，不改变 R06 合同或门槛。
- [x] 提交 `ce4687e` 推送后，R06 静态合同按门唯一运行并返回 36/37、E0/FAIL；报告 `results/reports/m01_xyce_build_preflight_contract_r06.json`、SHA-256 `e9f333f38ad3d1b533b75f29b8574d9cf1bd829a3bdb58215ba4e470f31cbf98` 原样保留。唯一失败为 `checker:r06_independent_standard_library`：独立 checker 为哈希绑定合法登记 runner 路径，静态 checker 却要求该文件名不出现在源码中。没有构建、模拟器进程、器件网表或数值输出。
- [x] 注册 R06 失败后的首次 `make check` 为 653/658：M00 与 M01 R02/R03/R04/R05 五个历史检查仍把当前下一门限制在 R06 实施前状态。失败报告 `results/reports/project_check_m01_xyce_r06_failure_next_scope_stale_failed.json`、SHA-256 `e1492a11872d20ad3d343e0d66afa4d1e21600feef64e714acc7146bea7f9bbe` 已保留；修正只允许已登记的 R06-failure-to-R07 scope，随后 659/659 PASS，不改历史状态、输入或门槛。
- [x] R07 合同实施已完成但尚未运行：新增独立配置、公共树哈希模块、39 项静态 checker、47 项 runner、25 项独立 checker 和三个 Make 入口。R07 哈希绑定 R06 配置/checker/36/37 报告及两份项目检查失败；独立 checker 可登记 runner 路径，但不得导入 runner、导入/调用 `subprocess` 或执行进程。官方源码继续复用原哈希路径，build/install/output 全部换为新的 `r07` 根且当前不存在。
- [x] R07 实施提交 `d421277` 推送并确认与 `origin/main` 同步后，静态合同按门唯一运行：39/39 PASS、E3。报告 `results/reports/m01_xyce_build_preflight_contract_r07.json` 的 SHA-256 为 `2d8cfe605dd86f8313043e42834b4acbd916c165d8d1765758fa609aba0b7fdd`；报告记录 0 个 build/simulator process、无器件网表和数值输出，全部 R07 build/install/output 根仍为空。
- [x] R07 build/tool runner 在静态 PASS 状态提交后唯一运行：42/47、E0/FAIL。R07 生成器和 Xyce 7.10.0 纯源码构建/安装、版本/许可证、自测进程均通过；Xyce 实际生成 `bsource_self_test.prn` 且内容为 1.25 V，但 runner 只查找预注册 `.csv` 并用 CSV 解析，导致 self-test 两门和后续 parser-only/调用审计三门失败。报告 `results/reports/m01_xyce_build_preflight_r07.json` SHA-256 `7e2c17794b013c9928e3b707c674d3da4413c98aa2ab4ec25d2d145856d0a6e6`、全部日志、manifest、`.prn`、完整 generator/Xyce 安装树均保留；独立 R07 检查未运行。
- [x] R08 输出/parser 恢复合同已实现但尚未执行：配置绑定真实 R07 提交 `9a7375ef30ae90adf5214b3c7421a5f7a8cab726`、R07 42/47 失败报告和完整 generator/Xyce 安装树；新 runner 只登记 Xyce 版本、许可证、标量 B-source `.prn` 解析和冻结 IGZO 候选 `-syntax` 四条命令，禁止构建、ngspice、AIM-Spice、正式器件 DC 和下游输出。静态/runner/独立检查冻结为 36/32/25 项，R08 输出根当前全部不存在。
- [x] R08 静态合同按提交 `95d6563` 唯一执行一次，但 checker 在写报告前发现注册表错误并返回 `expected=36 actual=30`。该 E0 checker 失败不是 Xyce/权限/器件失败；归档 `results/reports/m01_xyce_build_preflight_contract_r08_registry_mismatch_failed.json` 与对应日志，未启动 build、Xyce、ngspice、AIM-Spice、器件网表、R08 runner 或独立检查。R08 源码和配置不重跑，R09 使用新命名空间修正注册缺陷。
- [x] R09 输出/parser 合同已建立但尚未执行：新配置绑定 R08 30/36 注册表失败、R07 42/47 `.prn` 观察和完整 hash-bound Xyce 安装树；静态 checker 补齐至 36 项，runner/独立 checker 仍冻结为 32/25 项，所有 R09 报告、输出目录和正式 M01 输出均不存在。该状态只表示 E0 实施链，不表示静态 PASS、Xyce parser 运行、器件曲线或 M01 完成。
- [x] R09 静态合同在提交 `9285865` 后唯一执行并返回 `34/36`、E0/FAIL。失败项为 `reuse:allowlist_and_namespace_denylist`（未允许保留的 R08 失败归档路径）和 `boundary:evidence_and_next_gate`（R09 next_gate 缺少独立检查字样）；报告 `results/reports/m01_xyce_build_preflight_contract_r09.json` 与日志 `results/compact/m01_xyce_build_preflight_r09_contract_assertions_failed.log` 已保留。检查记录 0 个 build/simulator process、无器件网表/数值输出，R09 runner/独立检查未运行，R10 只修正这两个合同断言。
- [x] R10 合同实施已建立：新增独立 config/common/static checker/runner/independent checker、36/32/25 注册和三个 Make 入口。R10 绑定 R09 34/36 报告/日志以及 R08/R07 全部历史失败哈希，只修正 R09 允许保留历史归档和独立检查 wording 两项断言；R10 报告、runner/独立报告、输出目录和正式 M01 输出尚不存在，未启动任何 build、Xyce、SPICE、器件网表或下游进程。
- [x] R10 静态合同在实施提交 `bd7ebda` 推送后唯一执行并返回 36/36 PASS、E3；报告 `results/reports/m01_xyce_build_preflight_contract_r10.json` 的 SHA-256 为 `a7dbcf6d639897f6648d25a151d3a29c48c3dc352992a7872104b684b29fe785`。报告验证 R09/R08/R07 哈希绑定、36/32/25 注册与 no-execution 门，记录 0 个 build/simulator process、无器件网表和数值输出；R10 runner/独立 checker 未运行。
- [x] 注册 R10 静态 PASS 后首次项目总检查为 683/684：历史 R08 状态检查尚未接受已合法推进到的 execute-R10 scope。失败报告 `results/reports/project_check_m01_xyce_r10_static_pass_r08_next_scope_stale_failed.json`、SHA-256 `988ae80969aa18a1d8813fd4d883b82ae4b55a3a784258c0f85b6141ae31103d` 已保留；修正仅补入 execute-R10 状态，随后 685/685 PASS，不改合同、门槛、输入或结果。
- [x] R10 runner 在静态 PASS 提交 `8dff9ad` 后唯一执行。Xyce 版本、GPL 许可证和标量 B-source 三条命令返回 0，固定列 `.prn` 独立解析得到 1.25 V；随后在 `scripts/run_m01_xyce_build_preflight_r10.py:336` 以 ASCII 写入含中文绝对工程路径的 `.include` 行时触发 `UnicodeEncodeError`，parser-only 命令未启动。失败报告 `results/reports/m01_xyce_build_preflight_r10_runner_unicode_path_failed.json`、伴随日志和 8 文件部分目录（树 SHA-256 `5a3d1ac4ff62848fb7132db9211a6281a477b43900e87ddfe6047f6da9fef85e`）保留；0 个 build、3 个 Xyce 工具进程、无正式 DC/数值输出，R10 独立 checker 未运行且 R10 不重跑。
- [x] R11 路径安全合同实施已建立但尚未执行：新增独立配置、公共哈希/固定列解析模块、36 项静态 checker、32 项 runner、25 项独立 checker 和三个 Make 入口。R11 绑定提交 `63be6a4` 下的 R10 配置/源码/36/36 报告/Unicode 失败报告与日志/8 文件部分树；唯一实现变化是用 `spice/models/igzo_dg_behavioral_r02.inc` 仓库相对 ASCII include 配合 project-root cwd，禁止绝对工程路径。所有 R11 输出和正式 M01 输出仍不存在，未启动 build、Xyce、ngspice、AIM-Spice、器件或下游进程。
- [x] R11 实施状态的项目总检查为 700/700 PASS，报告结构检查为 12 章、5 附录、15 个既有占位、26 张图片 PASS；三个 JSON 与五个 Python 文件语法检查通过。该实施里程碑提交前没有运行 R11 正式静态合同。
- [x] R11 实施提交 `f64dc16` 推送并确认与 `origin/main` 同步后，36 项纯静态合同唯一执行并返回 36/36 PASS、E3；报告 `results/reports/m01_xyce_build_preflight_contract_r11.json` 的 SHA-256 为 `73ebc2bd650411e91d7bb704a8d2b26938f47e1a0d83332fd1f5b9e37164e400`。它验证 R10 不可变归档、路径安全 include、36/32/25 注册和 no-execution 门，记录 0 个 build/simulator process、无器件网表/数值输出；R11 runner/独立 checker 未运行。
- [x] R11 runner 在静态 PASS 提交 `b38b319` 推送后唯一运行：`make m01-xyce-build-preflight-r11` 返回 32/32 PASS、E2。版本、许可证、控制 B-source 自测和仓库相对 ASCII include 的 `-syntax` 检查共 4 个 Xyce 工具/parser 进程均返回 0，固定列 `.prn` 观测为 1.25 V；没有构建、正式器件 DC、ngspice、AIM-Spice 或下游进程。报告 `results/reports/m01_xyce_build_preflight_r11.json` SHA-256 为 `cfe369d5df97217499f207701836447f784f5dbc201ad33b01a0b1765841d552`，全部 runner 输出保留，独立检查尚未运行。
- [x] 注册 R11 runner PASS 后，`make check` 为 714/714 PASS，`make report-check` 为 12 章、5 附录、15 个占位符、26 张图片 PASS，`git diff --check` 通过；这些检查没有启动任何新仿真。
- [x] R11 runner PASS 提交 `0660dab` 推送并确认同步后，25 项独立 checker 唯一运行并返回 25/25 PASS、E3；报告 `results/reports/m01_xyce_build_preflight_check_r11.json` SHA-256 为 `792a4f6d4be65746fc08ff0c00205acc2f7b64bc5ad2d3f0c370d27c41d2d615`。它独立复核 runner 32/32、19 个历史绑定、R07 完整安装树、1.25 V `.prn`、相对路径 parser-only 输入/日志、4 命令白名单、8 个正式输出缺失和 no-runner-import/no-process 边界；没有启动任何进程。
- [x] 登记 R11 独立 PASS 后，`make check` 为 715/715 PASS，`make report-check` 为 12 章、5 附录、15 个既有占位符、26 张图片 PASS，`git diff --check` 通过；这些验证没有启动 TCAD/SPICE 或其他仿真进程。
- [x] 建立 `M01_OPEN_SOURCE_DEVICE_DC_R01` 独立命名空间：配置、公共网表/解析/指标模块、40 项纯静态合同检查器、30 项未来 runner、24 项未来独立检查器和三个 Make 入口均已实现。合同固定 247 行/13 曲线、233 scored + 14 audit、同一 `IGZO_DG_BEHAVIORAL_R02` 字节、一个 ngspice 与一个 GPL Xyce 串行进程、两个器件级 DC 网表、247+247 原始行、30 指标行、247 差异行、两图和失败保留。
- [x] 新网表生成器仅在内存完成最小自测：两路线各生成 247 个 IGZO 实例和一个单点 `.DC VSWEEP 0 0 1`，ASCII 字节数为 36452/36365；没有写出正式网表或启动模拟器。
- [x] 首次实施态 `make check` 因新增检查器错误要求预测表与选择清单同序而 1 项 FAIL；报告 `results/reports/project_check_m01_device_dc_r01_prediction_order_assumption_failed.json` SHA-256 为 `dcf6c2ff89fd6f2d31dfc140c55cbe7d04f77e662370e35698acb926653599a0`。修正为选择清单定执行顺序、预测表按既有 `row_uid` 连接后，目标文件字节/物理/阈值未改，总检查 722/722 PASS。
- [x] 正式 runner 还要求静态 40/40 报告已登记为 `contract_ready/E3` 且下一门明确为执行两路线，ngspice/Xyce argv 均与独立构造的冻结命令比较后才可启动；未来独立 checker 同样要求 runner PASS 已登记为 `formal_run_passed/E2`。任何中途 runner 失败都会在结构化报告中哈希绑定已产生的部分文件。
- [x] 提交前复核：5 个相关 Python 文件通过 `py_compile`；18/18 正式输出路径保持缺失；R11 三份报告与候选模型哈希未变；`make check` 为 722/722 PASS，`make report-check` 为 12 章、5 附录、15 个既有占位、26 张图片 PASS，`git diff --check` 通过。没有启动仿真器。
- [x] R01 实施提交 `b8c3a03` 推送并确认与 `origin/main` 同步后，40 项静态合同唯一运行并返回 39/40、E0/FAIL。失败报告 `results/reports/m01_open_source_device_dc_contract_r01.json` SHA-256 为 `7baba2fcd7bc186bfa30780882816c27d33708c91957e0a53db51c8c435b16ba`；唯一失败项 `binding:r11_no_formal_or_independent_process` 错误读取 R11 独立报告不存在的顶层 `processes_invoked`。报告自身记录 0 个 build/simulator process、0 个器件网表、0 个数值输出，运行前 18 个未来路径全缺失，运行后仅该静态报告存在；ngspice/Xyce runner 与独立 checker 均未运行。
- [x] 登记 R01 39/40 失败后，`make check` 为 722/722 PASS，`make report-check` 为 12 章、5 附录、15 个既有占位、26 张图片 PASS，`git diff --check` 通过；没有重跑 R01 或启动模拟器。
- [x] 建立 `M01_OPEN_SOURCE_DEVICE_DC_R02` 新命名空间：配置、common、40 项静态 checker、30 项 runner、24 项独立 checker、R02 排他输出根和三个 Make 入口均已实现。R02 哈希绑定提交 `7d5f079` 下的 R01 config/common/checker/runner/independent 与 39/40 报告；schema 修正在三个 R02 组件中统一使用 R11 既有 `summary.check_count/passed/failed` 和 `independence:no_runner_or_process_import=PASS`。
- [x] 首次 R02 实施态 `make check` 为 1 项 FAIL：总检查器把 R02 静态 checker 为审计未来 runner/independent 而保留的旧字段字符串字面量，误判为 R02 自身仍执行旧字段读取。失败归档 `results/reports/project_check_m01_device_dc_r02_implementation_state_failed.json` SHA-256 为 `bc7fed2c0bf45f5f803a351a41b08eef26434346f80f1a12a069d9ab7eb34221`；修正只禁止旧的可执行条件并保留审计字面量，随后 729/729 PASS。
- [x] R02 内存网表生成自测仍为 247 行、两路线各 247 个 IGZO 实例，ASCII 字节数 36452/36365；5 个 R02 Python 文件通过 `py_compile`，18/18 R02 正式输出路径缺失。没有启动静态合同或模拟器。
- [x] R02 实施态最终 `make check` 为 729/729 PASS，`make report-check` 为 12 章、5 附录、15 个既有占位、26 张图片 PASS，`git diff --check` 通过；R02 40 项正式静态合同尚未运行。
- [x] R02 实施提交 `86c5106` 推送并确认与 `origin/main` 同步后，纯静态合同唯一执行并返回 40/40 PASS、E3。报告 `results/reports/m01_open_source_device_dc_contract_r02.json` SHA-256 为 `0154abfbe5175b91d7622416804561c5bb50bdeeef0792e426d0299a37564d2c`；40 项全部通过，报告记录 0 个 build/simulator process、0 个器件网表、0 个数值输出，18 个预注册路径中仅静态合同报告产生。
- [x] R02 静态 PASS 只把下一门打开到提交后的双路线 runner；它不是 ngspice/Xyce 器件 DC、路线一致性、物理参数、实验校准、正式 M01 或电路证据。runner 与独立 checker 仍为未运行，R01/R11 和更早 revision 均不重跑。
- [x] 登记 R02 静态 PASS 后，`make check` 为 730/730 PASS，`make report-check` 为 12 章、5 附录、15 个既有占位、26 张图片 PASS，`git diff --check` 通过；这些检查没有启动 TCAD/SPICE 或其他仿真进程。
- [x] 静态 PASS 提交 `da7dde8` 推送并确认同步后，唯一执行 `make m01-open-source-device-dc-r02` 返回 30/30 PASS、E2。ngspice/Xyce 各一个串行进程均返回 0；报告 `results/reports/m01_open_source_cross_check_r02.json` SHA-256 为 `3dd916bea81caf582757696674c3f1fe41576122a66fef4c24ff3dd204f53cac`，2 个 247 器件 ASCII 网表、2 份 247 行原始表、30 行指标、247 行路线差异、2 张 PNG 和命令/原始日志全部落盘。无 AIM-Spice、TCAD、电路或下游进程。
- [x] runner 的显式诊断为：ngspice 最大 `|ID|/W` `2.0417057839146633e-31 A/cm`，Xyce 最大 `4.6825230492225607e-4 A/cm`；最大路线绝对差 `4.6825230492225607e-4 A/cm`、最大对数差 `16.670479923821013 decade`。合同预注册路线/目标和路线差异阈值为 diagnostic-only，因此 30/30 只证明有限、完整、可追溯的器件级双路线执行，不证明路线一致、方程身份、物理参数或实验校准。
- [x] runner PASS 登记后的首次 `make check` 返回 741/745，4 项失败均为机器状态登记/历史 scope：通用 JSON 补丁误命中 recovery、R11、R01 三个历史块，R02 自身未切换 E2。失败报告 `results/reports/project_check_m01_device_dc_r02_runner_pass_state_failed.json` SHA-256 为 `5e02032f3e4ab4d9d52d87b94482594e952973f4ad07927aecda37e02b85a72d`；已精确恢复三块历史状态并只登记 R02，不改 runner 产物、输入、阈值或诊断。
- [x] 修正登记后 `make check` 为 746/746 PASS，`make report-check` 为 12 章、5 个附录、15 个既有占位、28 张图片 PASS，`git diff --check` 通过；检查没有启动新进程。
- [x] 推送前 Git blob 审计发现四份 runner CSV 会被全局 LF 规则规范化，三个原生 `.log/.raw` 又被 ignore；这会破坏 runner 报告中的 artifact SHA-256。已为本 R02 hash-bound 目录/表设置逐路径 `-text` 并强制纳入原生日志/输出，只保留原字节，不修改其内容。
- [x] runner PASS 提交 `605cbe9` 推送并确认同步后，唯一执行 `make m01-open-source-device-dc-r02-check` 返回 24/24 PASS、E3，报告 `results/reports/m01_open_source_cross_check_r02_check.json` SHA-256 为 `8afc00cec09ab533b8b3be4fe200529cabf24d35054034d2888e3a9c498e5fac`。标准库 checker 启动 0 个进程，独立再生 2 个网表、解析两份原生输出、精确重算 247+247 行、30 指标、247 差异、14 个 runner 哈希和两张 2240x1760 PNG。
- [x] R02 40/30/24 全部通过只关闭“器件级双路线执行及落盘完整性”证据链；独立复核确认最大绝对/对数差仍为 `4.6825230492225607e-4 A/cm`/`16.670479923821013 decade`。因此 M01 不以路线一致关闭，不能据此打开 C00；R02 不重跑，后续用新合同隔离 ngspice/Xyce 电流语义。
- [x] 独立 E3 登记后 `make check` 为 747/747 PASS，`make report-check` 为 12 章、5 个附录、15 个既有占位、28 张图片 PASS；JSON/CSV/Python 语法和 `git diff --check` 通过，全部检查为零模拟器执行。
- [x] 建立 `M01_ROUTE_DIVERGENCE_ROOT_CAUSE_R01` 独立命名空间：配置、common、40 项静态 checker、30 项最小 runner、22 项独立 checker 和三个 Make 入口已实现。它哈希绑定提交 `6e61c5d` 的 R02 40/30/24 链、候选中的 `limit(x/s,-60,60)`、ngspice 无兼容模式日志和本地 Xyce 7.10 源码哈希。
- [x] 未来最小探针只允许两个串行进程：ngspice/Xyce 各一次，每路观测 3 个 `limit/min/max` 表达式点、1 个已知支路电流哨兵点、3 个原候选点和 3 个只将 clamp 改为 `min(max(...))` 的诊断副本点。正式 247 行 R02 不重跑，候选文件不修改，分支提取和表达式语义分开验收。
- [x] 实施期两次项目检查失败均已保留：首次 `752/753` 是新配置转录 Xyce R02 PRN SHA-256 时遗漏最后一位；第二次 `753/754` 是全文禁止导入扫描误命中自身审计字面量。修正分别只恢复哈希最后一位和只匹配真实行首 import；两份失败均为零模拟器进程。随后项目总检查为 755/755 PASS。
- [x] E0 实施态收口验证：`make check` 755/755 PASS，`make report-check` 以 12 章、5 附录、15 个既有占位、28 张图 PASS；JSON/Python 语法和 `git diff --check` 通过。这些仍是实施/结构验证，不是根因静态合同或数值探针结果。
- [x] 实施提交 `015253f` 推送并确认与 `origin/main` 同步后，唯一执行 `make m01-route-divergence-r01-contract-check` 返回 38/40、E0/FAIL；报告 SHA-256 为 `3aba1c829ca3aea4002f7ee285155a26c68837c9833ab88be3f475f336a34378`。主失败 `observation:r02_divergence_values` 来自 checker 读取不可改写 R02 runner 报告中不存在的顶层 `route_diagnostics`，`result:static_ready` 仅为连带失败；其余 38 项通过。
- [x] R01 静态报告记录 0 个模拟器进程、0 个网表和 0 个数值输出；runner/独立报告、探针目录和探针表均不存在。该失败不支持也不否定三参数 `limit` 假设，不是器件、路线、物理参数或校准结果。R01 不重跑；R02 只能在新命名空间修正诊断证据读取来源。
- [x] 建立 `M01_ROUTE_DIVERGENCE_ROOT_CAUSE_R02` 新命名空间：配置、common、40 项静态 checker、30 项最小 runner、22 项独立 checker 和三个 Make 入口均已实现。R02 只修正 R01 暴露的诊断证据来源，哈希绑定实际落盘的 ngspice/Xyce/route-difference 三份 CSV，并使失败 `next_gate` 按状态生成；表达式点、候选、工具、进程预算、阈值、失败保留和 IGZO 范围不变。
- [x] R02 实施态绑定 R01 提交 `203acaa`、R01 38/40 E0/FAIL 报告和三份既有诊断 CSV；静态/runner/独立报告、探针网表、日志和新增数值输出均不存在。`make check` 为 756/756 PASS，`make report-check` 为 12 章、5 附录、15 个既有占位、28 张图 PASS，`git diff --check` 通过；这些是结构/实施证据，不是 R02 静态 PASS 或敏感性结果。
- [x] R02 静态合同在实施提交 `91fe397` 推送并同步后唯一执行，返回 40/40 PASS、E3；报告 `results/reports/m01_route_divergence_root_cause_contract_r02.json` SHA-256 为 `2870566c9bd6b3f5b0b4db796492afc75a55a5500d630dfa291e81a9ddb21169`。报告记录 0 个模拟器进程、0 个网表和 0 个数值输出；R02 runner/独立检查、探针表和所有探针输出仍缺失。该 PASS 只证明 schema-only 静态执行合同完整，不确认 `limit` 根因、路线一致、物理参数、实验校准、正式敏感性、P2/T03、M01 或电路。
- [x] 登记 R02 静态 PASS 后首次 `make check` 返回 756 总检查、13 项失败；失败全部是历史状态链尚未接受“execute the committed R02 probe”下一门。报告 `results/reports/project_check_m01_route_divergence_r02_static_pass_next_scope_stale_failed.json` SHA-256 为 `518df893d4ee6a42ec3dd030957a62151eb752828f9d974a54633da921d8d23c`，记录 0 个模拟器进程，已原样保留。修正只扩展已登记的 next_scope 白名单，随后 `make check` 恢复 756/756，不改 R02 合同、输入、阈值或探针预算。
- [x] R02 最小根因探针在静态 PASS 提交 `283cf32` 推送并同步后唯一运行，返回 30/30 PASS、E2；报告 `results/reports/m01_route_divergence_root_cause_r02.json` SHA-256 为 `7b878ee2e109afb01d998f6a41c38723e5ed3d2f964ca859809dec205a019ddd`。恰好一个 ngspice 和一个 Xyce 串行进程完成 3 个表达式点、1 个 1 V/1 kOhm 支路哨兵、3 个原始候选点和 3 个 portable 点；所有网表、日志、raw/PRN、命令记录和 26 行探针表均已落盘。
- [x] 探针诊断显示 ngspice 三参数 `limit` 观测为 `-15/60.25/135`，显式 clamp 和 portable 候选分别通过；Xyce 三参数点与 clamp 一致；两路支路电流哨兵均通过。该结果支持预注册表达式语义假设并在这些点排除支路电流提取替代解释，但不建立完整 247 行路线一致、物理 IGZO 参数、实验校准、正式敏感性、P2/T03、M01 或电路证据。
- [x] 登记 R02 探针状态后的首次 `make check` 返回 756 总检查、3 项失败：一次过宽机器状态补丁临时改动了不可变的开源恢复、R11 和 R01 历史块。失败报告 `results/reports/project_check_m01_route_divergence_r02_probe_registration_scope_failed.json` SHA-256 为 `6821a18e74ae21b433f1e732005391e619c5db7a39540b2f6b6b93df35ee3684`，记录 0 个模拟器进程并已保留。修正只精确恢复三个历史块且仅登记 R02 E2，随后 `make check` 恢复 756/756；探针产物、诊断、输入和阈值未改。
- [x] E2 探针提交 `406cfce` 推送并与 `origin/main` 同步后，唯一执行 22 项标准库独立 checker，返回 22/22 PASS、E3；报告 `results/reports/m01_route_divergence_root_cause_r02_check.json` SHA-256 为 `06878ca53aefc1dea557b6eb5838ea48e1bf7459a825d1ee99d996ef1b74d556`，启动 0 个进程。checker 独立再生两份网表、重算 9 个 runner 产物哈希和全部 26 行探针表，并复现 `THREE_ARGUMENT_LIMIT_SEMANTICS_MISMATCH` 分类。
- [x] 独立 E3 只关闭最小数值根因诊断：支路提取替代解释在预注册点被排除，portable clamp 在这些点通过；完整 247 行路线一致明确仍为 false。该结果不是接受的新完整器件候选、物理 IGZO 参数、实验校准、正式敏感性、P2/T03、正式 M01 或电路证据。

### 下一步与关闭条件

- 下一步：提交并推送 M01 `DONE_WITH_LIMITATION` 与 C00 entry-gate 决策后，建立独立版本化 C00 双栅 IGZO 有源负载反相器静态合同，先冻结拓扑、偏压、尺寸、VTC/瞬态提取、失败保留、输出、资源预算和证据边界；合同 PASS 状态另行提交前不得运行电路。
- M01 当前根状态为 `done_with_limitation/E3`，历史根状态 `preflight_failed_tool_provenance/E0` 及 Xyce R01/R05 `preflight_failed_build` 均作为不可改写子证据保留；14/29、9/20、19/29 和 R02/R03/R04 checker 失败不被改标，也不代表物理参数、实验拟合或电路证据。
- P3、P5 已完成并冻结，不得借本阶段重跑；C00 只开放静态合同建立，SPICE 电路执行、版图、PEX 和 HZO 继续关闭。历史 AIM-Spice 预检、M01 revision-1/2 合同失败、28/30 干跑失败和 R10 runner 失败均保留。

## 已完成

- [x] 正式范围收敛为双栅 IGZO 单材料主线。
- [x] 固定双栅 IGZO 有源负载单极性逻辑拓扑。
- [x] 固定 INV/NAND2/NOR2/XOR2/RING5/全加器层次和器件数。
- [x] 建立从 S00 到 R00 的阶段 DAG、接口和验收门。
- [x] 定义高难度五组器件参数和电路附加参数。
- [x] 保留 13 篇 HZO/ZrO2 文献矩阵和可选扩展边界。
- [x] 学长 23 个参考文件已哈希，两份 XLSX 已规范化，6 个 Office 文件已结构化审计。
- [x] 活动冻结基线已重建为 7 个 IGZO 来源副本，旧材料和旧电路副本已移出活动数据集。
- [x] 既有二维双栅静电基准为 E2，可作为后续起点。
- [x] 报告已拆成 12 章和 5 个附录源，按清单组装为最终单文件 HTML，并支持打印分页。
- [x] 文档、配置、目录合同、AI 入口、分章报告合同、17 阶段依赖图、T02-A/B/C、T03-P4-L、完整数值 P1，以及含 DIT、bulk 方程冒烟、V1/V2 失败保留和正式 V3 的完整 P2 证据链均已纳入项目检查。
- [x] 建立 `AGENTS.md` 权威 AI 入口及 Claude/Copilot 兼容指针。
- [x] S00 数据审计已生成 50 条来源哈希、23 条单位记录（9 参数、14 数据字段）、8 个数据集边界和 6 项冲突登记；审计报告 PASS。
- [x] G0 已决策为 `TEACHING_BASELINE_ONLY`：允许 E2 教学参数 T01，禁止称为实验拟合或校准双栅预测。
- [x] T01-A 已冻结单栅 IGZO 输入合同：厘米制坐标、电子漂移扩散、理想欧姆接触、两档网格和分步偏压协议；合同检查 PASS。
- [x] T01-B 已运行 DEVSIM 2D 单栅电子-only 漂移扩散：两档网格的零偏压平衡态和 VGS=0 V、VDS=0/1/5/10 mV 均收敛；10 mV 漏端电流为 1.235e-6/1.232e-6 A/cm，源漏相对不平衡不超过 1.29e-14，粗细网格电流差 0.240%，独立结果检查 PASS。
- [x] T01-C 已在两档网格完成 VDS=0.01 V、8 个 VGS 点的低漏压转移续算：30 次 DC 求解全部收敛，漏端电流随 VGS 单调增加，最大源漏相对不平衡 1.61e-12，T01-B 的 VGS=0 V 锚点复现，16 份节点状态和 6 组 VTK 已保存，独立 14 项检查 PASS。
- [x] T01-C 明确记录网格限制：VGS=1 V 时粗/细网格电流为 2.761e-5/3.809e-5 A/cm，相对差 27.5%、对数差 0.140 decade；当前绝对电流、数值跨度和高栅压结果不得用于定量拟合、Ion/Ioff 或模型精度结论。
- [x] T01-D-A 已固定 T01-C fine 横向/体区网格和全部物理输入，仅在 10 nm 氧化层侧、12 nm 沟道侧界面窗口做 1x/2x/4x/8x 法向加密；4 档共 48 次 DC、28 个正式点全部收敛，节点数为 656/902/1394/2378。
- [x] T01-D-A 的 4x/8x 在 VDS=0.01 V、VGS=0.5/1.0 V 的最大绝对电流相对差为 0.01639%，中心沟道势差为 0.03265 mV，最大端口不平衡 8.45e-14；T01-C fine 回归差不超过 7.83e-15，独立 14 项检查 PASS。
- [x] T01-D-B 已按冻结 Stage 3 网格完成 interface_4x 的 VGS=0/0.3/0.5/1.0 V 四条 Id-Vd 曲线，并用 interface_8x 复核 VGS=0.5/1.0 V；每条曲线均从独立零偏压平衡态开始，6 条曲线共 65 次 DC、30 个正式点全部收敛。
- [x] T01-D-B 的全部采样曲线随 VDS 单调不减，正式网格在各非零 VDS 下随 VGS 有序；非零漏压最大源漏相对不平衡 7.28e-14，4x/8x 最大电流差 0.01639%、中心势差 0.03289 mV，T01-D-A 锚点最大回归差 1.50e-14，独立 16 项检查 PASS。
- [x] T01-D-C 已在 interface_4x/interface_8x 上完成 VDS=0.01 V、VGS=-1 至 1 V 的 51 点定向提取网格；两档共 120 次 DC、102 个正式点全部收敛，最大端口相对不平衡 6.76e-8，漏端电流随 VGS 单调增加。
- [x] T01-D-C 已保存关态代理、课程目标附近代理和开态代理的电势、电子浓度、三角形三节点电流密度矢量及 15 个 VTK 文件；4x 数值代理 VTH=0.217535 V、SS=59.6081 mV/dec、场效应迁移率=19.1739 cm2/(V*s)，4x/8x 差分别为 0.017 mV、2.49e-9 相对值和 0.0265%，独立 17 项检查 PASS。
- [x] T02-A 已以 16 项静态检查冻结对称教学顶栈：30 nm Al2O3、理想静电 Dirichlet 顶栅、与 T01 相同的 IGZO/温度/迁移率/源漏接触；顶栈为 T00 教学扩展，不是已制造工艺事实。
- [x] T02-A 共完成 14 次 DC：移除顶栈的 7 个 VBG 点对 T01-D-C 的最大电流相对差为 7.13e-15、中心电势差为 4.16e-17 V、中心载流子相对差为 2.21e-16；启用顶栈的 2419 节点/4480 三角形零偏压平衡态收敛并保存 6 个 VTK，独立 14 项检查 PASS。
- [x] T02-B 以 17 项静态合同检查冻结最小正向顶栅族；9 次 DC 全部收敛，4 个正式点的漏端电流、沟道中心电势和电子浓度均随 VTG 严格增加，最大端口相对不平衡为 1.41e-14，独立 14 项检查 PASS。
- [x] T02-B 在 VTG=0/0.3 V 保存 2 份 2419 行节点状态和 12 个 VTK 关联文件；端点电流比为 9.6802，中心电势增量为 0.055212 V，中心电子浓度比为 8.3756。
- [x] T02-C 以 21 项静态合同冻结 `VDS=0.01 V`、主栅 `-0.5~1.0 V/0.05 V`、副栅 `-0.3/0/0.3 V`、6 条正向曲线和 2 条零副栅回程曲线；6 个独立器件共 318 次 DC、248 个正式点全部收敛，运行器 15 项和独立 17 项检查 PASS。
- [x] T02-C 的零副栅恒流 VTH 为 0.263857 V；副栅 -0.3/0/+0.3 V 的 Delta VTH 为 +0.256957/0/-0.304252 V，顶/底主栅耦合斜率均约 -0.93535 V/V，R2=0.99764；gm 数值代理为 3.506e-5 至 3.938e-5 S/cm。
- [x] T02-C 最大端口相对不平衡 3.71e-8，正反扫最大电流相对差 8.19e-11，上下栅互易最大电流相对差 3.70e-8；6 组代表状态保存 14514 行节点、3564 个三角形电流密度记录和 36 个 VTK 关联文件。
- [x] T03-P4-L V2 已冻结沟道长度单变量合同：L=8/10/12 um，保持 T02-C 顶栅主扫、底栅 0 V、VDS=0.01 V、31 点网格和提取公式不变；V1 失败输入、报告、CSV、状态和图片已归档。
- [x] T03-P4-L 三个新器件共完成 123 次 DC、93 个正式点、3 个 VTOP=1 V 状态；运行器 16 项、独立持久化证据 14 项全部 PASS，E3 证据已落盘。
- [x] T03-P4-L 观察到 L 增大时开态电流代理和 gm 代理严格下降：4.10629e-5 -> 3.59372e-5 -> 3.19487e-5 A/cm，gm=4.45359e-5 -> 3.93760e-5 -> 3.51205e-5 S/cm。
- [x] T03-P4-L 明确保留理想 1/L 诊断 FAIL：VTH 范围 12.058 mV，I*L spread 14.315%，gm*L spread 15.461%，log I-log L 斜率 -0.61818、R2=0.999517；没有放宽阈值或改写为物理缩放定律。
- [x] T03-P1-BIAS 以 22 项静态合同冻结唯一变量 `VBG=-0.4/-0.2/0/+0.2/+0.4 V`；顶栅主扫、`VDS=0.01 V`、31 点网格、材料、接触、几何、网格及 `Ctop/Cbottom=1` 输入代理保持不变。
- [x] T03-P1-BIAS 五个新器件共完成 217 次 DC、155 个正式点和 5 个 `VTG=0.3 V` 状态；运行器 14 项与独立持久化证据 14 项全部 PASS，E3 证据已落盘。
- [x] T03-P1-BIAS 的 VTH 数值代理随 VBG 从 -0.4 V 增至 +0.4 V 而由 0.600083 V 降至 -0.155482 V；五点 OLS 耦合斜率为 -0.940554 V/V、R2=0.995712，零副栅曲线和提取对 T02-C 复现差异为 0。
- [x] T03-P1-CAP-RATIO 以 20 项静态合同冻结唯一变量 `Ctop/Cbottom=0.5/0.75/1.0/1.5/2.0`；上下介质物理厚度均固定 30 nm，并以 `epsilon_top+epsilon_bottom=13.6` 固定总平行板耦合代理，P4 几何与公共介质变量不变。
- [x] T03-P1-CAP-RATIO 五个新器件共完成 205 次 DC、155 个正式点和 5 个 `VTG=0.3 V` 状态；运行器 16 项和独立持久化证据 13 项全部 PASS，最大端口相对不平衡为 4.84e-10。
- [x] 随有效分配比增大，VTH 代理由 0.368433 V 严格降至 0.209247 V，gm 代理由 2.80673e-5 S/cm 严格升至 4.94347e-5 S/cm；共同偏压状态的电流、中心势和中心电子浓度均严格增加，`Ctop/Cbottom=1` 对 T02-C 的曲线、状态和提取复现差异为 0。
- [x] T03-P1-BIAS 与 T03-P1-CAP-RATIO 共同关闭数值 P1 组；成对介电常数只编码固定总耦合下的差分分配，不是实测 Al2O3 介电常数、物理电容、制造非对称栈或实验校准。完整 T03 后由 P2/P3/P5 依序关闭。
- [x] T03-P2-DIT 已以 22 项静态合同冻结四行 E1 文献来源、bottom 单界面、`Q_it=-q*D_it*(Potential-Psi_neutral)`、`Psi_neutral=0 V` 教学假设和后续正式 `8.43e11/3.07e12/6.02e12 cm^-2 eV^-1` 三点；合同检查本身不运行器件仿真。
- [x] T03-P2-DIT 方程冒烟完成 5 个器件和 17 次 DC，落盘 12095 行节点状态与 195 行界面采样；运行器 14 项、独立持久化复核 15 项全部 PASS，零 `D_it` 节点势差为 0，代表中心 Gauss 相对误差为 `1.49e-15`。
- [x] T03-P2-DIT-FORMAL V2 以零陷阱控制和 `8.43e11/3.07e12/6.02e12 cm^-2 eV^-1` 三个文献约束点完成 4 个独立器件、164 次 DC、124 个正式点和 4 个共同 `VTG=0.3 V` 状态；最大端口相对不平衡为 `8.44e-12`，最终刷新墙钟约 `11.02 s`。
- [x] 正式 V2 合同 21/21、运行器 14/14 和不导入运行器/DEVSIM 的独立 16/16 全部 PASS；零 DIT 的 31 点曲线、中心状态、VTH 和 gm 对 T02-C 复现差异均为 0，24 个 VTK 和两张 PNG 通过哈希/内容复核。
- [x] 随 DIT 增加，VTH 数值代理为 `0.263857/0.283583/0.316118/0.338997 V`，SS 为 `137.594/168.657/231.493/292.966 mV/dec`，gm 为 `3.93760e-5/3.89139e-5/3.80152e-5/3.72531e-5 S/cm`。最低栅压电流代理为 `2.10e-10/1.41e-9/1.09e-8/2.96e-8 A/cm`，受 `Psi_neutral=0 V` 线性化电荷符号影响，不得写成物理 Ioff。
- [x] 两类失败证据已保留：首次在第二个器件发现 DEVSIM mesh 重名；完整 V1 两 decade SS 窗口的 R2 为 `0.95470/0.97082/0.98560/0.99444`，前两点未过 `R2>=0.98`。V2 改为固定一 decade 窗口，不改仿真栈、DIT 点或 R2 门槛。
- [x] P2-DIT 的 E3 正式结果只关闭线性化 bottom-interface 子阶段；它本身不证明 bulk tail/deep traps、能量分布占据、动态捕获-发射、迟滞、实验校准或完整 P2/T03。完整 P2 由后续 bulk 正式 V3 独立门关闭。
- [x] T03-P2-BULK-TRAPS 已冻结 DOI `10.3390/electronics9101652` 的受主型导带指数尾态 NTA 与高斯深态 NGA；两类各取零控制 + 三个文献点，扫描时另一类和双界面 DIT 固定为零，NTD/NGD 延后。
- [x] bulk-trap 合同固定 `epsilon=Ec-E`、准静态占据和 Poisson 体电荷 Jacobian；96 点 Gauss-Legendre 对独立 32768 区间 Simpson 参考的最大相对误差为 `7.93e-7`，30/30 静态检查 PASS，明确 `simulation=NOT_RUN_BY_CONTRACT_CHECK`。
- [x] bulk-trap 方程冒烟完成零控制、`NTA=5e18 cm^-3 eV^-1` 尾态参考和 `NGA=5e16 cm^-3 eV^-1` 深态参考三个器件，共 21 次耦合 DC；7257 行二维节点状态和 6 行积分样本已落盘，运行器 E2 PASS，独立 16 项检查 E3 PASS。
- [x] `config/project.json` 与 `config/experiments.json` 已同步登记 bulk 方程冒烟的完成历史、结果路径和 E2/E3 边界；未改变物理输入或既有仿真证据。
- [x] `T03-P2-BULK-TRAPS-FORMAL` V1 输入合同以 22/22 静态检查冻结 NTA 与 NGA 各自零控制加三个正式点、两个 family 完全隔离、DIT/NTD/NGD 为零、DIT V2 提取方法、失败证据保留、阶段输出路径和独立落盘验收要求。
- [x] 正式 V1 完成 8 个新器件、328 条全部收敛的 DC 记录、248 个 transfer 点、8 个共同状态和 48 个 VTK；最大端口相对不平衡为 `6.01e-9`。最高 NTA 曲线在 `VTG=1.0 V` 仅达 `3.14e-6 A/cm`，未包络不变的 `1e-5 A/cm` VTH 判据；非零陷阱零外偏内部势最大为 `0.157504 V`。运行器因此保持 E0/FAIL，输入、源码、日志、曲线、状态、VTK 和报告均已版本化保留。
- [x] V2 保持全部 NTA/NGA 点、方程和提取阈值不变，将所有器件共同栅压网格扩展为 `-0.5~1.7 V/0.05 V`，并只对精确零陷阱控制施加近零内部电势回归。V2 合同 23/23 PASS、E3、`NOT_RUN_BY_CONTRACT_CHECK`；8 器件/440 DC/360 点仍是计划量，不是仿真结果。
- [x] 正式 V2 随后完成 8 个器件、440 条全部收敛的 DC 记录、360 个 transfer 点、8 个共同状态和 48 个 VTK，墙钟 `28.414 s`，最大端口相对不平衡仍为 `6.01e-9`。最高 NTA 在 1.7 V 达 `1.41901e-5 A/cm`，已包络 VTH 判据。
- [x] V2 最高 NTA 的诊断 VTH 为 `1.4666676 V`，不变的 gm 评价点为 `1.6666676 V`；该点高于 45 点网格的倒数第二点 1.65 V，缺少冻结中心差分所需的上邻点。运行器因此保持 E0/FAIL；标准目录 75 个文件与版本化失败归档 84 个文件均已保留，合计 159 个，没有运行独立检查、没有生成指标结论或报告图片。
- [x] 用户批准采用统一 `VTG=-0.5~1.8 V/0.05 V` 的 V3 恢复方案；原 V2 活动配置和运行器已原样冻结。V3 保持全部密度点、方程、提取方法和验收阈值不变，冻结 8 器件、456 次计划 DC、376 个计划 transfer 点、8 状态和 48 VTK；静态合同 24/24 PASS、E3、`NOT_RUN_BY_CONTRACT_CHECK`。
- [x] V3 合同检查首次因新增 V2 历史曲线被检查器误按 JSON 加载而在断言前退出；失败记录已保留。修正仅将该依赖加入 CSV 加载分支，没有运行 DEVSIM、改变物理输入或放宽门槛。
- [x] 首次 `make check` 因新增边界断言把子串错误写成列表整项匹配而 419/420 PASS；失败报告已保留为 `results/reports/project_check_t03_p2_bulk_formal_boundary_checker_bug_failed.json`。修正只改变检查器匹配方式，不放宽任何合同、数值或物理门槛；归档失败本身已纳入最终总检查。
- [x] 正式 V3 在统一 `VTG=-0.5~1.8 V/0.05 V` 网格完成 8 个隔离器件、456 次全部收敛 DC、376 个 transfer 点、8 个共同状态和 48 个 VTK；墙钟 `36.669 s`，最大端口相对不平衡 `6.01e-9`，运行器 17/17 PASS、E2。
- [x] 不导入运行器或 DEVSIM 的独立检查 16/16 PASS、E3；重算 376 点、8 行提取、两组 T02-C 零控制、8 状态、48 VTK、两张 PNG 和输入/输出哈希，最大节点占据密度、导数和 Poisson 电荷相对误差分别为 `6.69e-16`、`1.17e-15` 和 `5.94e-16`。
- [x] V3 两个零控制在 31 个共同点对 T02-C 的电流、中心势、中心密度、VTH 和 gm 复现差异均为 0；两个独立零控制在 47 点及全部提取量上也完全一致。正式 P2 因此只在冻结准静态、文献约束、未校准教学模型边界内关闭。
- [x] NTA 三点相对零控制的 Delta VTH 为 `0.03729/0.18104/1.20281 V`，SS 代理升至 `432.510 mV/dec`，gm 代理下降；NGA 三点的 Delta VTH 为 `0.00722/0.03407/0.33686 V`，gm 代理下降，但 SS 代理由 `137.594` 轻微降至 `132.874 mV/dec`。后者按预注册语义保留为方向诊断，不作为失败门，也不解释为真实深态机制。
- [x] T03-P3-CONTACT-RESISTANCE V1 以 2 行 E1 TLM 来源冻结 `R_pair*W=0/0.5/4.5 kOhm*um` 三点；0 为精确理想接触回归，两个非零点只借用论文数值大小并按项目教学约定映射为总源漏串联电阻，再各半分到源/漏，不继承论文金属或 Rc 定义。
- [x] P3 合同冻结零点直连理想欧姆接触、非零点通过 DEVSIM circuit node 与两个外部电阻自洽耦合；势垒高度、热发射、隧穿、接触区材料/网格、陷阱、迁移率、几何和温度扫描均关闭。
- [x] V1 实际完成 12 个器件、243 次全部收敛 DC、93 个 transfer 点、63 个 output 点、3 状态和 18 VTK。circuit KCL 最大相对残差 `2.42e-12`、Ohm 定律最大相对残差 `1.21e-12`、压降分配绝对残差为 0；最大非零漏压端口相对不平衡 `3.35e-11`，零漏压最大绝对电流 `1.08e-19 A/cm`。
- [x] V1 把相对端口守恒门也用于 9 个零漏压点，舍入级电流使无意义相对比值达到 `1.67205`，故运行器仅 24/25 PASS 并按合同保留为 E0/FAIL；没有运行独立检查，也没有把其他通过门改写为 P3 PASS。原失败 manifest 的归档同名覆盖缺陷已用补充清单披露并恢复唯一副本，原 manifest 与原始结果均未改写。
- [x] V2 静态恢复合同保持两个阈值、三个接触点、全部器件方程、偏压、提取和 12/243/156/3/18 预算不变，只将相对守恒门限定到 `external VDS>0`、绝对电流门限定到 `external VDS=0`，并改用独立 V2 输出/归档路径。34/34 PASS、E3、`NOT_RUN_BY_CONTRACT_CHECK`；在该合同检查时点 P3 仍未完成。
- [x] P3 首次静态检查因 T02-C 报告字段假设、`Ti` 子串误判和连字符拼写三项检查器错误而 27/30 PASS；失败报告已保留。修正只改检查器断言，不改输入、模型、偏压、提取或验收门槛。
- [x] 正式 V2 按已提交合同唯一运行一次，完成 12 个器件、243 次全部收敛 DC、93 个 transfer 点、63 个 output 点、3 状态、7257 行节点、7680 行沟道单元和 18 VTK；墙钟 `24.735 s`，运行器 25/25 PASS、E2。
- [x] V2 非零漏压最大端口相对不平衡 `3.35344e-11`，零漏压最大绝对电流 `1.08454e-19 A/cm`，circuit KCL/Ohm 最大相对残差为 `2.42178e-12/1.20922e-12`，压降分配残差为 0；最大接触点的高栅电流代理相对理想点下降 `0.161396%`，外部总电阻宽度积代理由 `2780.13345` 增至 `2784.63204 kOhm*um`。
- [x] 不导入运行器或 DEVSIM 的独立检查重算输入/输出哈希、全部 156 点、243 次求解、器件守恒、circuit 闭合、提取、T02-C 回归、3 状态、18 VTK 和两张图，20/20 PASS、E3。V2 只关闭数值 P3，不改写 V1 失败，也不建立项目 TLM、Ti/Ni、势垒/注入或实验校准证据。
- [x] T03-P5-TEMPERATURE 正式输入合同冻结 `T=250/300/350 K` 和 `V_t=0.021543333155/0.025851999786/0.030160666417 V`；300 K 点精确继承 T01/T02-C 的 `0.025851999786 V` 控制。
- [x] P5 只允许 `V_t` 随温度变化；迁移率、有效 DOS、带隙/亲和势、介电常数、源漏接触密度、陷阱、几何和偏压全部冻结。VTH/gm/SS 与高低栅压电流只允许称为数值代理，方向假设只报告、不判门。
- [x] P5 合同预注册 3 个新器件、123 次计划 DC、93 个计划 transfer 点、3 个计划 `VTG=1 V` 状态、18 个计划 VTK、300 K 对 T02-C 回归、失败拒绝覆盖和独立落盘复核；23/23 静态检查 PASS、E3、`NOT_RUN_BY_CONTRACT_CHECK`，合同检查时未运行 DEVSIM。
- [x] P5 按已提交合同唯一运行一次，3 个新器件完成 123 次全部收敛 DC、93 个 transfer 点、3 个 `VTG=1 V` 状态、7257 行节点、7680 行沟道单元和 18 VTK；墙钟 `9.127 s`，运行器 14/14 PASS、E2。
- [x] P5 独立检查不导入运行器或 DEVSIM，重算曲线、提取、300 K T02-C 回归、状态、18 VTK、两张图和哈希，15/15 PASS、E3。最大端口相对不平衡 `4.37301e-10`，300 K 曲线/状态/VTH/gm 差异均为 0。
- [x] 250/300/350 K 的 VTH 代理为 `0.245409/0.263857/0.281977 V`，SS 代理为 `117.138/137.594/157.796 mV/dec`，gm 代理为 `3.98472e-5/3.93760e-5/3.88128e-5 S/cm`；这些只是在固定迁移率和其余温度项缺省下的 `V_t-only` 数值响应。
- [x] P5 收口后的首次 `make check` 因旧 P3 断言仍要求当前下一门为 P5 而 539/540 PASS；原始失败报告已保留为 `results/reports/project_check_t03_p5_p3_next_gate_stale_failed.json`。修正只让 P3 校验历史快照、把当前下一门归最新 P5 门负责，不改物理输入、结果或阈值；最终总检查 542/542 PASS，报告结构检查为 12 章/5 附录/22 图 PASS。
- [x] M00 数据注册表固定 13 个表的路径、SHA-256、行数、上游运行报告和独立检查；只有 T01-D-B/C、T02-C、T03-P4 和 T03-P3 理想接触 output 的显式子集允许进入正式 train/holdout。加密网格、上下栅互易、回程和重复零控制只作复现审计，P1/P3/P5 改变只作挑战，P2 陷阱变体与外部基线禁止参与拟合。
- [x] M00 预注册以整条件分割 9 条 train/163 点和 4 条 holdout/70 点，将 7 个 `VDS=0` 点作为不变量、7 个重复 `VDS=0.01 V` output 点作为跨阶段审计而不重复加权。冻结平滑电荷差教学核、11 个系数与边界、确定性 `least_squares`、每曲线等权线性/对数误差、VTH/gm/单调/零偏压门和局部有效域。
- [x] M00 合同首次静态检查因把 T01/T02 实际机器状态 `complete_e2`/`bidirectional_verified` 误写为通用 `verified` 而 24/25 PASS；原 FAIL 报告已保留。只修正依赖状态字面值后 25/25 PASS、E3，`fit/TCAD/SPICE/circuit=NOT_RUN_BY_CONTRACT_CHECK`；数据、划分、方程、参数边界和验收阈值均未改变。
- [x] M00 合同已纳入项目总检查和报告证据矩阵；`make check` 551 项 PASS，`make report-check` 以 12 章/5 附录/15 占位/22 图 PASS，JSON/CSV/XHTML 和 Python 语法检查均 PASS。
- [x] M00 正式执行链已实现：运行器只把 9 条训练曲线送入一次确定性 `least_squares`，优化终止后才加载 4 条 holdout；输出拒绝覆盖并保留失败所需快照、行清单、优化日志、预测和双尺度残差。独立检查器只用标准库重建冻结行、参考核、误差、VTH/gm、哈希和候选边界，不导入运行器、NumPy 或 SciPy。`make m00-compact-model-self-test`、静态合同 25/25 与当前项目总检查 551 项 PASS；这些只是执行链预检，不是正式拟合结果。
- [x] M00 R01 唯一正式运行完成训练后再评分 holdout：优化器 18 次函数评价正常终止，train aggregate linear/log 为 `0.0799203/0.0832202`，holdout 为 `0.123434/0.148789`，均通过；两条 holdout transfer 的 gm 相对误差为 `0.374514/0.512384`，后者超过冻结 `0.50`。运行器 21/24、E0/FAIL；另外两项 FAIL 只是禁止生成候选及候选产物不完整的派生结果。
- [x] R01 的输入快照、247 行选择清单、优化日志、预测/残差、13 行曲线指标、11 行参数、有效域、两张图和失败报告均保留。没有执行 PASS-only 独立检查，没有生成/运行 ngspice 或 AIM-Spice 候选，也没有运行 TCAD 或电路；任何系数只作失败诊断。
- [x] R01 失败收口检查通过：`make check` 566 项，`make report-check` 为 12 章/5 附录/15 占位/24 图；Python、JSON/CSV/XHTML 和差异格式检查均通过。两张失败图已人工核对为非空且可读；这些检查只证明证据完整，不改变 E0/FAIL。
- [x] R02 结构恢复合同以提交前 split 做可识别性审计：训练侧 8 条 `L=10 um` 曲线、1 条 `L=8 um` 曲线，却有 `length_exponent` 与 `length_vth_slope_v` 两个自由度。R02 固定 `Lref/L` 指数为 `1.0`、移除前者，只保留后者并以零初值训练；10 个有界参数、独立输出路径和 R01 不可改写边界均已冻结。
- [x] R02 保持 13 表字节/哈希、9/163 train、4/70 holdout、7 个零漏压点、7 个低漏压审计点、底值/权重/优化器、全部误差与 `0.50` gm 门不变。纯静态检查 27/27 PASS、E3，明确 `fit/TCAD/SPICE/circuit=NOT_RUN_BY_CONTRACT_CHECK`；固定反长度因子只是教学正则化，不是物理缩放验证。
- [x] R02 合同收口检查通过：`make check` 571 项，`make report-check` 为 12 章/5 附录/15 占位/24 图；Python、JSON/CSV/XHTML 与差异格式检查通过。这些检查不提升尚未运行的 R02 拟合证据。
- [x] R02 版本化执行链已实现：runner 只把 9 条 train/163 点送入 10 参数确定性优化，优化日志落盘后才加载 4 条 holdout/70 点；所有 R02 输出拒绝覆盖，固定长度因子直接为 `Lref/L` 且不存在自由 `length_exponent`。独立检查器不导入 runner、NumPy、SciPy、DEVSIM 或 subprocess，只用标准库独立重建 247 行选择、固定核、残差、指标、VTH/gm、产物哈希和候选边界，其报告也拒绝覆盖。
- [x] `make m00-compact-model-r02-self-test` PASS，Python/JSON 语法与 15 个正式输出缺失检查 PASS，`make check` 575/575 PASS，`make report-check` 以 12 章/5 附录/15 个允许占位/24 图 PASS。该里程碑是执行链 E2 合成自测，不是正式拟合、holdout 验证、M00 PASS、SPICE 或电路证据。
- [x] R02 唯一正式运行按已推送提交 `56a4215` 绑定，训练只使用 9 条整条件曲线/163 个计分点，优化结束并落盘日志后才加载 4 条 holdout/70 点；runner 24/24 PASS、E2。train aggregate linear/log 为 `0.0830935/0.0838732` decade，holdout 为 `0.109299/0.142615` decade；两条 holdout gm 相对误差为 `0.363249/0.419248`，均通过不变的 `0.50` 门。
- [x] R02 独立标准库检查器在 runner PASS 后唯一执行，重算 247 行选择、固定核、13 条曲线指标、VTH/gm、10 个参数、两张图、候选状态和哈希，20/20 PASS、E3。12 个 runner 产物、预测/残差表、参数表、IGZO-only 行为候选及未执行 Level-15 候选均已落盘；没有运行 ngspice、AIM-Spice、TCAD 或电路。
- [x] R02 结果边界已收口：`lambda_per_v` 和 `log_gmin` 严格在界内但接近下界，合同没有预注册边界裕量门；它们不是物理参数。R01 失败不被覆盖，M00 只对冻结教学模型的局部数值域关闭，并允许建立 M01 合同，不允许直接进入 M01 执行或下游。
- [x] M01 revision-1 合同检查因把 247 个持久化行误称为全部 scored（实际为 233 scored + 14 审计）而 28/32 FAIL；revision-2 因历史失败路径被误计入未来输出而 31/32 FAIL。两份报告均原样保留，修正只改变合同行角色、历史输出过滤和大小写断言，不运行模拟器、不改变 R02 输入。
- [x] M01 revision-3 静态合同 32/32 PASS、E3：冻结 R02 247 行、13 曲线、163/70 scored split、7+7 审计、同一几何/偏压/温度/端口映射、ngspice 行为候选、AIM-Spice Level 15 候选、工具指纹、语法/预检、指标差异、失败保留和 no-circuit 预算。合同检查只生成 `results/reports/m01_simulator_cross_check_contract_v3.json`，没有 ngspice/AIM-Spice 原始输出或电路结果。
- [x] M01 R01 工具/来源预检在已推送执行链提交 `a6386d2` 后唯一运行一次，11/13、E0/FAIL。ngspice 三项门全部通过；AIM-Spice 可执行文件指纹通过，但授权来源可审计和文档化 batch/CLI 两项失败。报告与 827 字节原始日志均落盘并哈希；AIM-Spice 未启动，唯一子进程没有网表参数，10 个声明的数值输出全部不存在。此前披露前的帮助/版本探索同样不进入正式证据。
- [x] M01 开源恢复合同 30/30、E3：绑定 revision-3 合同与 R01 失败哈希，冻结 ngspice + 纯源码 GPL Xyce 7.10.0、同一 IGZO 行为候选、247 行目标、批处理模板、工具/许可证自测、独立输出和失败保留。源码审阅只构成语法能力证据；Xyce 尚未构建或运行。第一次 28/30 干跑报告 `results/reports/m01_open_source_recovery_contract_r01.json` 原样保留，最终报告为 `results/reports/m01_open_source_recovery_contract_r01_e3.json`。
- [x] M01 Xyce 构建/工具预检合同 25/25、E3：实现排他构建 runner 与标准库独立检查器，固定四个官方源码/工具包的实际哈希、串行两任务、MPI/Fortran 关闭、版本/许可证指纹、标量 B-source 自测和随后 parser-only `-syntax`。旧恢复合同的 Xyce 哈希转录差异明确登记且旧报告不改写；合同检查没有启动 Xyce/ngspice 或创建任何网表/数值输出。

## 后续领域实现

- [x] T01 单栅 IGZO 漂移扩散（教学参数 E2 数值门完成；不等同实验标定或物理参数验证）。
- [x] T02 双栅电流与阈值耦合（冻结教学模型数值门完成；不等同实验标定、物理电容比、迟滞或紧凑模型验证）。
- [x] T03 五组器件参数分析（P1/P2/P3/P4/P5 DONE；P2/P3 历史 FAIL 保留；各完成组均有独立 E3 落盘检查）。
- [x] M00/M01 紧凑模型拟合与双轨对照（两阶段均只在冻结教学数值域内 `DONE_WITH_LIMITATION`。M00 R01、M01 全部历史失败和 R02 路线分歧保留；R03 42/30/24 E3/E2/E3 独立复现 portable 候选机器精度级路线一致。该关闭不等于物理参数、实验校准、原生 Level 61 或电路验证）。
- [ ] C00/C01 单极性标准单元。
- [ ] C02/C03 环振和全加器。
- [ ] L00/V00/V01 PCell、GDS、DRC、几何 LVS。
- [ ] PEX0 和 FE0 可选扩展。
- [ ] PPT 和最终报告正文。

## 不属于当前结果

- 旧范围反相器、环振和全加器数值。
- 条件不完整的学长 VTC/IGZO 表所推导的模型精度。
- 只有静电方程的漏电流、SS、迁移率或接触结论。
- T01-A 输入合同不是 `Id-Vg`、`Id-Vd` 或迁移率提取结果。
- T01-B 仅是低偏压收敛、端口电流和基础网格烟雾结果，不是完整 `Id-Vg`、完整 `Id-Vd`、VTH/迁移率提取、实验标定或双栅电流预测。
- T01-C 的低 VDS `Id-Vg` 只证明教学方程下的数值续算和单调栅控；约 17 decade 的数值电流跨度不是物理 `Ion/Ioff`。其高正栅压网格警告已由 T01-D-A 在限定目标点关闭，但 T01-C 自身仍不是完整网格或参数提取结果。
- T01-D-A 只证明 VDS=0.01 V、VGS=0.5/1.0 V 目标点在冻结教学模型下的数值网格收敛，不证明完整 Id-Vd、实验精度、VTH/SS/迁移率、物理 Ion/Ioff 或双栅电流。
- T01-D-B 只覆盖 VDS=0/0.01/0.05/0.1/0.2 V 的离散教学模型点；连线不证明连续输出特性、真实饱和机理或沟道长度调制，也不证明实验精度、参数提取、完整 T01 或双栅电流。
- T01-D-C 关闭的是冻结教学模型的数值阶段门，不是实验验证门。0.217535 V、59.6081 mV/dec 和 19.1739 cm2/(V*s) 必须写成配置方法下的数值代理；约 17.42 decade 是数值电流跨度，不是物理 Ion/Ioff，也没有给出不确定度或跨条件预测精度。
- T02-A 只证明“移除顶栈”极限返回 T01，以及对称教学顶栈在全零偏压下能建立移动电子平衡态。它没有运行非零 VTG，不得声称双栅电流趋势、Delta VTH、gm、耦合斜率或完整 T02 已验证。
- T02-B 只覆盖固定 `VDS=0.01 V`、`VBG=0 V` 时的四点单向非负 VTG 族。端点 9.68 倍电流增加只是冻结教学模型的数值响应，不是物理 Ion/Ioff、实验精度、Delta VTH、gm、电容比或耦合斜率。
- T02-C 关闭的是对称 30 nm Al2O3、常数教学迁移率、理想欧姆接触、无陷阱/复合/铁电的冻结模型数值门。0.263857 V、Delta VTH、gm 和 -0.93535 V/V 不得写成实测或校准参数；正反扫重合只说明无迟滞方程时的数值路径无关，不证明真实器件无迟滞。
- T03-P1-BIAS 只改变固定底栅偏压。0.600083 至 -0.155482 V 的 VTH 代理和 -0.940554 V/V 的斜率不得称为实测阈值、物理电容比、实验耦合系数或电路可用参数；它单独不完成 P1。
- T03-P1-CAP-RATIO 只改变固定总耦合下的有效分配比。VTH/gm/状态的五点单调趋势不得称为实测电容比、实测 Al2O3 介电常数、真实非对称介质栈、物理 Ion 或实验模型精度；它与 BIAS 共同完成数值 P1，但不完成 T03。
- T03-P2-DIT 正式扫描只验证文献范围约束的准静态、线性化、bottom 单界面教学方程。VTH/SS/gm 和 `VTG=-0.5 V` 电流均是数值代理，不是实测 DIT、物理 Ioff/Ion、能量分布陷阱、实验标定或完整 P2。
- T03-P2-BULK-TRAPS 正式 V1 的 8/328/248 和 V2 的 8/440/360 都是已计算的 E0/FAIL 证据，不是阶段 PASS。V3 的 8/456/376 是已通过运行器和独立检查的正式数值证据，能够关闭冻结教学模型边界内的 P2，但不是测量/拟合 DOS、物理 SS/VTH/Ion/Ioff、动态捕获-发射、实验校准或完整 T03 证据。
- T03-P3 V1 的 12 器件、243 DC、156 点和 3 状态是已完成但 E0/FAIL 的计算证据，不是 P3 PASS；V2 的相同规模已由 25/25 运行器和 20/20 独立检查验证，只能关闭冻结教学模型内的 P3。V1 失败不能因 V2 通过而改标；V2 也不证明项目 TLM 提取、Ti/Ni 金属比较、势垒/注入、物理 Ion 或接触参数校准。
- T03-P5 的 3/123/93 正式运行和 15/15 独立检查只证明冻结教学模型的三点 `V_t-only` 数值响应。250/300/350 K 不是实测工作范围，不能据此声称 IGZO 迁移率温度律、激活能、物理 SS/VTH/漏电、工作温区、自热、可靠性或实验校准。
- M00 R01 的聚合误差通过不能覆盖 `L=12 um` holdout gm 门失败。其 11 个系数、预测和图是已计算但未接受的 E0/FAIL 诊断，不是 M00 模型、实验标定、外部独立验证、物理参数提取、双仿真器验证或电路可用性。
- M00 R02 的 27/27 静态合同、24/24 runner 和 20/20 独立复核只证明结构正则化教学代理对冻结项目数值曲线的局部一致性；`Lref/L` 固定指数、10 个系数及近下界诊断不能写成物理缩放规律、实验拟合、外部验证、原生 Level 61 或电路模型。候选文件尚未执行。
- M01 R01 的 11/13 只证明 ngspice 版本探针通过且原 AIM-Spice 路线不满足来源/批处理门。它不是 AIM-Spice 或 ngspice 数值失败、Level 15 执行、IGZO 曲线或第二路线通过；开源候选工具在独立合同、提交和正式运行前也不得写成 M01 结果。
- M01 根因 R01 当前是不可改写的 38/40 E0/FAIL；R02 探针/独立复核为 30/30 E2 与 22/22 E3，只覆盖预注册最小点。R03 42/30/24 三门已经 E3/E2/E3 完成，机器精度级路线一致已由独立落盘重算复现；它仍不能写成方程身份、物理参数、实验校准或自动等同正式 M01 收口。
- 尚未生成的有源负载网表、标准单元版图和 LVS 报告。

## 当前阻塞

1. 主 IGZO 原始 Id-Vg/Id-Vd、批次和完整条件尚待老师确认；这阻止定量拟合，但不阻止继续教学参数敏感性。
2. 双栅实测数据缺失时只能做文献约束敏感性。
3. 需要老师确认 DEVSIM、单极性有源负载逻辑和 KLayout 几何 LVS 的接受度。
4. 复杂电路跨线层和顶栅实际工艺尚未明确。
5. M00 R01 的 `L=12 um` holdout gm 相对误差 `0.512384` 超过冻结 `0.50`，该失败永久保留；M01 全部工具/合同历史失败和 R02 路线分歧同样保留，未授权 AIM-Spice 永久排除。M01 的受限关闭只允许 C00 合同建立，不能替代正式敏感性、物理校准或电路验证。

## 下一步

提交并推送 C00 R01 46/48 静态失败后，建立独立 C00 R02 合同，只将禁止范围扫描改为 ASCII 标识符整词匹配并绑定 R01 失败；R02 静态 PASS 状态另行提交前不生成或运行正式电路网表。C01/C02/C03、版图、PEX 和 HZO 保持关闭。
