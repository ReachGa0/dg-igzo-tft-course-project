# SPICE 目录

- `models/`：统一器件与子电路模型。
- `netlists/devices/`：Id-Vg、Id-Vd、双栅和铁电器件测试。
- `netlists/cells/`：INV/NAND2/NOR2/XOR2 及测试。
- `netlists/blocks/`：RING5 和 FULL_ADDER_1BIT 及测试。

参考网表是设计意图的单一主源。版图生成和 LVS 对比均使用同一份端口顺序与器件尺寸。
