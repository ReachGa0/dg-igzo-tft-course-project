# 物理模型

按层次保存方程与参数：

1. `electrostatic`：Poisson/Laplace、介电常数和边界条件；
2. `drift_diffusion`：载流子连续性、迁移率和复合；
3. `traps`：体陷阱、界面陷阱和占据统计；
4. `contacts`：欧姆接触、势垒或串联电阻；
5. `ferroelectric`：仅在静电和输运基线通过后加入。

每个参数必须标记 `measured`、`course`、`literature`、`fitted` 或 `assumed`。

## 当前 T03-P2-DIT 方程合同

- 位置：仅 `bottom_oxide_channel`；`region0=bottom_oxide`，`region1=channel`。`channel_top_oxide` 的 `D_it` 固定为 0。
- 物理面电荷：`Q_it=-q*D_it*(Potential@r1-Psi_neutral)`；`D_it` 单位为 `cm^-2 eV^-1`，`Psi_neutral=0 V` 是 `assumed` 教学参考。
- DEVSIM 组装：保留连续 `PotentialEquation`，另以 `fluxterm` 加入 `q*D_it*(Potential@r1-Psi_neutral)=-Q_it`。
- 来源：DOI `10.1039/D6TC00357E` 的 `D_it` 只标记为 `literature/E1` 范围，不是本项目测量或拟合参数。
- 当前证据：零极限和代表方程冒烟 E3；零控制 + 3 文献约束点正式 transfer sensitivity 也为 E3。未实现能量分布、bulk tail/deep states、捕获-发射、迟滞或 bias stress。
