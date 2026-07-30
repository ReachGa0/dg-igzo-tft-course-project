# AI Agent Project Instructions

> 本文件是所有仓库型 AI 的第一入口。开始分析、编辑、运行工具或给出项目结论前，必须先读完本文件。
> `STATUS.md` 是当前进度的唯一入口；本文件只保存长期有效的协作规则，不复制容易过期的任务状态。

## 1. 启动协议

每次接手按以下顺序执行：

1. 确认当前目录是本项目根目录。
2. 运行 `git status --short --branch` 和 `git log -5 --oneline --decorate`。
3. 工作区有未提交修改时，先判断它们是否来自用户或其他 AI，不得覆盖、还原或删除。
4. 按顺序阅读：
   - `README.md`
   - `AI_CONTEXT.md`
   - `ARCHITECTURE.md`
   - `STATUS.md`
   - `PROJECT_PLAN.md`
   - `DECISIONS.md`
   - `AI_LOG.md` 顶部最新记录
   - `config/project.json`
   - `config/experiments.json`
5. 用简短文字向用户复述：当前范围、已完成内容、证据边界、下一阶段和本次准备做什么。
6. 没有收到明确实施任务时，不启动新的 TCAD、SPICE、KLayout、DRC、LVS 或批量参数扫描。

若文档冲突，优先级为：用户最新明确指令、最新 ADR、`ARCHITECTURE.md`、机器可读配置、旧日志。无法可靠消解时先报告冲突。

## 2. 固定项目边界

- 项目 ID：`DG-IGZO-TFT-PDK`。
- 正式题目：基于双栅 IGZO TFT 的二维器件模型、紧凑模型与可编程单极性逻辑教学 PDK。
- 活动器件只有 n 型 IGZO，不重新加入 SnO 器件、模型、网表或版图。
- 历史文档中的 SnO 文字只用于解释范围变化，不是当前实现依据。
- 主电路采用双栅 IGZO 有源负载有比例逻辑；理想电阻负载只允许作为 `solver_smoke` 或 Boolean 降级验证。
- 固定器件数：`INV=2`、`NAND2=3`、`NOR2=3`、`XOR2=12`、`RING5=10`、`FULL_ADDER_1BIT=33`。
- HZO/铁电顶栅是可选扩展，基础器件、电路和版图闭环未通过前不得占用主线交付时间。
- 本项目是课程研究和教学 PDK，不得称为代工厂签核或可直接流片 PDK。
- 报告正文必须在 `report/chapters/` 按 12 章分别维护，附录在 `report/appendices/`；正式提交仍是自动组装的单个自包含 HTML。

## 3. 证据与表述规则

- `E0`：计划或未实现。
- `E1`：文献或外部参考支持，项目未复现。
- `E2`：项目脚本可运行并有基本自测。
- `E3`：有自动验收、故障注入或独立数据验证。
- `E4`：老师、实验或独立外部工具确认。

必须遵守：

1. T00 仅为二维双栅静电基准，不含移动电荷、陷阱、接触和漏电流，不能据此报告迁移率、SS 或 Id。
2. 学长数据元信息不完整，只能标记为 `reference_only`。
3. 不得把旧互补电路数值写成当前单极性逻辑结果。
4. 没有双栅实测数据时，不得声称“精确实验拟合”。
5. 30 nm Al2O3 是工艺物理厚度，10 nm TOX 是当前 SPICE 有效口径，必须分开记录。
6. ngspice 行为等效模型不得称为原生 HSPICE Level 61；AIM-Spice Level 15 才对应教师指定路线。
7. 图表和报告必须写明输入、单位、偏压、温度、模型版本和证据等级。

## 4. 阶段门

- 没有条件完整数据时，只能做教学参数或敏感性分析。
- T01 最小案例未收敛，不做大规模 T02/T03 扫描。
- M00 没有训练/验证误差，不做定量电路预测。
- C00 反相器未通过，不做环振和全加器。
- INV 的几何 LVS 未通过，不扩展大模块版图。
- 基础闭环未完成，不进入 HZO/NLS 或 PEX 扩展。

完整依赖和验收标准以 `ARCHITECTURE.md` 与 `config/experiments.json` 为准。

## 5. 文件与实现纪律

- 优先沿用现有目录、配置和脚本，不另建平行工程。
- `data/raw/` 是冻结来源，不手工改数据；需要清洗时写入 `data/processed/` 并保存来源哈希。
- 源码、配置、原始输出、处理结果和图表分开存放。
- 每个实验保存输入、参数快照、命令、工具版本、原始输出、处理输出和 PASS/FAIL 报告。
- 不把缓存、虚拟环境、密码、Token、SSH 私钥或本地临时文件提交到 Git。
- 不做与当前任务无关的大范围重构。
- 不删除用户或其他 AI 的未提交修改；禁止 `git reset --hard` 和强制推送。
- 外部论文和学长资料默认只建立 manifest/哈希，未经确认不复制受限原文到仓库。

## 6. 修改后的必做检查

至少执行：

```bash
make check
git status --short
git diff --check
```

涉及报告源、清单、图片或构建器时，额外执行 `make report-check`。

涉及领域实现时还要运行对应的最小测试，并在最终说明中明确哪些测试没有运行。

任何实质修改都要：

1. 在 `AI_LOG.md` 顶部追加可验证记录。
2. 同步 `STATUS.md` 的已完成、未完成和下一步。
3. 重新运行 `make check`。
4. 检查 `git diff`，只暂存本次相关文件。
5. 仅在用户要求保存版本时执行 `git commit` 和 `git push`。

## 7. Git 协作规则

- 远端：`git@github.com:ReachGa0/dg-igzo-tft-course-project.git`。
- 主分支：`main`。
- 单个 AI 顺序工作时可在 `main` 上提交。
- 多个 AI 并行工作时，每个任务使用独立分支，例如 `ai/t01-drift-diffusion`。
- 拉取前先检查工作区；工作区干净时使用 `git pull --ff-only`。
- 提交信息说明完成的结果，例如 `feat: add minimal T01 drift-diffusion case`。
- 不提交未验证结果，不改写已经推送的历史，不使用 `--force`。

## 8. 完成汇报格式

任务结束时向用户说明：

1. 实际修改了什么。
2. 哪些结果已验证，证据等级是什么。
3. 运行了哪些命令及其 PASS/FAIL。
4. 哪些内容仍未完成或存在风险。
5. 如已保存版本，给出分支、提交短哈希和推送状态。

不要只说“已经完成”，也不要把结构检查通过写成领域仿真通过。

## 9. 本机来源路径

- 项目：`/mnt/c/Users/ReachGao/Desktop/SDU/科研/氧化物TFT_铁电双栅课程项目`
- 论文：`/mnt/c/Users/ReachGao/Desktop/SDU/科研/论文`
- 老师要求：`/mnt/c/Users/ReachGao/Desktop/deepseek_work/大学课程/氧化物/实验/实验课程项目与报告要求(1).html`
- 学长参考：`/mnt/c/Users/ReachGao/Desktop/deepseek_work/大学课程/氧化物/实验/学长`
- ngspice 基线：`/mnt/c/Users/ReachGao/Desktop/deepseek_work/大学课程/氧化物/数据/ngspice_results`
- AIM-Spice 基线：`/mnt/c/Users/ReachGao/Desktop/deepseek_work/大学课程/氧化物/数据/AIMSPICE_improved`
- KLayout 基线：`/mnt/c/Users/ReachGao/Desktop/deepseek_work/大学课程/氧化物/数据/klayout_oxide_pdk`
