# 物理模型

按层次保存方程与参数：

1. `electrostatic`：Poisson/Laplace、介电常数和边界条件；
2. `drift_diffusion`：载流子连续性、迁移率和复合；
3. `traps`：体陷阱、界面陷阱和占据统计；
4. `contacts`：欧姆接触、势垒或串联电阻；
5. `ferroelectric`：仅在静电和输运基线通过后加入。

每个参数必须标记 `measured`、`course`、`literature`、`fitted` 或 `assumed`。
