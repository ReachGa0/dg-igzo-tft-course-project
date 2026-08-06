# 环境与安装记录

本项目为二维 IGZO 教学模型课程项目，提交时不需要运行 TCAD/SPICE。

## 已验证环境

- OS：Windows/WSL 工作区
- Python：项目 Makefile 的 `PYTHON` 解释器；脚本使用 Python 标准库，报告导出使用 Microsoft Edge headless。
- 器件数值：历史 DEVSIM 运行证据已落盘；本次打包没有重新运行。
- 电路交叉检查：历史 ngspice 与 GPL Xyce R04 产物已落盘；AIM-Spice 未启动。

## 安装/重建

在项目根目录执行 `make check` 和 `make report-check`。如果需要重建本提交目录，执行 `make submission`。
不要把 `.git`、`.cache`、`__pycache__` 或本机虚拟环境复制进老师提交包。
