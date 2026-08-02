# ngspice 模型合同

本目录将保存可审查的 IGZO 行为等效模型。它与 AIM-Spice Level 15 共用数据目标和误差指标，但不声称方程等价。

实现必须包含单元测试、参数来源、有效偏压范围和极限输入检查。

M00 R01 已完成一次正式参考核拟合，但因 L=12 um holdout gm 门失败而保持 E0/FAIL；合同因此没有生成或运行 ngspice 候选。后续新 revision 候选必须保持 IGZO-only，并在 M01 实际执行前标记为未验证候选。
