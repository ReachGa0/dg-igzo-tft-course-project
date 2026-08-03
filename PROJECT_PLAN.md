# 项目计划

## 当前阶段

`M01_R11_PATH_SAFE_STATIC_CONTRACT_PASS_E3_NEXT_RUNNER`：T01/T02/T03 数值门已关闭，历史失败保留。M00 R01 保持 21/24、E0/FAIL；R02 runner 24/24 E2、独立检查 20/20 E3，只在冻结 IGZO 教学数值域内关闭 M00。M01 revision-3 合同 32/32 E3，R01 工具/来源预检唯一运行 11/13、E0/FAIL，开源恢复合同 30/30 E3。Xyce build/tool R01 执行 14/29、独立 9/20 E0/FAIL；R02/R03/R04 静态合同分别唯一检查 22/25、21/25、25/26 E0/FAIL。R05 静态合同 27/27 E3 后，runner 唯一运行 19/29 E0/FAIL；R06 静态合同 36/37 E0/FAIL。R07 静态合同 39/39 E3 后 runner 唯一返回 42/47 E0/FAIL，原因是 `.prn`/`.csv` 输出合同缺陷；R08 静态 checker 唯一执行因预期 36、实际注册 30 而在写报告前失败，归档保留；R09 静态 checker 唯一返回 34/36 E0/FAIL。R10 静态合同唯一返回 36/36 PASS、E3；runner 唯一运行通过版本、许可证和 1.25 V B-source 自测后，因中文绝对路径不能按 ASCII 写入 parser-only 网表而失败，parser 命令与独立检查未运行。R10 不重跑。R11 静态合同唯一返回 36/36 PASS、E3，下一门是提交后的单次 32 项 runner；独立检查和正式器件 DC 仍关闭。

## 截止日期

| 节点 | 日期 | 必须可见的成果 |
|---|---|---|
| 选题/架构确认 | 2026-07-30 | 题目、范围、完整架构、数据缺口、风险和老师待确认项 |
| PPT | 2026-08-06 | 至少 T01/M00/C00 中的真实中期结果，不使用旧范围电路数值 |
| 报告 | 2026-08-13 | 12 章独立源、单文件 HTML、完整工程、数据、代码、图表和复现说明 |

## 工作包

| WP | 时间 | 内容 | 退出条件 |
|---|---|---|---|
| WP0 | 07-30 | 架构与数据冻结 | S00 审计 PASS，G0 决策和老师问题清单形成 |
| WP1 | 07-31 至 08-01 | T01 单栅漂移扩散 | Id-Vg/Id-Vd、内部状态、守恒和网格比较 |
| WP2 | 08-01 至 08-03 | T02/T03 双栅与五组参数 | 五组不少于三点，趋势定量且可解释 |
| WP3 | 08-02 至 08-04 | M00/M01 紧凑模型 | 双轨参数、拟合/验证误差和适用域 |
| WP4 | 08-03 至 08-05 | C00 与 INV 版图闭环 | VTC/延迟/功耗、GDS、DRC、几何 LVS |
| WP5 | 08-04 至 08-06 | 基础门、环振、全加器 | 真值表、频率、延迟和层次版图 |
| WP6 | 08-05 至 08-06 | PPT 冻结 | 每张图有条件、单位、命令和证据等级 |
| WP7 | 08-07 至 08-10 | 可选 HZO/PEX | 基础闭环完成后才进入 |
| WP8 | 08-10 至 08-13 | 分章报告与交付 | 12 章分别审阅、单 HTML 无占位符且断网可读 |

## 阶段门

1. `G0 数据门`：没有条件完整数据时，只能做教学参数或敏感性。
2. `G1 数值门`：T01 不收敛，不进入大批量扫描。
3. `G2 模型门`：M00 无验证误差，不进入定量电路预测。
4. `G3 反相器门`：C00 未通过，不做环振和全加器。
5. `G4 版图门`：INV 未完成几何 LVS，不扩展大模块版图。
6. `G5 扩展门`：基础闭环未完成，不做 HZO/NLS。

## 任务状态

| ID | 任务 | 状态 | 当前证据 |
|---|---|---|---|
| A00 | 范围与总体架构 | DONE，待老师确认 | `ARCHITECTURE.md` |
| S00 | 来源、单位和数据冲突审计 | DONE，G0 教学参数限定 | `data/processed/s00/` 与 `results/reports/s00_data_audit.json`，E3 审计 |
| T00 | 二维双栅静电基准 | DONE，E2 | 既有 JSON/CSV/VTK/PNG |
| T01 | 单栅漂移扩散 | DONE，E2 教学模型数值门 | `results/reports/tcad_t01_d_extraction.json`；状态、守恒、网格代理比较与独立检查完整，不代表实验标定 |
| T02 | 双栅电流与阈值耦合 | DONE，E2 教学模型数值门 | T02-A/B/C 证据完整；双向族、受限代理、回程、互易和六状态均通过，不代表实验标定 |
| T03 | 五组器件参数 | DONE，E3；P2/P3 FAILURES PRESERVED | P1/P2/P3/P4/P5 均有正式结果与独立检查；P5 为 3/123/93、runner 14/14、independent 15/15，只关闭冻结教学模型数值门 |
| M00 | IGZO 教学多曲线代理拟合 | DONE_WITH_LIMITATION，R02 RUN E2 / CHECK E3 | R01 21/24、E0/FAIL永久保留；R02 27/27 静态 PASS、runner 24/24、独立检查 20/20，原 9/163 train、4/70 holdout 和所有门槛不变。仅关闭冻结教学数值域；候选已生成但未执行 |
| M01 | 双仿真器对照 | PREFLIGHT E0/FAIL；R07 runner 42/47 E0/FAIL；R08 checker 30/36 E0/FAIL；R09 checker 34/36 E0/FAIL；R10 static 36/36 E3、runner Unicode 路径 E0/FAIL；R11 static 36/36 E3、runner 未运行 | revision-3 32/32、开源恢复 30/30；R01 执行 14/29、独立 9/20，R02/R03/R04 静态合同 22/25、21/25、25/26 均保留。R05 合同 27/27 E3、runner 19/29 E0/FAIL；R06 静态合同 36/37；R07 build/tool 生成器/Xyce 安装成功但 self-test 输出合同失败；R08/R09 checker 失败；R10 三个 Xyce 工具命令通过但 parser-only 网表写入失败；R11 静态合同 36/36 E3 只证明路径安全工具/输出合同，runner/独立检查与正式器件 DC 继续关闭 |
| C00 | 有源负载 INV | TODO | 架构与器件数已定 |
| C01 | NAND2/NOR2/XOR2 | TODO | 依赖 C00 |
| C02 | RING5 | TODO | 依赖 C00 |
| C03 | 一位全加器 | TODO | 依赖 C01 |
| L00 | PCell/GDS | TODO | IGZO 单管外部基线可参考 |
| V00 | 电路级 DRC | TODO | deck 合同已定 |
| V01 | 几何 LVS | TODO | 依赖 L00 |
| PEX0 | 简化寄生 | OPTIONAL | 基础 LVS 后再做 |
| FE0 | HZO 扩展 | OPTIONAL | 基础闭环后再做 |
| R00 | 分章写作与单文件 HTML | SCAFFOLDED，E2 | 12 章、5 附录、清单和组装检查通过 |

## 当前下一件事

M00 R01/R02 和 M01 R01/R02/R03/R04/R05/R06/R07/R08/R09/R10 均不重跑，不放宽门槛、不改变 split 或用 holdout 选参数。M01 revision-3、开源恢复、Xyce build/tool R01 合同、R05 合同、R07、R10 与 R11 静态合同分别为 32/32、30/30、25/25、27/27、39/39、36/36、36/36 E3；R01 执行/独立检查 14/29、9/20，R02/R03/R04 静态合同 22/25、21/25、25/26，R05 runner 19/29，R06 静态合同 36/37，R07 runner 42/47，R08 checker 注册 30/36，R09 checker 34/36，R10 runner 为 Unicode 路径写入失败，证据均保留。R11 静态 PASS 只证明工具/输出合同；下一步提交并推送该 PASS，再唯一执行 32 项 runner。runner PASS 提交前不得执行独立 checker，正式 M01 器件 DC、电路、版图、PEX 和 HZO 继续关闭。
