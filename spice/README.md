# SPICE 目录

- `models/`：统一器件与子电路模型。
- `netlists/devices/`：Id-Vg、Id-Vd、双栅和铁电器件测试。
- `netlists/cells/`：INV/NAND2/NOR2/XOR2 及测试。
- `netlists/blocks/`：RING5 和 FULL_ADDER_1BIT 及测试。

当前 `models/igzo_dg_behavioral_r02.inc` 是 M00 生成的 IGZO-only 行为候选。M01 revision-3 合同已冻结同一 247 行器件目标和路线差异口径，但候选尚未由 ngspice 执行；R01 工具/来源预检唯一运行只执行 `ngspice --version` 并以 11/13、E0/FAIL 保留，器件网表从未运行。用户披露的未授权 AIM-Spice 安装不进入正式证据链，替代开源第二路线须另建合同。不得把任何候选当作原生 HSPICE Level 61、实验校准或电路可用模型。SnO、HZO、旧电路和瞬态网表不属于当前 M01 范围。

参考网表是设计意图的单一主源。版图生成和 LVS 对比均使用同一份端口顺序与器件尺寸。
