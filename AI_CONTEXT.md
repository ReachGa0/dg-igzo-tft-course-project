# AI 工作上下文

> 仓库型 AI 必须先读取根目录 `AGENTS.md`。本文件提供详细项目事实，当前进度以 `STATUS.md` 为准。

## 必读顺序

1. `AGENTS.md`
2. `README.md`
3. `ARCHITECTURE.md`
4. `STATUS.md`
5. `PROJECT_PLAN.md`
6. `DECISIONS.md`
7. `AI_LOG.md`
8. 与任务对应的 `docs/*.md`

## 当前权威范围

- 项目 ID：`DG-IGZO-TFT-PDK`。
- 题目：基于双栅 IGZO TFT 的二维器件模型、紧凑模型与可编程单极性逻辑教学 PDK。
- 活动器件只有 n 型 IGZO。
- 电路采用双栅 IGZO 有源负载有比例逻辑；电阻负载仅作求解/功能降级。
- S00 数据审计已完成，T01-A 输入合同已冻结但未运行仿真，G0 为 `TEACHING_BASELINE_ONLY`；除既有 T00 外，T01/M00/C00/L00/V01 均未实现。
- HZO 是可选扩展，不能阻塞基础闭环。

## 硬性事实

- 当前日期：2026-07-30。
- PPT：2026-08-06；报告：2026-08-13。
- 基础工艺：Si/300 nm SiO2/50 nm Al/30 nm Al2O3/24 nm IGZO/50 nm Ti。
- IGZO 尺寸：`W/L=60/10 um`。
- 物理 Al2O3 厚度 30 nm；当前 SPICE 有效 TOX 10 nm，两者不得混写。
- 后续课程口径：迁移率约 35.5 cm2/(V s)、VTH 0.21 V、k 6.8。
- 早期论文口径：迁移率 10.05 cm2/(V s)、SS 0.86 V/dec、Ion/Ioff 约 5.28e5、VTH 5.00 V。
- 两组 IGZO 数据不能拼成同一器件参数。
- ngspice 未来使用行为等效模型，不是 HSPICE Level 61。
- AIM-Spice 对应教师指定 Level 15/HSPICE Level 61 路线。
- 报告按 12 个独立章节源写作和审阅，最终组装为单文件 HTML且全部图片内嵌；高难项目至少五组参数。

## 固定器件数

```text
INV=2, NAND2=3, NOR2=3, XOR2=12, RING5=10, FULL_ADDER_1BIT=33
```

## 证据等级

- `E0`：计划或未实现。
- `E1`：文献支持，未在项目复现。
- `E2`：脚本可运行并自测。
- `E3`：有自动验收、故障注入或独立数据验证。
- `E4`：老师、实验或外部工具确认。

## 当前已有证据

- S00 来源、单位和数据边界审计：E3；T01 仅允许使用教学参数，禁止实验拟合。
- T00 二维双栅静电：E2；不含移动电荷、陷阱、接触和漏电流。
- 学长 IGZO 曲线：E1/reference_only；元数据不完整。
- IGZO 单管外部 GDS：E2 基线，可参考但尚未迁入新 PDK。
- 其余领域任务：E0。

## AI 强制规则

1. 不得引用旧范围电路数值作为当前单极性逻辑结果。
2. 不得在没有双栅实测时写“精确实验拟合”。
3. 每个实验保存输入、参数快照、命令、版本、原始输出、处理输出和 PASS/FAIL。
4. C00 未通过不得做环振和全加器；INV LVS 未通过不得扩展大版图。
5. LVS 必须从 GDS 几何提取，并有断路/短路/错标故障注入。
6. 行为模型不能写成 Level 61；教学 PDK 不能写成流片签核。
7. 有实质修改后更新 `AI_LOG.md` 和 `STATUS.md`。
8. 用户已授权完成 T01-A 输入合同。T01-B 才能以 `IGZO_T01_TEACHING_BASELINE_V1` 做 E2 教学参数仿真；未经新指令不得启动 T02、SPICE、KLayout 或批量扫描。

## 原始资产路径

- 论文：`/mnt/c/Users/ReachGao/Desktop/SDU/科研/论文`
- 老师要求：`/mnt/c/Users/ReachGao/Desktop/deepseek_work/大学课程/氧化物/实验/实验课程项目与报告要求(1).html`
- 学长参考：`/mnt/c/Users/ReachGao/Desktop/deepseek_work/大学课程/氧化物/实验/学长`
- ngspice 外部基线：`/mnt/c/Users/ReachGao/Desktop/deepseek_work/大学课程/氧化物/数据/ngspice_results`
- AIM-Spice 外部基线：`/mnt/c/Users/ReachGao/Desktop/deepseek_work/大学课程/氧化物/数据/AIMSPICE_improved`
- KLayout 外部基线：`/mnt/c/Users/ReachGao/Desktop/deepseek_work/大学课程/氧化物/数据/klayout_oxide_pdk`

## 完成定义

架构任务完成需要：范围一致、DAG 完整、接口明确、器件数固定、旧结果边界清楚、自动结构检查通过。它不等于任何新模型或电路已经实现。
