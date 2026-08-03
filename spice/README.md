# SPICE 目录

- `models/`：统一器件与子电路模型。
- `netlists/devices/`：Id-Vg、Id-Vd、双栅和铁电器件测试。
- `netlists/cells/`：INV/NAND2/NOR2/XOR2 及测试。
- `netlists/blocks/`：RING5 和 FULL_ADDER_1BIT 及测试。

当前接受的电路桥接输入是 `models/igzo_dg_behavioral_r03_portable.inc`。M01 R03 已在冻结 247 行教学域完成 42/30/24 E3/E2/E3 的 ngspice/GPL-Xyce 器件级链，并仅以 `M01_TEACHING_MODEL_ONLY_PASS` 受限关闭；R01/R02、根因和 build/tool 失败仍保留。该候选不是原生 HSPICE Level 61、物理参数卡或实验校准模型。

`C00_ACTIVE_LOAD_INVERTER_R01` 当前仅为 `contract_implemented/E0`：配置与 48/36/29 三门源码已存在，但静态合同尚未运行，`netlists/cells/` 下没有正式 C00 网表，也没有 VTC、瞬态或功耗输出。未授权 AIM-Spice、SnO、HZO、C01+、版图和 PEX 不进入本门。

参考网表是设计意图的单一主源。版图生成和 LVS 对比均使用同一份端口顺序与器件尺寸。
