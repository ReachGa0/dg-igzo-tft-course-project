# 双栅 IGZO TFT 课程项目

## 1. 正式题目

**基于双栅 IGZO TFT 的二维器件模型、紧凑模型与可编程单极性逻辑教学 PDK**

当前只完成总体架构冻结，不开始新的器件、电路或版图实现。所有 `TODO/E0` 内容都只是计划，不得在汇报中写成已完成结果。

## 2. 为什么这个题目仍然成立

项目核心没有改变：围绕高难度“双栅氧化物 TFT 模型”，建立器件到电路再到版图验证的参数链。范围收敛为单材料 IGZO 后：

1. 二维 TCAD、紧凑模型和参数提取更加集中。
2. 不需要同时解决两类材料的数据与模型不一致。
3. 电路改为双栅 IGZO 有源负载单极性逻辑，第二栅的阈值调节能直接连接器件研究与电路设计。
4. 仍可完成 SPICE、标准单元、环振、全加器、KLayout、DRC/LVS 和报告全流程。
5. HZO 顶栅保留为可选扩展，不阻塞基础交付。

## 3. 四层结构

| 层次 | 研究对象 | 主要输出 |
|---|---|---|
| 器件层 | 二维单栅/双栅 IGZO，陷阱、接触、几何和温度 | Id-Vg/Id-Vd、二维电势/载流子、Delta VTH、敏感性 |
| 模型层 | AIM-Spice Level 15 与 ngspice 行为等效模型 | 参数表、训练/验证误差、适用范围 |
| 电路层 | 双栅 IGZO 有源负载逻辑 | INV、NAND2、NOR2、XOR2、RING5、全加器 |
| PDK 层 | PCell、GDS、DRC、几何 LVS | 标准单元版图、正常 PASS、故障注入 FAIL |

完整依赖、接口和阶段门见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 4. 固定逻辑拓扑

使用 n 型双栅 IGZO 有源负载：负载管由第二栅调节等效阈值，驱动网络负责下拉。它是有比例逻辑，必须报告低电平静态功耗、输出摆幅和负载/驱动尺寸比。

| 单元 | 层次结构 | TFT 数 |
|---|---|---:|
| INV | 负载 + 驱动 | 2 |
| NAND2 | 负载 + 2 个串联驱动 | 3 |
| NOR2 | 负载 + 2 个并联驱动 | 3 |
| XOR2 | 4 个 NAND2 | 12 |
| RING5 | 5 个 INV | 10 |
| FULL_ADDER | 2 XOR2 + 3 NAND2 | 33 |

若有源负载暂不收敛，只能用理想电阻负载做求解/Boolean 冒烟，不能据此报告 PDK、面积或真实功耗。

## 5. 数据事实

基础工艺：

```text
Si substrate / 300 nm thermal SiO2
50 nm Al bottom gate
30 nm Al2O3 physical gate dielectric
24 nm IGZO active layer
50 nm Ti source/drain and interconnect
```

课程尺寸与后续参数口径：

```text
W/L = 60/10 um
effective TOX = 10 nm
dielectric k = 6.8
mobility approximately 35.5 cm2/(V s)
VTH = 0.21 V
```

早期论文文字还给出另一组 IGZO 数据：迁移率 10.05 cm2/(V s)、SS 0.86 V/dec、Ion/Ioff 约 5.28e5、VTH 5.00 V。两组数据来源/批次不同，不能拼成同一器件模型。

30 nm 是工艺物理厚度，10 nm 是当前 SPICE 有效 TOX 口径，必须分栏记录。

## 6. 当前证据

| 内容 | 等级 | 状态 |
|---|---|---|
| 老师要求、论文和学长资料索引 | E3 | 已有来源哈希和自动检查 |
| 二维双栅静电基准 | E2 | 已运行，只能解释电势与耦合 |
| 学长 IGZO 参考曲线 | E1 | 条件不完整，只作导入和质量参考 |
| 条件完整的漂移扩散电流模型 | E0 | 待实现 |
| IGZO 多曲线紧凑模型标定 | E0 | 待实现 |
| 有源负载逻辑电路 | E0 | 架构已定，待实现 |
| IGZO 单管 GDS 外部基线 | E2 | 可复用，需迁入新教学 PDK |
| 标准单元 DRC/LVS | E0 | 待实现 |
| HZO 扩展 | E0/E1 | 文献与计划 |

旧电路数值不属于当前单极性逻辑的结果，不能继续引用为当前环振频率或全加器验证。

## 7. 高难度五组参数

1. 双栅偏压与上下栅电容比。
2. 体/界面陷阱。
3. 接触电阻或势垒。
4. 沟道/介质几何。
5. 温度。

电路层额外扫描第二栅负载偏压、`Wload/Wdriver`、VDD 和 Cload。

## 8. 工作顺序

1. 冻结主 IGZO 数据集、单位和来源。
2. 完成 T01 单栅漂移扩散最小案例。
3. 完成 T02 双栅电流与 T03 五组参数。
4. 完成 M00/M01 紧凑模型双轨标定。
5. 只做一个完整 C00 反相器。
6. 对同一个 INV 建立 GDS、DRC 和几何 LVS 最小闭环。
7. 扩展基础门、环振和全加器。
8. 最后再决定是否实现 HZO/NLS。

不能从大电路倒推器件参数，也不能在 C00 失败时直接做环振。

## 9. 工程目录

```text
AGENTS.md                所有仓库型 AI 的强制第一入口
ARCHITECTURE.md          总体依赖、接口和验收门
PROJECT_PLAN.md          阶段与里程碑
STATUS.md                当前完成/待完成
DECISIONS.md             设计决策
AI_CONTEXT.md            其他 AI 必读上下文
AI_LOG.md                AI 修改和验证日志
config/                  机器可读范围和实验矩阵
data/                    原始/处理数据和哈希
tcad/                    二维器件结构与方程
models/                  Level 15、双栅、HZO 模型
spice/                   模型与器件/单元/模块网表
pdk/                     技术层、PCell、DRC、LVS
layout/                  单元、模块和 GDS
verification/            仿真、DRC/LVS 与故障注入
results/                 图、表和机器报告
report/                  12 章独立源、组装清单和最终单 HTML
```

## 10. 当前阶段怎么验收

现在只验收架构，不验收模型性能：

- 正式题目和范围在所有入口一致。
- 活动配置只定义 IGZO。
- 每个阶段有输入、输出、依赖和 PASS 条件。
- 单极性逻辑拓扑和器件数固定。
- 旧范围电路结果不再作为当前证据。
- 项目结构检查通过。

## 11. 老师仍需确认

1. 最终主 IGZO 数据集及原始 Id-Vg/Id-Vd 是否能提供。
2. 是否接受 DEVSIM 作为二维器件工具。
3. 双栅是否有实测数据，还是允许做文献约束敏感性。
4. KLayout 几何 LVS 是否满足课程要求。
5. 单极性有源负载逻辑是否可作为器件到电路验证案例。
6. HZO 顶栅是否保留为可选扩展。

## 12. 快速入口

- AI 接手规范：[AGENTS.md](AGENTS.md)
- 总体架构：[ARCHITECTURE.md](ARCHITECTURE.md)
- 项目计划：[PROJECT_PLAN.md](PROJECT_PLAN.md)
- 当前状态：[STATUS.md](STATUS.md)
- 实验为什么这样做：[docs/09_知识点详解与实验设计原理.md](docs/09_知识点详解与实验设计原理.md)
- 二维 TCAD 路线：[docs/11_二维TCAD实施路线.md](docs/11_二维TCAD实施路线.md)
- 课程要求映射：[docs/12_课程要求映射与完整实验矩阵.md](docs/12_课程要求映射与完整实验矩阵.md)

## 13. 证据边界

本项目是课程研究和教学 PDK，不是流片签核 PDK。架构检查通过只表示文件、范围和依赖一致，不表示器件模型、电路、DRC/LVS 或 HZO 扩展已经实现。
