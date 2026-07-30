# 报告目录

报告采用两层结构：**写作和审阅按章节拆分，课程提交仍为一个自包含 HTML**。这同时满足老师最新“最好分章节”的口头建议和原书面“单文件 HTML”要求。

```text
report/
|-- manifest.json                 # 12章、5个附录、外壳和输出顺序的唯一清单
|-- src/实验报告_草稿.xhtml       # 标题、内联CSS、目录和章节容器，不放正文
|-- chapters/                     # 01至12章，每章一个XHTML片段
|-- appendices/                   # 附录A至E，每个附录一个XHTML片段
|-- assets/                       # 构建前图片，章节统一引用 assets/<文件名>
|-- evidence_matrix.csv           # 结论到数据、脚本和命令的索引
`-- final/实验报告.html           # 唯一正式提交报告，由构建器生成
```

## 写作流程

1. 只编辑任务对应的 `report/chapters/*.xhtml` 或 `report/appendices/*.xhtml`。
2. 不手工复制章节，不直接编辑 `report/final/实验报告.html`。
3. 新章节文件或顺序变化必须同步 `report/manifest.json`。
4. 图片放入 `report/assets/`，章节内使用 `assets/FigXX_name.png`。
5. 每次修改后运行 `make report-check`。

只检查章节清单、片段 ID、目录组装、图片和占位符状态：

```bash
make report-check
```

当前草稿允许 `[待填写...]`。正式构建会拒绝任何未解决占位符：

```bash
make report
```

构建器按清单生成目录，组装 12 章和 5 个附录，将图片转换为 Base64，并输出 `report/final/实验报告.html`。打印 CSS 会让每章另起一页。最终文件不能依赖网络、外部 CSS/脚本、本地绝对路径或同目录图片。
