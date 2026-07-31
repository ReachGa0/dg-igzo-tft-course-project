# AI_LOG

## 记录规则

每次 AI 对项目做实质修改后，在文件顶部追加一条记录。每条必须包含：

- 日期和 AI/工具。
- 用户目标。
- 读取的关键输入。
- 修改的文件。
- 执行的验证命令和结果。
- 新决策、假设和未解决问题。
- 下一步建议。

不允许只写“已优化”、“已完成”而不列出可验证产物。

---

## 2026-07-31 | Codex GPT-5 | 完成 T02-B 最小正向顶栅偏压族

### 用户目标

按阶段门继续 T02，只完成下一个小阶段：在 T02-A 已冻结的启用顶栈拓扑上运行最小非零顶栅偏压族，通过后更新状态、分章报告、Git 并推送，不提前展开 T02-C、T03、SPICE 或版图。

### 读取的关键输入

- `AGENTS.md`、README、AI_CONTEXT、ARCHITECTURE、STATUS、PROJECT_PLAN、DECISIONS、AI_LOG、`config/project.json` 和 `config/experiments.json`。
- T01 冻结教学基线、T01-D-A `interface_4x` 网格合同、T02-A 顶栈合同、回归报告和独立检查报告。
- T02-A 已验证的启用拓扑初始化、网格、方程、接触、偏压和状态导出函数。

### 本次修改

- 新增 `config/tcad_t02_b_minimal_bias.json`，冻结 `VDS=0.01 V`、`VBG=0 V`、`VTG=0/0.1/0.2/0.3 V`、9 次 DC 路径、端点状态和结论边界。
- 新增 `scripts/check_t02_b_contract.py` 与 `make t02-b-contract-check`；17 项静态检查通过，该命令不运行器件仿真。
- 新增 `tcad/run_t02_dual_gate_minimal_bias.py` 与 `make t02-b-minimal`；复用 T02-A 已验证的启用拓扑，保存偏压表、输入快照、求解日志、2 份节点状态、12 个 VTK、JSON 报告和三面板图。
- 新增 `scripts/check_t02_b_minimal_bias.py` 与 `make t02-b-minimal-check`；独立读取落盘 CSV/JSON/VTK，不导入运行器，复算 14 项证据。
- 更新 `scripts/check_project.py`、`config/experiments.json`、状态/计划/架构/上下文、ADR-018、TCAD 文档、报告第 5/7 章和证据矩阵。

### 实际结果

- 9 次 DC 全部收敛；启用拓扑为 2419 个含界面重复计数的活动节点、4480 个三角形、3 个区域、4 个接触和 2 个介质界面。
- VTG=0/0.1/0.2/0.3 V 的漏端电流为 `1.1931e-6/3.7004e-6/7.4130e-6/1.1549e-5 A/cm`，端点比为 `9.6802`。
- 沟道中心电势增加 `0.0552122 V`，中心电子浓度端点比为 `8.3756`；三个观察量均随 VTG 严格增加。
- 最大端口相对不平衡为 `1.405e-14`；零偏压平衡态的最大端口电流和最大节点电势均为 0。

### 验证

```text
make t02-b-contract-check
T02_B_CONTRACT_PASS checks=17 simulation=NOT_RUN_BY_CONTRACT_CHECK

make t02-b-minimal
T02_B_MINIMAL_PASS points=4 dc_solves=9

make t02-b-minimal-check
T02_B_MINIMAL_CHECK_PASS checks=14

make check
PROJECT_CHECK_PASS checks=265

make report-check
REPORT_STRUCTURE_PASS chapters=12 appendices=5 placeholders=19 images=4
```

### 决策和边界

- T02-B 只允许声称冻结教学模型在四个单向非负顶栅点上具有正向、数值可检出的电流和内部状态响应。
- 9.6802 倍电流增加不是物理 Ion/Ioff；未验证负偏压、回程扫描、底栅族、Delta VTH、gm、电容比、耦合斜率、实验精度或完整 T02。
- 只打开 T02-C 合同；T02-C 通过前不启动 T03、SPICE、KLayout 或大批量扫描。

### 下一步

先冻结 T02-C 双向偏压合同：定义固定顶栅/扫底栅和固定底栅/扫顶栅的最小网格，明确负偏压与回程路径、Delta VTH/gm 提取、代表状态和笔记本运行上限，合同通过后再分块求解。

---

## 2026-07-31 | Codex GPT-5 | 完成 T02-A 顶栅输入合同与 T01 极限回归

### 用户目标

在完整 T01 数值门关闭后继续下一阶段，但严格先冻结双栅输入合同并验证“关闭顶栅耦合返回 T01”，不启动大批量双栅扫描、T03、SPICE 或版图。

### 读取的关键输入

- `AGENTS.md`、README、AI_CONTEXT、ARCHITECTURE、STATUS、PROJECT_PLAN、DECISIONS、AI_LOG、`config/project.json`、`config/experiments.json`。
- `config/tcad_baseline.json` 的 T00 对称双栅静电结构。
- `config/tcad_t01_baseline.json`、T01-D-A 网格合同、T01-D-C 报告和独立 17 项检查报告。
- T01 DEVSIM 核心运行器的网格、方程、接触、求解和状态导出函数。

### 本次修改

- 新增 `config/tcad_t02_a_dual_gate_contract.json`，冻结 30 nm Al2O3 教学顶介质、理想顶栅 Dirichlet 边界、对称界面加密、偏压顺序、回归容差和证据边界。
- 新增 `scripts/check_t02_a_contract.py` 与 `make t02-a-contract-check`；合同 16 项检查通过。第一次检查正确拒绝了不在 T01-D-C 冻结参考网格中的 `VBG=0.75 V`，随后改为参考网格已有的 `0.7 V`，没有放宽容差。
- 新增 `tcad/run_t02_dual_gate_limit_regression.py` 与 `make t02-a-regression`。禁用模式移除整个顶栈并复用 exact T01 `interface_4x` 域；启用模式加入顶介质/顶栅并只跑全零偏压平衡。
- 新增 `scripts/check_t02_a_limit_regression.py` 与 `make t02-a-regression-check`；独立读取 CSV、JSON、节点状态、VTK 和输入哈希，不导入运行器。
- 共享 CSV 写入器显式固定 `lineterminator="\n"`，与 `.gitattributes` 的 `*.csv eol=lf` 一致，保证状态清单的 SHA-256 在提交与干净检出后不变。
- 更新 `scripts/check_project.py`、`config/experiments.json`、状态/计划/架构/上下文、ADR-017、TCAD 文档、报告第 5/7 章和证据矩阵。

### 实际结果

- T02-A 共 14 次 DC（禁用回归 12 次、启用零偏压 2 次）全部收敛。
- 禁用顶栈的 7 个 `VBG=0/0.1/0.2/0.3/0.5/0.7/1.0 V` 点对 T01-D-C 的最大电流相对差为 `7.132e-15`，中心电势差为 `4.163e-17 V`，中心电子浓度相对差为 `2.207e-16`；最大端口相对不平衡为 `6.098e-14`。
- 禁用拓扑为 1394 节点/2560 三角形；启用拓扑为 2419 节点/4480 三角形、3 个活动区域、2 个介质接口和 4 个接触。
- 启用顶栈全零偏压状态的最大端口电流和最大结点电势均为 `0`，保存 2419 行节点 CSV 和 6 个 VTK 关联文件。

### 验证

```text
make t02-a-contract-check
T02_A_CONTRACT_PASS checks=16 simulation=NOT_RUN_BY_CONTRACT_CHECK

make t02-a-regression
T02_A_LIMIT_REGRESSION_PASS disabled_points=7 dc_solves=14

make t02-a-regression-check
T02_A_LIMIT_REGRESSION_CHECK_PASS checks=14

make check
PROJECT_CHECK_PASS checks=248

make report-check
REPORT_STRUCTURE_PASS chapters=12 appendices=5 placeholders=19 images=3
```

验证过程中两个阶段门曾正确触发，且已按证据规则关闭：

- 第一次独立回归检查拒绝了修改 `config/project.json` 后的旧输入快照哈希；重跑 14 次 T02-A DC 后刷新快照，独立 14 项复算恢复 PASS。
- 第一次 `make check` 发现总检查集成代码把运行器检查数误写为 9，而报告实际含 10 项 PASS；仅修正期望数为 10，未改阈值或仿真数据，复查 248 项全部 PASS。
- 首次暂存时 Git 指出新 CSV 的 CRLF 将按属性转为 LF，这会使未提交工作区哈希与干净检出字节不同；修正生成端换行符后重跑 T02-A 及独立验收，没有人工改写哈希。

### 决策和边界

- `VTG=0 V` 不再被称为“关闭顶栅”；只有移除整个顶介质/顶栅域并恢复 T01 自然顶边界才是禁用极限。
- 对称 30 nm Al2O3 顶栅是 T00 继承的教学扩展，不是已制造单底栅工艺的实测层。
- T02-A 只打开 T02-B 最小非零顶栅偏压族；未验证非零双栅电流、Delta VTH、gm、耦合斜率、实验标定或完整 T02。

### 下一步

在冻结合同上只运行 T02-B 的一个最小非零顶栅偏压族，固定 VDS、底栅、几何、陷阱、接触和温度，先检查端口守恒、方向和内部状态，再决定是否进入双向曲线族。

---

## 2026-07-31 | Codex GPT-5 | 完成 T01-D-C 状态、受限数值代理与完整 T01 数值门

### 用户目标

按阶段门继续 T01 的最后一个小阶段：补齐关态/目标附近/开态内部状态，在普通笔记本可运行的二维教学模型边界内做可审计提取，独立验证后更新状态、分章报告、Git 并推送；不提前进入 T02、SPICE 或版图。

### 读取的关键输入

- `AGENTS.md`、全部权威状态/计划/决策文件、T01 验收标准和二维 TCAD 路线。
- `config/tcad_t01_baseline.json` 的冻结单栅几何、材料、方程、接触、求解器和偏压边界。
- T01-A 合同、T01-D-A 网格配置/PASS 报告、T01-D-B 配置/PASS 报告及其输入哈希。
- DEVSIM 2.10.0 本地 API 与示例；探针确认 `element_from_edge_model` 对每个三角形返回三个单元节点矢量值。

### 本次修改

- 新增 `config/tcad_t01_d_extraction.json`、`tcad/run_t01_single_gate_extraction.py`、`scripts/check_t01_d_extraction.py` 与 `make t01-d-extract`/`make t01-d-extract-check`。
- 在 `interface_4x/interface_8x` 上固定同一 VDS=0.01 V、51 点 VGS 网格；每档从新建器件的零偏压 Poisson/耦合平衡开始，重放低 VDS 阶梯、负栅压预处理，再从 -1 V 向 1 V 续算。
- 固定三种数值代理方法：`10 nA*(W/L)=60 nA` 恒流 VTH 对数插值、`1e-13~1e-8 A/cm` 窗口 SS 回归、30 nm 物理 Al2O3 电容与 VGS=0.475/0.525 V 中心差分场效应迁移率。PASS 不依赖代理值接近课程目标或常数输运迁移率。
- 在 VGS=-0.5/0.2/1.0 V 保存节点电势、沟道电子浓度、三角形三个单元节点的 `Jx/Jy` 原值、单元中心平均矢量、VTK 和状态摘要；明确局部 A/cm2 与二维端口 A/cm 的区别。
- 更新状态、计划、架构、ADR、实验矩阵、TCAD 说明、验收/汇报文档、报告第 5/7 章、证据矩阵和总项目检查规则。

### 实际结果

- 两档各 51 个正式点，共 120 次 DC、102 个正式点全部收敛；最大源漏相对不平衡为 `6.764e-8`，两档漏端电流均随 VGS 单调增加。
- interface_4x 数值代理为 VTH=`0.217535 V`、SS=`59.6081 mV/dec`、场效应迁移率=`19.1739 cm2/(V*s)`；interface_8x 对应为 `0.217552 V`、`59.6081 mV/dec`、`19.1688 cm2/(V*s)`。
- 4x/8x 的 VTH 差为 `0.017 mV`，SS 相对差 `2.49e-9`，迁移率相对差 `0.0265%`；T01-D-B 四个低漏压锚点最大电流回归差 `5.89e-15`。
- 三状态共写出 3 份节点 CSV、3 份各含 1600 个三角形的电流密度 CSV 和 15 个 VTK 关联文件；状态端口电流与中心电子浓度从关态代理到开态代理严格增加。

### 验证

```text
make t01-d-extract
T01_D_EXTRACTION_PASS meshes=2 bias_points=102 states=3

make t01-d-extract-check
T01_D_EXTRACTION_CHECK_PASS checks=17

make check
PROJECT_CHECK_PASS checks=232

make report-check
REPORT_STRUCTURE_PASS chapters=12 appendices=5 placeholders=19 images=3

图像人工检查
PASS：提取图和三状态图非空，坐标/图例/色标无重叠，三种状态与 4x/8x 曲线可辨认
```

### 决策和边界

- T01-D-C 形成 E2 教学参数证据并关闭冻结模型的完整 T01 数值阶段门，只允许进入 T02 的最小双栅移动电荷基线。
- VTH、SS、gm、迁移率和约 `17.42 decade` 电流跨度必须称为数值代理；没有实验标定、置信区间、物理 Ion/Ioff 或紧凑模型预测精度。
- 连续 Id-Vd、真实饱和机理、陷阱、非理想接触、温度、双栅电流、SPICE 和版图均不属于本阶段结果。

### 下一步

进入 T02 前先冻结顶栅/顶介质结构、上下栅边界、偏压路径和“关闭顶栅耦合返回 T01”的回归门；只做一个最小双栅移动电荷案例，通过后再扩展偏压族。

---

## 2026-07-31 | Codex GPT-5 | 完成 T01-D-B 单栅离散 Id-Vd 曲线族

### 用户目标

按阶段门继续 T01，在 T01-D-A 通过的界面网格口径上完成下一小阶段：运行冻结的多 VGS Id-Vd 点，完成收敛、守恒、趋势、网格复核和报告闭环；通过后提交并推送，不提前启动 T01-D-C、T02、SPICE 或版图。

### 读取的关键输入

- `AGENTS.md`、`STATUS.md`、`PROJECT_PLAN.md`、`ARCHITECTURE.md`、`DECISIONS.md`、实验矩阵和 T01 技术路线。
- `config/tcad_t01_baseline.json` 的 T01-A Stage 3 正式网格：VGS=0/0.3/0.5/1.0 V，VDS=0/0.01/0.05/0.1/0.2 V。
- T01-A 合同与 T01-D-A 配置/PASS 报告；每次正式运行锁定这些输入的 SHA-256。

### 本次修改

- 新增 `config/tcad_t01_d_idvd.json`、`tcad/run_t01_single_gate_idvd.py`、`scripts/check_t01_d_idvd.py` 与 `make t01-d-idvd`/`make t01-d-idvd-check`。
- 以 `interface_4x` 运行 4 条正式曲线，以 `interface_8x` 只复核 VGS=0.5/1.0 V；每条曲线均新建器件，从零偏压 Poisson/耦合平衡态开始，在 VDS=0 分步升 VGS，再逐点升 VDS。
- 保存输入快照、65 条完整 DC 求解记录、30 点端口表、6 条曲线指标、2 档网格摘要、10 点网格对比、4 个 T01-D-A 回归锚点、机器报告、独立验收报告和报告用 PNG。
- 将 T01-D-B 接入总项目检查、状态、计划、架构、ADR、实验矩阵、TCAD 说明、验收标准、汇报稿、报告第 5/7 章和证据矩阵。

### 实际结果与失败记录

- 首次运行的 65 次 DEVSIM 求解全部完成，但结果整理代码对长度天然相差 1 的相邻点数组使用严格 `zip`，在分段斜率计算处报错；修正只涉及后处理数组配对，随后完整重跑。
- 第二次运行生成 30 点后，阶段门因把 VDS=0 的 `10^-19 A/cm` 舍入残差代入相对守恒比值而正确返回 FAIL，最大无意义比值约 1.27。合同改为 VDS=0 使用 `1e-16 A/cm` 绝对端口电流门，只有非零 VDS 使用 `1e-5` 相对守恒门；没有改变仿真输入或数值阈值。
- 第三次完整运行 PASS：6 条独立曲线、65 次 DC、30 个正式点全部收敛；VDS=0 最大绝对端口电流 3.38e-19 A/cm，非零 VDS 最大源漏相对不平衡 7.28e-14。
- 所有采样曲线随 VDS 单调不减，正式网格在相同非零 VDS 下随 VGS 有序；高栅压 4x/8x 最大电流差 0.01639%、最大中心势差 0.03289 mV，T01-D-A 锚点最大电流回归差 1.50e-14。

### 验证

```text
make t01-d-idvd
T01_D_IDVD_PASS curves=6 bias_points=30

make t01-d-idvd-check
T01_D_IDVD_CHECK_PASS checks=16

make check
PROJECT_CHECK_PASS checks=213

make report-check
REPORT_STRUCTURE_PASS chapters=12 appendices=5 placeholders=19 images=1

图像人工检查
PASS：PNG 非空，4 条正式曲线和 2 条复核曲线可辨认，无坐标或图例遮挡
```

### 决策和边界

- T01-D-B 形成 E2 教学参数离散 Id-Vd 证据，只证明冻结的 30 个点通过收敛、守恒、单调趋势和选定网格复核。
- 图中点间连线只用于辨认采样趋势，不证明连续输出行为、真实饱和机理或沟道长度调制。
- 本阶段不包含状态图集合、VTH/SS/迁移率验证、物理 Ion/Ioff、实验精度、双栅、紧凑模型、电路或版图结论。

### 下一步

进入 T01-D-C：沿用 `interface_4x` 正式网格和已验证偏压口径，补齐关态/中间态/开态状态图，限定可提取与不可提取指标，并关闭完整 T01 阶段门；此前不启动 T02 或其他领域工作。

---

## 2026-07-31 | Codex GPT-5 | 完成 T01-D-A 单栅界面法向网格收敛

### 用户目标

按阶段门继续 T01，在不启动完整 Id-Vd、T02、SPICE 或版图工作的前提下，先解决 T01-C 暴露的高正栅压绝对电流网格敏感性；通过后更新状态、报告、Git 并推送。

### 读取的关键输入

- `AGENTS.md` 规定的项目入口、`STATUS.md`、`PROJECT_PLAN.md`、`ARCHITECTURE.md`、`DECISIONS.md`、实验矩阵和 T01 技术路线。
- `config/tcad_t01_baseline.json` 冻结的几何、材料、方程、接触、求解器和偏压协议。
- T01-A/B/C 的 PASS 报告及 T01-C `WARNING`；每次运行锁定配置和三份依赖报告 SHA-256。

### 本次修改

- 新增 `config/tcad_t01_d_mesh_refinement.json`、`tcad/run_t01_single_gate_mesh_refinement.py`、`scripts/check_t01_d_mesh_refinement.py` 与 `make t01-d-mesh`/`make t01-d-mesh-check`。
- 扩展已有结构化网格构造器：只有新配置声明时才启用界面窗口分段加密；T01-B/C 原路径保持不变。
- 固定 T01-C fine 的 x 向 250 nm、氧化层体区 5 nm、沟道体区 3 nm 网格及全部物理输入，仅在 Al2O3/IGZO 界面两侧 10 nm/12 nm 窗口按 1x/2x/4x/8x 加密。
- 保存输入快照、完整 DEVSIM 求解记录、28 点偏压表、网格规模表、相邻网格比较、T01-C 回归表、4 份 VGS=1 V 节点状态、20 个 VTK 关联文件、机器报告和独立验收报告。
- 将 T01-D-A 接入总项目检查、实验矩阵、状态、计划、架构、ADR、汇报稿、TCAD 路线、报告第 5/7 章和证据矩阵。

### 实际结果与失败记录

- 首次运行的 4 档、48 次 DC 和 28 个正式点全部收敛，4x/8x 数值门也通过；但分段长度/间距的浮点商略高于整数，直接 `ceil` 使 `fine_1x` 多插入一层节点，对 T01-C fine 的最大电流回归差约 0.098%，因此阶段报告正确返回 FAIL。
- 将分段计数修正为“接近整数时使用该整数”，未改变物理输入、网格目标间距或 5%/1 mV 验收阈值；完整重跑后 `fine_1x` 恢复 656 个活动节点，对 T01-C fine 的最大电流回归差为 7.83e-15。
- 四档活动节点数为 656/902/1394/2378，48 次 DC 和 28 个正式点全部收敛，漏电流随 VGS 单调，最大源漏相对不平衡为 8.45e-14。
- 4x/8x 在 VDS=0.01 V、VGS=0.5/1.0 V 的最大电流相对差为 0.01639%，最大中心沟道势差为 0.03265 mV，低于冻结的 5%/1 mV 门；独立 14 项检查 PASS。

### 验证

```text
make t01-d-mesh
T01_D_MESH_PASS meshes=4 bias_points=28

make t01-d-mesh-check
T01_D_MESH_CHECK_PASS checks=14

make check
PROJECT_CHECK_PASS checks=196

make report-check
REPORT_STRUCTURE_PASS chapters=12 appendices=5 placeholders=19 images=0

git diff --check
PASS
```

### 决策和边界

- T01-D-A 形成 E2 教学参数网格证据，只证明 VDS=0.01 V、VGS=0.5/1.0 V 目标点的数值绝对电流已随界面法向网格收敛。
- 本阶段不包含完整 Id-Vd、全工作区 Id-Vg 网格指标、VTH/SS/迁移率、物理 Ion/Ioff、实验精度、双栅、紧凑模型、电路或版图结论。
- T01-D-A 只打开 T01-D-B；完整 T01 仍需 T01-D-B Id-Vd 与 T01-D-C 状态/提取阶段门。

### 下一步

以 `interface_4x` 作为 T01-D-B 生产网格、`interface_8x` 作为选点复核网格，按冻结的 VGS=0/0.3/0.5/1.0 V 和 VDS=0/0.01/0.05/0.1/0.2 V 运行 Id-Vd；先做最小偏压族和守恒检查，不同时启动 T01-D-C 或 T02。

---

## 2026-07-31 | Codex GPT-5 | 完成 T01-C 单栅低漏压栅压续算并登记网格警告

### 用户目标

按阶段门开始 T01-C：继承 T01-B 的 VGS=0 V、VDS=0.01 V 收敛路径，完成冻结的 -1.0 至 1.0 V 栅压续算；通过后更新状态、报告、Git 并推送，不启动 T02、SPICE 或版图工作。

### 读取的关键输入

- `AGENTS.md` 规定的项目入口、`STATUS.md`、`PROJECT_PLAN.md`、`ARCHITECTURE.md`、`DECISIONS.md` 和实验矩阵。
- `config/tcad_t01_baseline.json` 冻结的 T01-A 几何、方程、网格、接触和 8 点 VGS 阶梯。
- T01-A 合同 PASS 报告与 T01-B 低漏压 PASS 报告；T01-C 每次运行都锁定三者 SHA-256。

### 本次修改

- 新增 `config/tcad_t01_c_transfer.json`、`tcad/run_t01_single_gate_transfer.py`、`scripts/check_t01_c_transfer.py` 与 `make t01-c-transfer`/`make t01-c-check`。
- 每档网格先重放零偏压和 T01-B 低 VDS 路径，再经 VGS=0 -> -0.5 -> -1.0 V 预处理，随后按冻结顺序记录 8 个 VGS 点，避免直接跳到最大负栅压。
- 保存输入快照、完整 DEVSIM 求解记录、规范 Id-Vg/网格 CSV、16 份逐偏压节点状态、6 组选定偏压 VTK、状态 manifest、机器报告和独立验收报告。
- 将 T01-C 接入项目检查、实验矩阵、状态、计划、架构、ADR、汇报稿、TCAD 路线、报告第 5/7 章和证据矩阵。

### 实际结果与失败记录

- 首次开发运行的 30 次 DC 求解和 16 个正式偏压点均收敛，但初始合同把 T01-D 的全曲线 5% 相对网格门提前用于 T01-C；VGS=1 V 的粗细电流差为 27.5%，因此阶段报告正确返回 FAIL。
- 依据既有计划中“T01-C 做 VGS continuation，T01-D 做完整网格指标”的边界，合同改为：T01-C 必须通过收敛、守恒、单调性、T01-B 锚点回归、逐点状态和不超过 0.25 decade 的对数曲线差，同时把超过 5% 的绝对电流差保存为 `WARNING` 并禁止定量使用。没有把 27.5% 写成网格一致。
- 完整重跑后，两档网格 30 次 DC 求解全部收敛；最大源漏相对不平衡为 1.61e-12，VGS=0 V 电流相对 T01-B 的回归差不超过 6.36e-15，漏端电流在两档网格均随 VGS 单调增加。
- VGS=1 V 漏端二维电流为 coarse `2.760977e-5 A/cm`、fine `3.808578e-5 A/cm`；相对差 `27.506%`、对数差 `0.139700 decade`。该警告使绝对电流、约 17 decade 数值跨度、Ion/Ioff 和参数提取继续阻塞到 T01-D。

### 验证

```text
make t01-c-transfer
T01_C_TRANSFER_PASS meshes=2 bias_points=16

make t01-c-check
T01_C_TRANSFER_CHECK_PASS checks=14

make check
PROJECT_CHECK_PASS checks=179

make report-check
REPORT_STRUCTURE_PASS chapters=12 appendices=5 placeholders=19 images=0
```

### 决策和边界

- T01-C 形成 E2 教学参数低漏压栅压续算证据，只证明数值连续性、守恒和单调栅控；不关闭完整 T01 门。
- 负栅压端的极低数值电流来自无陷阱、无复合、理想接触的教学闭合，不能称为物理 Ioff 或实验开关比。
- T01-D 必须先做累积层局部网格加密，再做完整 Id-Vd、状态图集合和 VTH/SS/迁移率提取；其通过前不得启动 T02 或定量紧凑模型。

### 下一步

把 T01-D 再拆成最小网格收敛子阶段：只比较高正栅压累积态的局部加密网格，确定绝对电流稳定后，再运行多 VGS 的 Id-Vd。

---

## 2026-07-31 | Codex GPT-5 | 完成 T01-B 单栅低偏压漂移扩散烟雾

### 用户目标

在不启动 T02、SPICE、KLayout 或完整 I-V 扫描的前提下，执行 T01-B：先验证单栅 IGZO 的零偏压平衡态、低 VDS continuation、接触电流接口和两档网格基础一致性。

### 读取的关键输入

- `AGENTS.md`、`STATUS.md`、`PROJECT_PLAN.md`、`ARCHITECTURE.md`、`DECISIONS.md` 和 T01-A 输入合同。
- `config/tcad_t01_baseline.json`、S00 G0 教学参数边界、既有 T00 网格/接触实现。
- DEVSIM 2.10.0 的 `simple_dd`、`simple_physics` 与二维 MOS/diode 示例，确认 Scharfetter-Gummel 电流、欧姆接触和混合残差口径。

### 本次修改

- 新增 `config/tcad_t01_b_smoke.json`、`tcad/run_t01_single_gate_smoke.py`、`scripts/check_t01_b_smoke.py` 与 `make t01-b-smoke`/`make t01-b-check`。
- 运行器保存输入快照、DEVSIM 求解记录、偏压点 CSV、两档网格节点 CSV、VTK、机器可读结果和独立验收报告。
- 修正 T01-A 合同元数据：明确 10 nm 是未用于 T01 的 SPICE 有效 TOX；环境空气是无方程的接触拓扑缓冲区，沟道顶边仍为自然零法向通量；Poisson 与载流子连续性残差采用独立且有理由的绝对阈值。
- 将 T01-B 接入实验矩阵、项目检查、状态、架构、计划、汇报稿、TCAD 路线、报告第 5/7 章和证据矩阵。

### 实际结果与失败记录

- 首次运行发现最小两区域网格无法让 DEVSIM 识别 `bottom_gate`；加入无电学方程的环境接触缓冲区后，底栅、源、漏分别识别为 21/5/5 个粗网格接触节点。
- 第二次运行显示通用 `1e-12` 绝对残差不适用于以 `cm^-3` 计的载流子连续性残差；相对残差已低于 1e-10 但被绝对门阻止。配置中分离 Poisson `1e-12` 与耦合载流子 `1e10` 的 DEVSIM 残差阈值后重跑。
- 两档网格各完成 6 次 DC 求解：零偏压 Poisson、零偏压耦合平衡态和 VGS=0 V、VDS=0/1/5/10 mV continuation，均收敛。
- VDS=10 mV 漏端二维电流：coarse `1.235458e-6 A/cm`，fine `1.232488e-6 A/cm`；相对网格差 `0.240398%`。非零点源漏相对电流不平衡最大值为 `1.37e-14`（coarse）和 `1.29e-14`（fine）。

### 验证

```text
make t01-b-smoke
T01_B_SMOKE_PASS meshes=2 bias_points=8

make t01-b-check
T01_B_SMOKE_CHECK_PASS checks=11
```

```text
make t01-a-check
T01_A_CONTRACT_PASS checks=16 simulation=NOT_RUN

make check
PROJECT_CHECK_PASS checks=164

make report-check
REPORT_STRUCTURE_PASS chapters=12 appendices=5 placeholders=19 images=0

git diff --check
PASS
```

### 决策和边界

- T01-B 形成 E2 教学参数器件数值证据，只覆盖零偏压和 VGS=0 V、VDS<=0.01 V；它不关闭完整 T01 阶段门。
- 不得将本次结果写成完整 `Id-Vg`、完整 `Id-Vd`、VTH/SS/迁移率提取、实验拟合、模型精度或双栅预测。
- 常数迁移率、背景施主浓度和理想欧姆接触仍是教学闭合假设；完整状态集和参数提取留给 T01-C/D，定量标定仍受 G0 限制。

### 下一步

从 T01-C 开始：继承 T01-B 的 VDS=0.01 V 收敛解，按冻结 VGS 阶梯逐点续算；不通过前不启动 T02 或电路工作。

---

## 2026-07-30 | Codex GPT-5 | 完成 T01-A 单栅漂移扩散输入合同

### 用户目标

完成 T01-A：只冻结最小单栅 IGZO 漂移扩散案例的输入和求解顺序，不运行器件仿真。

### 读取的关键输入

- `AGENTS.md`、`STATUS.md`、`PROJECT_PLAN.md`、`ARCHITECTURE.md` 和 `config/experiments.json`。
- `config/project.json`、`config/tcad_baseline.json`、`tcad/run_dg_electrostatic.py` 及 DEVSIM 2.10.0 的 `simple_dd`/`simple_physics` 实现。
- S00 审计报告和 T01/T02 阶段门；T00 仅作为静电参考，不直接产生输运结果。

### 本次修改

- 新增 `config/tcad_t01_baseline.json`：冻结单栅几何、厘米制单位、IGZO 教学参数、电子-only 漂移扩散、理想欧姆接触、两档网格和四级 continuation 偏压协议。
- 新增 `scripts/check_t01_a_contract.py` 与 `make t01-a-check`，生成 `results/reports/tcad_t01_input_contract.json`。
- 将 T01 输入合同接入 `scripts/check_project.py` 和 `config/experiments.json`，更新状态、计划、架构、AI 上下文、汇报稿、ADR、报告第 5 章和证据矩阵。

### 验证

```text
python3 -m json.tool config/tcad_t01_baseline.json
python3 -m py_compile scripts/check_t01_a_contract.py
make t01-a-check
T01_A_CONTRACT_PASS checks=15 simulation=NOT_RUN
```

后续还要运行 `make check`、`make report-check` 和 `git diff --check`。本次没有运行 DEVSIM、SPICE、KLayout、DRC 或 LVS。

### 决策和边界

- T01-A 的输入合同证据为 E3，器件仿真证据仍为 E0；`Id-Vg`、`Id-Vd`、守恒、收敛、网格独立性和迁移率提取都未产生。
- 单栅结构不包含顶栅/顶介质；30 nm 物理 Al2O3 用于 TCAD 几何，10 nm 有效 TOX 延后到紧凑模型。
- 背景施主浓度、电子亲和势、带隙和有效态密度是明示的 T01-A 初始化假设，不是实验拟合值。

### 下一步

等用户授权 T01-B 后，先运行零偏压平衡态和低 VDS 单点，检查收敛和接触电流接口；通过后才进入分步 VGS。

---

## 2026-07-30 | Codex GPT-5 | 完成 S00 数据口径审计

### 用户目标

执行 S00：冻结活动 IGZO 数据来源、单位、数据集边界和冲突口径，为 T01 最小单栅漂移扩散案例建立可追溯输入。

### 读取的关键输入

- `config/project.json`、`config/tcad_baseline.json` 与 `config/experiments.json`。
- 冻结的 7 个 IGZO 外部基线副本及其 manifest。
- 老师要求、23 个学长参考文件和 13 篇本地文献索引。
- 已规范化的学长 IGZO 转移曲线和反相器 VTC 参考 CSV。

### 本次修改

- 新增 `config/s00_data_audit.json`，固定 8 个数据集边界、9 个活动参数、14 个参考数据字段的单位和 6 项冲突及 G0 决策。
- 新增 `scripts/audit_s00_data.py` 与 `make s00-audit` / `make s00-audit-check`。
- 生成 `data/processed/s00/` 的来源库存、单位表、数据集边界和冲突登记，以及 `results/reports/s00_data_audit.json`。
- 将 S00 输出纳入项目检查器，并更新机器实验合同、状态、计划、架构入口、ADR、汇报稿、报告第 6 章和证据矩阵。

### 验证

```text
make s00-audit
S00_AUDIT_PASS sources=50 parameters=9 fields=14 datasets=8 conflicts=6 g0=TEACHING_BASELINE_ONLY

make s00-audit-check
S00_AUDIT_PASS sources=50 parameters=9 fields=14 datasets=8 conflicts=6 g0=TEACHING_BASELINE_ONLY

make check
PROJECT_CHECK_PASS checks=145

make report-check
REPORT_STRUCTURE_PASS chapters=12 appendices=5 placeholders=21 images=0
```

本次没有运行 TCAD、SPICE、KLayout、DRC 或 LVS。结构/来源检查 PASS 不代表器件或电路仿真 PASS。

### 决策和边界

- G0 为 `TEACHING_BASELINE_ONLY`：允许以 35.5 cm2/(V*s)、0.21 V 和冻结几何做 E2 教学参数 T01。
- 主 IGZO 原始 Id-Vg/Id-Vd、批次、温度、扫压方向和接触条件仍缺失；禁止实验拟合、模型精度或校准双栅预测。
- 30 nm 物理 Al2O3 与 10 nm SPICE 有效 TOX 分栏保存；旧 SnO 资产继续排除在活动基线之外。

### 下一步

仅启动一个单栅 T01 最小漂移扩散案例：先定义单位体系、单栅几何、载流子和理想欧姆接触，再按零偏压、低 VDS、分步 VGS 的顺序求解。T01 未通过收敛、守恒和网格门前，不启动 T02 或电路工作。

## 2026-07-30 | Codex GPT-5 | 报告改为分章写作、单文件提交

### 用户目标

老师最新口头建议最终报告最好分章节。调整工程报告结构，同时保持老师书面要求中的单个自包含 HTML 提交格式。

### 要求解释

- 写作、修改和审阅：12 个主章节与 5 个附录分别维护。
- 最终提交：仍由构建器合并为唯一 `report/final/实验报告.html`。
- 阅读/打印：自动生成目录，打印时每章另起一页。
- 不维护“章节版正文”和“合并版正文”两套内容，防止不一致。

### 本次修改

- 新增 `report/manifest.json`，固定外壳、12 章、5 附录和最终输出顺序。
- 新增 `report/chapters/*.xhtml` 与 `report/appendices/*.xhtml`，从旧长草稿迁移全部占位内容。
- 将 `report/src/实验报告_草稿.xhtml` 改为只含标题、CSS、目录和内容容器的外壳。
- 重写 `scripts/build_self_contained_report.py`，按清单组装、生成目录、校验片段并嵌入图片。
- 更新项目检查器、机器配置、R00 合同、报告说明、架构、计划、状态和 AI 交接规范。

### 验证

```text
make report-check
REPORT_STRUCTURE_PASS chapters=12 appendices=5 placeholders=22 images=0

make report
REPORT_BUILD_FAIL Unresolved placeholders: 22

make check
PROJECT_CHECK_PASS checks=131
```

`make report` 当前失败是预期的防误交保护，正式正文填完前不会生成最终报告。本次未运行 TCAD、SPICE、KLayout、DRC 或 LVS。

### 下一步

后续每完成一个实验，同步填写对应章节并运行 `make report-check`。全部 22 个占位符解决后，才运行 `make report` 生成正式提交文件。

## 2026-07-30 | Codex GPT-5 | 建立多 AI 自动接手入口

### 用户目标

把项目交接要求直接加入工程，使获得仓库访问权限的其他编码 AI 能自行读取范围、状态、证据边界和协作规则。

### 本次修改

- 新增根目录 `AGENTS.md`，作为唯一完整的 AI 协作合同。
- 新增 `CLAUDE.md` 和 `.github/copilot-instructions.md`，只负责把兼容工具引导到 `AGENTS.md`，不复制项目事实。
- 在 `README.md` 和 `AI_CONTEXT.md` 增加 AI 第一入口。
- 在 `STATUS.md` 记录交接入口完成。
- 更新 `scripts/check_project.py`，强制检查三个入口及关键合同标记。

### 合同内容

- 固定 IGZO-only 范围、单极性有源负载拓扑和器件数。
- 固定证据边界、阶段门、数据纪律、验证要求和 Git 安全规则。
- 当前进度只从 `STATUS.md` 读取，避免入口文件复制易过期状态。
- 禁止覆盖未提交修改、强制推送、上传凭据和把结构检查冒充领域结果。

### 验证

```text
make check
PROJECT_CHECK_PASS checks=122
```

本次只增加交接与检查基础设施，没有运行 TCAD、SPICE、KLayout、DRC 或 LVS。

### 使用方法

让新的仓库型 AI 先读根目录 `AGENTS.md`。普通网页聊天 AI 若没有本机或私有仓库访问权限，仍需上传文件或授权仓库读取，不能向其发送 Token 或 SSH 私钥。

## 2026-07-30 | Codex GPT-5 | Git/GitHub 版本库初始化

### 用户目标

从零建立 Git 版本控制并上传到 GitHub 私有仓库，便于后续按阶段保存、比较和恢复工程版本。

### 本次操作

- 验证 WSL Git、提交署名和现有 Ed25519 SSH 密钥。
- 验证 GitHub SSH 身份为 `ReachGa0`，远端仓库为空。
- 在项目根目录初始化 `main` 分支并绑定 `origin`：`git@github.com:ReachGa0/dg-igzo-tft-course-project.git`。
- 扩充 `.gitignore`，排除缓存、虚拟环境、本地编辑器文件和常见凭据文件。
- 新增 `.gitattributes`，统一 Windows/WSL 文本换行并标记二进制文件。
- 创建并推送首个架构基线提交 `c03d9b8`，包含 91 个文件。

### 上传前验证

```text
SSH authentication: PASS, account=ReachGa0
secret/large-file scan: PASS
PROJECT_CHECK_PASS checks=116
local main == origin/main == c03d9b8
```

没有上传密码、Token、SSH 私钥、虚拟环境或缓存目录。

### 后续版本流程

```bash
git status
git diff
git add <本次相关文件>
git commit -m "说明本次完成的内容"
git push
```

## 2026-07-30 | Codex GPT-5 | IGZO-only 架构冻结

### 用户目标

继续原高难度双栅氧化物 TFT 项目，只移除旧材料分支；当前只确定完整总体架构，不开始新的实现。

### 关键决策

- 正式范围为双栅 IGZO 二维器件模型、紧凑模型、单极性逻辑和教学 PDK。
- 电路固定为双栅 IGZO 有源负载有比例逻辑，器件数为 2/3/3/12/10/33。
- 旧范围电路结果失效；T01/M00/C00/L00/V01 均维持 E0。
- 当前只做文档、配置、接口和清理，不运行新的领域仿真。

### 本次架构文件

- 新增 `ARCHITECTURE.md`。
- 重写 `README.md`、`PROJECT_PLAN.md`、`STATUS.md` 和 `AI_CONTEXT.md`。
- 更新 `config/project.json`、`config/experiments.json`、`docs/01` 至 `docs/12` 和报告标题。
- 新增模型、网表和 DRC 目录合同 README；没有保留刚生成的实现模板。
- 在 `DECISIONS.md` 增加 ADR-008 至 ADR-010。
- 删除临时的新方向交接文件；活动冻结基线重建为 7 个 IGZO 来源副本。
- 更新基线/学长资料导入规则和项目检查规则，但没有新增器件、模型、网表或版图实现。

### 验证

```text
make import-baseline
make import-senior
make check
rg -i "sno" <活动配置、模型、网表、PDK、版图、验证和报告目录>
```

结果：

- `BASELINE_IMPORT_PASS files=7`。
- `SENIOR_REFERENCE_IMPORT_PASS files=23 inverter_rows=181 igzo_rows=123 office_files=6`。
- `PROJECT_CHECK_PASS checks=116`，0 失败。
- 活动目录无 SnO 文件；相关文字只保留在决策和 AI 历史中。
- 本轮未运行 TCAD、SPICE、KLayout、DRC 或 LVS。

### 下一步

本轮在架构冻结处停止。用户明确要求开始实现后，先确认数据和工具边界，再进入 T01 的单个最小漂移扩散案例。

## 2026-07-30 | Codex GPT-5 | 紧急换方向交接

### 用户目标

老师确认 SnO 部分可以不做。暂停旧方案，把此前获得的老师要求、论文、数据、工具、学长参考和证据边界汇总到一个文件，供新对话重新选题。

### 读取的关键输入

- 老师 `实验课程项目与报告要求(1).html` 的方向、五组参数、12 章和单文件 HTML 要求。
- `references/papers_manifest.csv` 中 13 篇 HfO2/HZO/ZrO2 铁电/反铁电论文。
- 旧选题论证、文献矩阵、项目配置、现有 TCAD/SPICE/KLayout 资产和学长资料审计结果。

### 本次修改

- 新增 `新方向选题_新对话交接.md`，作为新对话的自包含入口。
- 在 `README.md`、`AI_CONTEXT.md` 和 `STATUS.md` 标记原 IGZO/SnO 方向暂停。
- 保留全部旧资产，不提前决定纯 IGZO、HZO/AFE 或其他新方向。
- 完成 `scripts/import_senior_reference.py` 的 Office/XLSX 审计回归并生成 6 个 Office 文件结构摘要。
- 删除两个 Python 字节码缓存和一个 Matplotlib 字体缓存；在 `.gitignore` 增加 `results/.cache/`。

### 验证

```text
make import-senior
make check
```

结果：

- `SENIOR_REFERENCE_IMPORT_PASS files=23 inverter_rows=181 igzo_rows=123 office_files=6`。
- `PROJECT_CHECK_PASS checks=99`。
- `scripts/__pycache__` 和 `results/.cache` 已清空并移除。

### 证据边界

- “SnO 可以不做”来自用户转述的老师口头意见，尚无书面范围细则。
- 旧工程配置仍含 SnO 和互补标准单元，只能作为历史范围和可复用资产。
- 新方向确认前不声称旧题目仍有效。

### 下一步

在新对话中先读交接文件和用户追加论文，输出候选方向评分与推荐；确认方向后再统一迁移工程。

## 2026-07-30 | Codex GPT-5

### 用户目标

系统讲清完成本项目需要掌握的知识，并解释每个实验为什么这样设计，生成可供学习、汇报和后续 AI 接手的中文 Markdown 文档。

### 读取的关键输入

- 项目 `README.md`、计划、状态、决策、AI 上下文和既有知识/验证文档。
- AIM-Spice Level15 模型卡、ngspice 行为模型、仿真摘要和教学 PDK 参数。
- 两组 IGZO/SnO 参数口径及 13 篇 HZO/ZrO2 文献调研矩阵。

### 本次修改

- 新增 `docs/09_知识点详解与实验设计原理.md`。
- 在 `README.md` 增加文档入口。
- 在 `STATUS.md` 记录学习与实验设计文档完成。

### 文档范围

- 从 TFT 器件物理、I-V 指标、Level15/ngspice 模型，到互补逻辑、环振、全加器、PDK、DRC/LVS/PEX。
- 解释双栅电容耦合、HZO 极化、Landau/LK、NLS 和可靠性效应的适用层次。
- 为 E00-E15 写明研究问题、设计原因、变量、控制条件、判据、诊断方式和证据边界。
- 明确当前混合参数目标、物理厚度/有效 TOX 差异及已完成/未完成事项。

### 验证

```bash
make check
awk '/^```/{n++} END{exit n % 2}' docs/09_知识点详解与实验设计原理.md
```

结果：

- `PROJECT_CHECK_PASS checks=59`，报告更新为 `results/reports/project_check.json`。
- Markdown 代码围栏共 102 行，为偶数；主章节编号从 0 到 36 连续，文件非空。

### 下一步

按 E00 完成数据口径冻结，然后从 E05 反相器建立首个“网表 -> GDS -> DRC -> 几何 LVS”最小闭环。

## 2026-07-29 | Codex GPT-5

### 用户目标

根据本地论文和已有氧化物 TFT 工程，选择一个难度较高、可获得完整经验且有评分亮点的课程项目，建立独立工程目录、AI 交接文档和面向人的中文手把手说明。

### 读取的关键输入

- `C:\Users\ReachGao\Desktop\SDU\科研\论文` 中 13 篇 PDF。
- `C:\Users\ReachGao\Desktop\SDU\科研\论文_翻译` 中 HfO2 综述中文摘要。
- 已有 `ngspice_results`：器件、反相器、5 级环振和全加器前仿真。
- 已有 `AIMSPICE_improved`：Level15/HSPICE Level61 方向的课程网表。
- 已有 `klayout_oxide_pdk`：IGZO/SnO 器件 PCell、GDS、层表和教学 DRC。
- KLayout 官方 LVS 文档：内置 `mos3/mos4/dmos3/dmos4`、`extract_devices`、`connect`、`schematic`和 `compare`。

### 论文判断

论文主题集中在 HfO2/HZO/ZrO2 铁电与反铁电，关键变量是极化、相组成、应变、界面层、唤醒/疲劳和 NLS 开关动力学。它们适合支撑 HZO 铁电顶栅扩展，但不能代替 IGZO/SnO TFT 原始 I-V 数据。

### 决策

选择“基础 PDK/数字逻辑闭环 + 双栅 HZO 铁电扩展”的两层范围。不选 CFET/OISC 作为本次主线，因为它与现有 TFT 工艺和数据衔接弱；不选 COGENDA Te TFT 作为主线，因为当前无 Te TFT 数据、模型和已验证环境。

### 本次产物

- 独立工程目录 `氧化物TFT_铁电双栅课程项目`。
- 人类入口 `README.md`。
- AI 入口 `AI_CONTEXT.md` 与本 `AI_LOG.md`。
- 项目计划、状态、决策、文献矩阵、IC 流程、验收、汇报和风险文档。
- 基线导入脚本与项目完整性检查脚本。

### 验证

```bash
python -m py_compile scripts/import_baseline.py scripts/check_project.py
python scripts/import_baseline.py
make check
```

结果：

- Python 语法检查 PASS。
- 基线导入 PASS：44 个文件，每个源/目标 SHA-256 一致。
- 项目检查 PASS：59 项，0 失败。
- 报告：`results/reports/project_check.json`。

### 证据边界

当前只完成选题与工程骨架。基础门、环振、全加器版图和几何 LVS 仍未实现；HZO 扩展仍处于文献约束的研究计划阶段。

### 下一步

1. 2026-07-30 向老师确认选题和数据/工艺/LVS 边界。
2. 运行基线导入并锁定输入哈希。
3. 从 INV 开始建立“网表 -> PCell -> GDS -> DRC -> 几何 LVS”最小闭环。
