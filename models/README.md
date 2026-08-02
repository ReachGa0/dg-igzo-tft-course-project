# 模型目录

- `level61/`：AIM-Spice Level15/HSPICE Level61 参数、映射和拟合报告。
- `dual_gate/`：无回滞双栅静电耦合模型。
- `ferroelectric/`：HZO 回滞、NLS 与可靠性敏感性扩展。

每个模型必须同时提供方程、参数来源、有效范围、数值极限测试和证据等级。

当前 M00 已完成 `config/compact_m00_input_validation.json` 和 `references/m00_dataset_registry.csv` 定义的静态输入/验证合同，25/25 PASS、E3，并实现正式运行器与独立检查器。合成自测已通过，但尚未运行正式 9 条 train/163 点优化或 4 条 holdout/70 点评分，没有生成已验证模型，也没有运行 TCAD 或 SPICE。
