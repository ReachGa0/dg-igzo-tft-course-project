# 二维 TCAD 支线

## 这部分在项目里做什么

本项目**涉及二维 TCAD**，但分成两个证据层次：

1. `T00` 已搭建的双栅静电基准：求解二维电势，检查网格、边界条件和上下栅耦合。
2. `T01-B` 已运行的单栅 IGZO 低偏压烟雾：验证零偏压与 VGS=0 V、VDS<=0.01 V 的输运闭合。
3. `T01-C` 已运行的单栅低漏压栅压续算：在 VDS=0.01 V 保存 VGS=-1.0 至 1.0 V 的端口与节点状态，并暴露高正栅压网格警告。
4. `T01-D-A` 已运行的界面法向网格收敛：固定横向和体区网格，只在氧化层/沟道界面窗口做 1x/2x/4x/8x 加密，验证 VGS=0.5/1.0 V 目标点。
5. `T01-D-B` 已运行的离散 Id-Vd 曲线族：interface_4x 完成 4 条正式曲线，interface_8x 复核 2 条高栅压曲线。
6. `T01-D-C` 已运行的状态与受限提取：两档网格完成同一 51 点低漏压网格，interface_4x 保存关态/目标附近/开态的电势、电子浓度和局部电流密度。
7. `T02-A` 已运行的顶栅极限回归：先冻结对称 30 nm Al2O3 教学顶栈，再证明移除整个顶栈后 7 个低漏压点返回 T01，并对启用顶栈的结构只做全零偏压平衡烟雾。
8. `T02-B` 已运行的最小正向顶栅族：固定 VDS=0.01 V、VBG=0 V，只将 VTG 从 0 V 增至 0.3 V，验证端口守恒、响应方向和端点内部状态。

`T00` 不能被写成“IGZO TFT 电流仿真已完成”。它只证明二维结构、Poisson 方程、边界条件、扫描和数据导出链路能运行。

## 为什么选 DEVSIM

- 开源，Python API 可审查；
- 二维网格和方程可自定义；
- 当前笔记本已有 DEVSIM `2.10.0`、Gmsh `4.15.2` 和 NumPy；
- 可输出 VTK/CSV/PNG，不依赖 VisualTCAD 授权。

学长的 `VisualTCAD_Inverter.pptx` 只用于参考“结构 -> 边界 -> 电路符号 -> 扫描 -> 曲线”的操作顺序。其硅 CMOS 截面、材料参数和 VTC 不属于本项目氧化物 TFT 结果。

## 目录

```text
tcad/
|-- README.md
|-- run_dg_electrostatic.py   # T00 二维双栅静电基准
|-- run_t01_single_gate_smoke.py # T01-B 单栅低偏压漂移扩散烟雾
|-- run_t01_single_gate_transfer.py # T01-C 单栅低漏压 Id-Vg 续算
|-- run_t01_single_gate_mesh_refinement.py # T01-D-A 界面法向网格收敛
|-- run_t01_single_gate_idvd.py # T01-D-B 离散 Id-Vd 曲线族
|-- run_t01_single_gate_extraction.py # T01-D-C 状态与数值代理提取
|-- run_t02_dual_gate_limit_regression.py # T02-A 顶栅极限回归
|-- run_t02_dual_gate_minimal_bias.py # T02-B 最小正向顶栅族
|-- structures/README.md      # 后续 Gmsh/DEVSIM 结构与网格
|-- physics/README.md         # 方程、材料、陷阱和接触模型
`-- tests/README.md           # 网格、极限条件和故障测试
```

参数文件位于 `config/tcad_baseline.json`，结果写入：

```text
results/tcad/dg_electrostatic/
results/tables/tcad_dg_*.csv
results/figures/tcad_dg_*.png
results/reports/tcad_dg_electrostatic.json
```

T01-B 使用 `config/tcad_t01_baseline.json` 和 `config/tcad_t01_b_smoke.json`，结果写入：

```text
results/tcad/t01_single_gate/t01_b_smoke/
results/tables/tcad_t01_b_*.csv
results/reports/tcad_t01_b_smoke.json
results/reports/tcad_t01_b_smoke_check.json
```

T01-C 使用 `config/tcad_t01_c_transfer.json`，结果写入：

```text
results/tcad/t01_single_gate/t01_c_transfer/
results/tables/tcad_t01_c_idvg.csv
results/tables/tcad_t01_c_mesh_comparison.csv
results/reports/tcad_t01_c_transfer.json
results/reports/tcad_t01_c_transfer_check.json
```

T01-D-A 使用 `config/tcad_t01_d_mesh_refinement.json`，结果写入：

```text
results/tcad/t01_single_gate/t01_d_mesh_refinement/
results/tables/tcad_t01_d_mesh_*.csv
results/tables/tcad_t01_d_t01_c_reproduction.csv
results/reports/tcad_t01_d_mesh_refinement.json
results/reports/tcad_t01_d_mesh_refinement_check.json
```

T01-D-B 使用 `config/tcad_t01_d_idvd.json`，结果写入：

```text
results/tcad/t01_single_gate/t01_d_idvd/
results/tables/tcad_t01_d_idvd_*.csv
results/reports/tcad_t01_d_idvd.json
results/reports/tcad_t01_d_idvd_check.json
report/assets/tcad_t01_d_idvd.png
```

T01-D-C 使用 `config/tcad_t01_d_extraction.json`，结果写入：

```text
results/tcad/t01_single_gate/t01_d_extraction/
results/tables/tcad_t01_d_extraction_*.csv
results/reports/tcad_t01_d_extraction.json
results/reports/tcad_t01_d_extraction_check.json
report/assets/tcad_t01_dc_extraction.png
report/assets/tcad_t01_dc_state_maps.png
```

T02-A 使用 `config/tcad_t02_a_dual_gate_contract.json`，结果写入：

```text
results/tcad/t02_dual_gate/t02_a_limit_regression/
results/tables/tcad_t02_a_*.csv
results/reports/tcad_t02_a_input_contract.json
results/reports/tcad_t02_a_limit_regression.json
results/reports/tcad_t02_a_limit_regression_check.json
```

T02-B 使用 `config/tcad_t02_b_minimal_bias.json`，结果写入：

```text
results/tcad/t02_dual_gate/t02_b_minimal_bias/
results/tables/tcad_t02_b_minimal_bias.csv
results/tables/tcad_t02_b_state_summary.csv
results/reports/tcad_t02_b_input_contract.json
results/reports/tcad_t02_b_minimal_bias.json
results/reports/tcad_t02_b_minimal_bias_check.json
report/assets/tcad_t02_b_minimal_bias.png
```

## 运行 T00

在项目根目录执行：

```bash
make tcad-smoke
```

该命令会设置 DEVSIM 所需的 BLAS/LAPACK 库名，并使用课程 0 的 Python 环境。

## 运行 T01-B

```bash
make t01-b-smoke
make t01-b-check
```

T01-B 的 PASS 仅表示两个结构化网格上零偏压和 `VGS=0 V, VDS=0/1/5/10 mV` 续算收敛、端口电流守恒和低偏压网格比较通过。它不表示完成了 `Id-Vg`、完整 `Id-Vd`、参数提取、实验拟合或双栅电流预测。

## 运行 T01-C

```bash
make t01-c-transfer
make t01-c-check
```

T01-C 的 PASS 表示冻结的 8 个 VGS 点在两档网格完成续算、守恒、单调性、T01-B 锚点回归和状态文件检查。VGS=1 V 的粗细网格绝对电流相差 27.5%，已作为 `WARNING` 保存；约 17 decade 的数值跨度不是物理 Ion/Ioff，完整网格收敛和 Id-Vd 留给 T01-D。

## 运行 T01-D-A

```bash
make t01-d-mesh
make t01-d-mesh-check
```

T01-D-A 的 PASS 表示 4 档界面窗口网格的 48 次 DC 和 28 个正式点收敛，端口守恒与单调性通过，`fine_1x` 复现 T01-C fine，并且 `interface_4x/interface_8x` 在 `VDS=0.01 V, VGS=0.5/1.0 V` 的最大电流差为 0.01639%、中心势差为 0.03265 mV。该结论仅是教学模型在这些目标点的数值网格收敛；完整 Id-Vd、参数提取、实验精度和双栅预测仍未完成。

## 运行 T01-D-B

```bash
make t01-d-idvd
make t01-d-idvd-check
```

T01-D-B 的 PASS 表示 6 条独立初始化曲线的 65 次 DC 和 30 个冻结偏压点全部收敛，端口守恒、VDS/VGS 次序和选定 4x/8x 网格复核通过。它只验证离散教学模型点；连续输出行为、饱和机理、状态图、参数提取、实验精度和双栅预测仍未完成。

## 运行 T01-D-C

```bash
make t01-d-extract
make t01-d-extract-check
```

T01-D-C 的 PASS 表示 interface_4x/interface_8x 各 51 个低漏压正式点、共 120 次 DC 全部收敛，并补齐 3 组电势/电子浓度/电流密度状态。恒流 VTH、窗口 SS 和物理氧化层电容场效应迁移率均为冻结方法下的数值代理；它们可用于检查教学模型内部一致性，不能写成实测验证参数或物理 Ion/Ioff。该阶段关闭 T01 教学模型数值门并打开 T02。

## 运行 T02-A

```bash
make t02-a-contract-check
make t02-a-regression
make t02-a-regression-check
```

T02-A 的合同检查不运行仿真；它固定顶栈教学结构、两种耦合模式和偏压顺序。正式回归共 14 次 DC：禁用模式移除顶介质/顶栅并复现 T01 `interface_4x` 的 7 个点；启用模式只验证全零偏压平衡与状态输出。`VTG=0 V` 仍属于有限电容耦合，不能当作禁用极限。T02-A 的 PASS 不是非零双栅电流、Delta VTH、gm 或完整 T02 验证；它只打开 T02-B 最小非零偏压族。

## 运行 T02-B

```bash
make t02-b-contract-check
make t02-b-minimal
make t02-b-minimal-check
```

T02-B 合同检查不运行仿真；它固定启用拓扑、`VDS=0.01 V`、`VBG=0 V`、`VTG=0/0.1/0.2/0.3 V` 和端点状态。正式运行共 9 次 DC，四个正式点的电流、中心电势和中心电子浓度均严格增加，最大端口相对不平衡为 1.405e-14，端点电流比为 9.6802；独立 14 项检查 PASS。T02-B 只打开 T02-C，不验证负偏压、回程扫描、Delta VTH、gm 或完整 T02。

## 运行 T02-C

```bash
make t02-c-contract-check
make t02-c-bidirectional
make t02-c-bidirectional-check
```

T02-C 合同检查不运行仿真；21 项检查冻结 `VDS=0.01 V`、三档第二栅偏压、31 点主栅网格、双向扫描路径、恒流 VTH/gm/耦合斜率提取方法和 6 个代表状态。正式运行共完成 318 次 DC，并落盘 186 个正向曲线点和 62 个零第二栅回程点；全部收敛，最大端口相对不平衡为 `3.72e-8`，最大正反向电流相对差为 `8.19e-11`，上下栅互易电流相对差为 `3.70e-8`。顶栅主扫和底栅主扫都得到 `Delta VTH` 对第二栅偏压的 OLS 斜率 `-0.93535 V/V`，`R2=0.99764`；独立 17 项复算 PASS。

这些 VTH、`Delta VTH`、gm 和耦合斜率只是在冻结教学模型和离散偏压网格下的数值代理。T02-C 不构成实验标定、物理电容比、真实回滞、陷阱/接触模型或电路可用性验证。

## T00 的模型

三个区域均求解：

```text
div(epsilon * grad(Potential)) = 0
```

边界条件：

- 左侧 IGZO：源极电势；
- 右侧 IGZO：漏极电势；
- 下介质底边：底栅电势；
- 上介质顶边：顶栅电势；
- 其余外边界：自然零通量边界；
- 两个介质/IGZO 界面：电势连续、电位移通量由区域方程共同守恒。

## T02 已完成及后续工作

1. T02-A 已完成顶栅、顶介质、上下栅边界与禁用极限合同；
2. T02-B 已完成固定 VDS/VBG 的最小正向顶栅偏压族，电流方向、守恒与端点内部状态通过；
3. T02-C 已完成固定第二栅的上下栅主扫族、零第二栅回程路径、受限 VTH/gm/耦合提取和 6 个二维状态，关闭完整 T02 教学模型数值门；
4. T03 必须先冻结一个最小单变量组，再依次受控加入带尾态、深能级、界面陷阱、非理想接触、几何/介质和温度变化；
5. 与老师数据或条件完整的文献/实验数据定量对比。

学长 `1.xlsx` 缺少 `VDS`、尺寸、材料参数和求解设置，因此只能作为导入和形状参考。条件未补齐前，不参与“精确拟合”评分。
