# AIM-Spice Level 15 模型合同

本目录将保存 IGZO Level 15 模型卡、参数来源、有效范围和多曲线误差报告。M00 R01 因 holdout gm 门失败，按合同没有生成 Level 15 候选；R02 当前只有 27/27 静态结构合同，执行链和正式拟合未运行，因此也没有 R02 候选或 AIM-Spice 执行。当前不得放入未经验证即标为最终的模型卡。

计划文件：

```text
igzo_level15_r01.inc
igzo_level15_r01_parameters.json
igzo_level15_r01_fit_report.json
```

上述 R01 计划文件因数值门失败均不存在；R02 对应文件也尚未生成。未来新 revision 即使生成，在 M01 实际运行 AIM-Spice Level 15 前也只能标记为候选。AIM-Spice Level 15 与 ngspice 行为路线不声称方程同一；30 nm 物理 Al2O3 与 10 nm 有效 TOX 仍必须分开记录。
