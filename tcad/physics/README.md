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

## 当前 T03-P2-BULK-TRAPS 静态合同

- 来源：DOI `10.3390/electronics9101652`；NTA 取 `1e18/5e18/5e19 cm^-3 eV^-1`，NGA 取 `1e16/5e16/5e17 cm^-3 eV^-1`，两组都另有零控制。来源器件为不同单底栅高偏压结构，只作 E1 敏感性输入。
- 能量：`epsilon=Ec-E`，`g_TA=NTA*exp(-epsilon/WTA)`，`WTA=0.08 eV`；`g_GA=NGA*exp(-((epsilon-EGA)/WGA)^2)`，`EGA=0.5 eV`、`WGA=0.2 eV`。
- 占据：`f_t=1/(1+(Nc/n)*exp(-epsilon/(k_B*T)))`；受主态空时中性、占据时带一个负电荷。Poisson 节点源为 `q*(n_TA+n_GA)`，并显式提供 `Electrons` 解析导数。
- 积分：`0~3.0 eV` 上固定 96 点 Gauss-Legendre；静态检查器用 32768 区间 Simpson 独立对照，最大相对误差 `7.93e-7`。
- 隔离：NTA 扫描时 NGA=0，NGA 扫描时 NTA=0，双界面 `D_it=0`；NTD/NGD、SRH、动态捕获-发射、迟滞与 bias stress 延后。
- 当前证据：29/29 静态合同 PASS，`simulation=NOT_RUN_BY_CONTRACT_CHECK`。下一门是零控制、NTA 参考和 NGA 参考三案例方程冒烟，不是正式 transfer 扫描。
