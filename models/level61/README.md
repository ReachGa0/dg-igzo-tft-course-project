# AIM-Spice Level 15 模型合同

本目录保存历史冻结的 IGZO-only Level 15 候选、参数映射和有效范围。M00 R01 因 holdout gm 门失败，失败候选缺失继续保留；R02 已完成正式 runner 24/24 和独立检查 20/20，但本目录中的 `igzo_level15_r02.inc` 仍只是未执行候选。M01 revision-3 合同冻结了候选哈希、同一 247 行目标、工具指纹和输出边界；用户随后披露本机 AIM-Spice 副本未获授权，因此该安装禁止进入正式证据链，候选不得由其正式执行。不得把候选写成最终模型卡、实验校准或原生 Level 61 物理参数。

计划文件：

```text
igzo_level15_r02.inc
igzo_level15_r02_parameters.json
results/reports/m01_simulator_cross_check_contract_v3.json
```

R02 候选生成不等于 AIM-Spice 运行。R01 工具/来源预检唯一运行 11/13、E0/FAIL：只静态读取 AIM-Spice 文件指纹且未启动，授权来源和 batch/CLI 两门失败；报告/日志已保留，数值输出全缺失。失败提交后必须另建开源第二路线合同。任何未来 M01 路线仍须使用同一 W/L、VBG/VTG/VDS、300 K、源极 0 V 和 `|ID|/W` 口径并独立报告路线差异；替代路线不得称为原生 AIM-Spice Level 15 或 HSPICE Level 61。30 nm 物理 Al2O3 与 10 nm 有效 TOX 仍必须分开记录，SnO、HZO、旧电路和外部教师数据不属于本路线。
