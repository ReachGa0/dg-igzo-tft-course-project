"""Assemble the teacher-facing submission directory and source/result indexes."""

import csv
import hashlib
import shutil
import subprocess
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "submission"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tracked_files() -> list[Path]:
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return [ROOT / item for item in raw.decode("utf-8").split("\0") if item]


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for child in OUT.iterdir():
        if child.is_file():
            child.unlink()
        elif child.is_dir():
            shutil.rmtree(child)

    report = ROOT / "report" / "final" / "课程报告.pdf"
    slides = ROOT / "ppt" / "slides.pdf"
    if not report.exists() or not slides.exists():
        raise SystemExit("build report/final/课程报告.pdf and ppt/slides.pdf before packaging")
    shutil.copy2(report, OUT / "report.pdf")
    shutil.copy2(slides, OUT / "slides.pdf")
    shutil.copy2(ROOT / "AI_LOG.md", OUT / "AI_LOG.md")

    (OUT / "ENVIRONMENT.md").write_text(
        """# 环境与安装记录

本项目为二维 IGZO 教学模型课程项目，提交时不需要运行 TCAD/SPICE。

## 已验证环境

- OS：Windows/WSL 工作区
- Python：项目 Makefile 的 `PYTHON` 解释器；脚本使用 Python 标准库，报告导出使用 Microsoft Edge headless。
- 器件数值：历史 DEVSIM 运行证据已落盘；本次打包没有重新运行。
- 电路交叉检查：历史 ngspice 与 GPL Xyce R04 产物已落盘；AIM-Spice 未启动。

## 安装/重建

在项目根目录执行 `make check` 和 `make report-check`。如果需要重建本提交目录，执行 `make submission`。
不要把 `.git`、`.cache`、`__pycache__` 或本机虚拟环境复制进老师提交包。
""",
        encoding="utf-8",
    )
    (OUT / "FINAL_STATUS.md").write_text(
        """# 最终 PASS/FAIL 摘要

## 已完成

- 课程报告主体：`report.pdf`，由 26 图、26 页自包含 HTML 课程报告导出。
- 答辩辅助：`slides.pdf`，10 页。
- T01/T02、T03-P1/P2/P3/P4/P5、M00/M01：均在冻结 IGZO 教学模型边界内有 E2/E3 运行或独立检查证据。
- 项目总检查：`make check` 767/767 PASS。
- 报告结构检查：`make report-check`，12 章、5 附录、0 未解决占位符、32 张审计图 PASS。

## 最终负结果

- C00 R04：33/36、E0/FAIL。四个开源进程返回 0，输出表和哈希完整；冻结锚点 VOH 约 0.0912 V、最大增益约 0.884、无单位增益交点和瞬态输出 crossing。
- C01--C03、组合逻辑、版图、PEX 和 HZO：关闭，不能写成已完成。
- 项目不主张实验校准、真实物理参数、流片签核或真实工作频率。
""",
        encoding="utf-8",
    )
    (OUT / "README.md").write_text(
        """# 双栅 IGZO TFT 课程项目提交包

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
""",
        encoding="utf-8",
    )

    files = tracked_files()
    source_roots = ("config", "data", "scripts", "tcad", "models", "spice", "tests", "verification", "pdk", "layout", "references", "report", "ppt")
    source_rows = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(source_roots) or rel in {"Makefile", "README.md", "ARCHITECTURE.md", "DECISIONS.md", "PROJECT_PLAN.md", "STATUS.md"}:
            source_rows.append([rel, str(path.stat().st_size), sha256(path)])
    write_csv(OUT / "INPUT_INDEX.csv", ["path", "bytes", "sha256"], sorted(source_rows))

    result_rows = []
    result_root = ROOT / "results"
    for path in sorted(result_root.rglob("*")):
        if path.is_file() and ".cache" not in path.parts:
            result_rows.append([path.relative_to(ROOT).as_posix(), str(path.stat().st_size), sha256(path)])
    write_csv(OUT / "RESULT_INDEX.csv", ["path", "bytes", "sha256"], result_rows)

    figure_rows = []
    image_suffixes = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
    for path in sorted((ROOT / "report" / "assets").glob("*")):
        if path.is_file() and path.suffix.lower() in image_suffixes:
            figure_rows.append([path.relative_to(ROOT).as_posix(), str(path.stat().st_size), sha256(path)])
    write_csv(OUT / "FIGURE_INDEX.csv", ["path", "bytes", "sha256"], figure_rows)
    print(f"submission files={len(list(OUT.iterdir()))} source_rows={len(source_rows)} result_rows={len(result_rows)} figures={len(figure_rows)} date={date.today().isoformat()}")


if __name__ == "__main__":
    main()
