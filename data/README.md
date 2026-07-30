# 数据目录

- `raw/`：只读输入。`baseline/` 由 `make import-baseline` 从已有课程资产导入并记录 SHA-256。
- `processed/`：清洗、统一单位、论文图表数字化和拟合用数据。

不直接修改 `raw/` 中的文件。任何修正都通过脚本生成 `processed/` 文件，并保留来源列。
