# AIM-Spice Level 15 模型合同

本目录保存 IGZO-only Level 15 候选、参数映射和有效范围。M00 R01 因 holdout gm 门失败，失败候选缺失继续保留；R02 已完成正式 runner 24/24 和独立检查 20/20，但本目录中的 `igzo_level15_r02.inc` 仍只是 M01 候选，尚未由 AIM-Spice 执行或验证。M01 revision-3 合同冻结了候选哈希、同一 247 行目标、工具指纹和输出边界；不得把候选写成最终模型卡、实验校准或原生 Level 61 物理参数。

计划文件：

```text
igzo_level15_r02.inc
igzo_level15_r02_parameters.json
results/reports/m01_simulator_cross_check_contract_v3.json
```

R02 候选生成不等于 AIM-Spice 运行。M01 必须使用同一 W/L、VBG/VTG/VDS、300 K、源极 0 V 和 `|ID|/W` 口径，独立报告路线差异；AIM-Spice Level 15 与 ngspice 行为路线不声称方程同一，30 nm 物理 Al2O3 与 10 nm 有效 TOX 仍必须分开记录。SnO、HZO、旧电路和外部教师数据不属于本路线。
