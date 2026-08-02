# 模型目录

- `level61/`：AIM-Spice Level15/HSPICE Level61 参数、映射和拟合报告。
- `dual_gate/`：无回滞双栅静电耦合模型。
- `ferroelectric/`：HZO 回滞、NLS 与可靠性敏感性扩展。

每个模型必须同时提供方程、参数来源、有效范围、数值极限测试和证据等级。

当前 M00 静态输入/验证合同 25/25 PASS、E3。R01 已按冻结 9 条 train/163 点和 4 条 holdout/70 点唯一运行，但 L=12 um holdout gm 相对误差 `0.512384` 超过 `0.50`，故运行器 21/24、E0/FAIL。失败参数与预测只作诊断；独立检查和模型候选没有运行/生成，也没有运行 TCAD 或 SPICE。
