# 双栅 IGZO TFT 课程项目提交包

本目录是老师直接查看的交付入口。正式报告是 `report.pdf`，答辩材料是 `slides.pdf`。

完整输入、脚本、模型、原始结果、处理数据和图表仍按原项目目录保存：

- `config/`：阶段配置和预注册合同
- `data/`：原始/处理数据与来源边界
- `scripts/`、`tcad/`、`models/`、`spice/`：重建脚本、模型和网表输入
- `results/`：原始结果、处理表、图、日志和 PASS/FAIL 报告
- `report/`、`ppt/`：HTML/PDF、报告章节、图片和演讲材料

索引见 `INPUT_INDEX.csv`、`RESULT_INDEX.csv`、`FIGURE_INDEX.csv`；环境见 `ENVIRONMENT.md`；
最终口径见 `FINAL_STATUS.md`，AI 参与记录见 `AI_LOG.md`。

## 一条重建命令

在项目根目录执行：

```bash
make submission
```

该命令只组装提交目录，不启动 TCAD、SPICE、版图或 HZO。
