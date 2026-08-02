# AIM-Spice Level 15 模型合同

本目录将保存 IGZO Level 15 模型卡、参数来源、有效范围和多曲线误差报告。M00 输入数据集和验收门已静态冻结，但正式拟合和 AIM-Spice 执行尚未进行；当前不得放入未经验证即标为最终的模型卡。

计划文件：

```text
igzo_level15_r01.inc
igzo_level15_r01_parameters.json
igzo_level15_r01_fit_report.json
```

`igzo_level15_r01.inc` 即使由后续 M00 生成，在 M01 实际运行 AIM-Spice Level 15 前也只能标记为候选。AIM-Spice Level 15 与 ngspice 行为路线不声称方程同一；30 nm 物理 Al2O3 与 10 nm 有效 TOX 仍必须分开记录。
