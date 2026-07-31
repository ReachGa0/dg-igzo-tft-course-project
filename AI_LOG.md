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
